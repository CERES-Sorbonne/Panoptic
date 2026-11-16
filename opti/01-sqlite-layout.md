# 01: data.db layout

Status 2026-11-16: specification, reviewed. This note defines the `data.db` file. §3 is the
full schema and the one source of truth for tables and columns, §4 the encoding of each property
type, §7 the rules every reader and writer follows. Notes [03-elements.md](03-elements.md)
(images, files, instances) and [04-moves-and-deletions.md](04-moves-and-deletions.md) (rescans,
missing files) describe the model and the behaviour, and refer here for tables and columns. The
other database files are in [02-storage.md](02-storage.md). §8 lists the open questions, each
with its context, the options and a proposed answer. Until a question is closed, the schema
follows the proposed answer only where §8 says so.

In this note, **must** marks a requirement on the system. A sentence without it is a
description or a reason.

Builds on [06-collection-manager.md](06-collection-manager.md) §5.1. Numbers come from the
`bench/collection` load bench (`results/load/report-1000000.md`), from a copy of its 1M
`data.db` rebuilt in the value layout below (timed with the `sqlite3` CLI, warm cache, median
of 5), and from the real project `~/panoptic-projects/express` (150k images, 457 MB `data.db`).

Diagrams of §3 for [drawDB](https://github.com/drawdb-io/drawdb) are in [sql/](sql/):
`data-db-drawdb.json` (laid out, *Import diagram*) and `data-db-drawdb.sql` (plain SQL with
foreign keys, *Import from SQL*). They are drawings only and leave out `STRICT`,
`WITHOUT ROWID` and indexes. The SQL file also leaves out the foreign key
`folders.status_scan_id → scans.id`, a cycle its import cannot take; the JSON has it.

Out of scope: migrating existing projects to this layout.

## 1. Scope and requirements

`data.db` holds the annotated data of a project: images, files, instances, subimages, their
property values, and the history of every change. It is a store, not a query engine. The
layout must serve four operations, and is chosen for them, not for ad-hoc queries:

1. **Load a property column.** On open, and when a column is first needed, the engine reads
   every value of one property and builds its typed column (note 05 §3.6). This is the hot read
   path. A column load must be one range read of one B-tree, with no decode per cell except for
   `box` (§4).
2. **Write values.** User edits, imports, scans and plugin results, from one cell to a whole
   column in one transaction. Each transaction takes one `sequence`. Writes the user may undo
   are commits and also write `entity_log` rows (§7).
3. **Read changes since a `sequence`.** The engine, once behind (after its own write, a plugin's
   or a script's), reads the values, deletes and schema changes newer than its sequence, without
   reloading whole columns. The cost must scale with the number of changes, not with the size
   of the tables. The engine is the only reader of changes: plugins read the data as it is when
   they run (note 09).
4. **Stay readable from outside.** Plugins read and write the file directly through the Python
   plugin API (note 09). Scripts read it with plain SQL. Every value must be in a typed column
   of a table documented here: no opaque blobs, no state that only the app can decode, no
   derived copy that a direct write would leave stale. The few JSON columns (`box` cells,
   `tags.parents`, `file_sources.excludes` and `metadata`, `entity_log.changes`) must stay
   readable with SQLite's `json_each` / `json_extract`.

Platform requirements:

- **SQLite 3.37 or later**, for `STRICT` tables (`RETURNING`, used in §7, needs 3.35). The
  backend and the plugin API must check `sqlite_version()` when they open the file and refuse
  an older library with a clear error.
- **Layout version.** `PRAGMA user_version` holds the layout version, 3 for the layout of this
  note (the version the drawings in `sql/` name). The backend and the plugin API must refuse a
  file with another version. A file with version 0 and no tables is new and gets created.

## 2. Performance points

What each operation of §1 costs, and how the layout handles it. Numbers are at 1M instances
from `bench/collection`.

### Column load

The cost is the bytes read from disk plus the work per row. A cold open (file not in the OS
cache) costs about twice a warm one: 1.60 s against 782 ms for the 7 bench columns
(`results/cache/report-1000000.md`).

- **Read only the property's rows, in one pass.** The key starts with `property_id`, so one
  column is one contiguous range of one B-tree. Value tables are `WITHOUT ROWID`: the row is
  stored in the key's B-tree, so a load is one sequential read, with no second lookup per row
  into a rowid table.
- **No decode per cell.** Values are stored as native SQLite types that map straight to the
  engine's column (§4): numbers as INTEGER / REAL, dates as unix ms INTEGER, checkboxes as
  0 / 1, text as raw UTF-8. No JSON text to unquote, no ISO date to parse (a parsed date
  column loads in 129 ms against 85 ms for a number column). The one exception is a `box`
  cell, a short JSON array parsed at load (§3 notes, §5).
- **Small rows.** The disk read scales with table size, so every row byte counts on a cold
  open. Images are referred to by an integer `image_id` into `images`, not by the
  40-character hex sha1 string of today's format. That also removes today's sha1 interning,
  which is most of the identity load (276 ms).
- **Live rows only.** Deleted values are removed from the value tables (their record goes to
  `tombstones`), so a load reads no dead rows and filters nothing. Measured by
  `bench/collection` (`results/tomb/report-1000000.md`): with half the cells deleted, a column
  loads in 18 ms from a table with a separate tombstone table, against 47 ms with tombstones
  kept inline.

### Writes

The cost is one B-tree update per table and per index, plus the `entity_log` entry.

- **Few indexes.** Each value table has its key and a `sequence` index. Tag tables also have
  a `tag_id` index, used only to delete a tag. No index on a column that every row shares
  (like an `operation` flag), and no index that repeats a primary key.
- **Batches in one transaction.** WAL with `synchronous=NORMAL`: a commit appends to the WAL
  without an fsync per write.
- **History is the largest cost.** `entity_log` and its indexes are 244 MB of the 457 MB of
  express in the old format. The layout of §3 (integer keys, `WITHOUT ROWID`, native values)
  is 2.5× smaller than text keys and writes a 1M-row import 7× faster (§5, history).

### Changes since a sequence

- Every value table and every large structural table (`images`, `files`, `instances`,
  `folders`, `subimages`) has an index on `sequence`, so "what changed since S" is a range
  read. The other tables are small and read whole.
- Deletes are read from `tombstones` (indexed by `sequence`), since a deleted row is gone from
  its table. A reader that syncs after every commit spends 12.7 ms in total over 2000 commits
  with the tombstone table, 49 ms with inline tombstones, and 7.4 s when it reloads the column
  after each delete (`results/tomb/report-1000000.md`).
- The engine is the only reader of changes, and it loads in full when the project opens. So
  tombstones are only needed while the backend runs: they are deleted at project open, and,
  while the backend runs, below the store's sequence (note 00 §5.2).

### Outside access

Not a speed cost, but it limits the options above. Tables are `STRICT` with typed columns, and
every speed-up must keep the data readable with plain SQL and writable by the plugin API.
Derived copies that a direct write would leave stale are out, which is why the column cache in
§6 is rejected.

## 3. Schema

### File settings

Set once, when the backend creates the file, before the first table:

```sql
PRAGMA page_size = 8192;      -- only takes effect before the first table (or with VACUUM)
PRAGMA journal_mode = WAL;    -- stored in the file: every later connection is in WAL mode
PRAGMA user_version = 3;      -- the layout version (§1)
```

Set by every connection, the backend's and the plugin API's, since SQLite does not store them:

```sql
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;   -- ms; a writer waits for the lock instead of failing (§7 rule 6)
PRAGMA mmap_size = 1073741824;
PRAGMA temp_store = MEMORY;
```

`foreign_keys` stays off: the schema declares no foreign keys. The `→ table.id` comments name
the references, and the writers keep them true by the rules of §7 (owned rows, permanent
deletes).

### Tables

```sql
-- Identity: image (content), file (location), instance (sample). Note 03.
-- AUTOINCREMENT on every table whose ids other rows or the engine refer to: an id is never
-- reused, so it can be the engine slot (note 05 §2) and an undo can re-insert a row with its
-- old id.

CREATE TABLE images (
  id   INTEGER PRIMARY KEY AUTOINCREMENT,
  hash BLOB NOT NULL UNIQUE,          -- first byte names the hash algorithm, then the digest
  size INTEGER NOT NULL,              -- bytes
  sequence INTEGER NOT NULL
) STRICT;
CREATE INDEX images_seq ON images(sequence);

CREATE TABLE files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  folder_id INTEGER NOT NULL,         -- → folders.id
  image_id  INTEGER NOT NULL,         -- → images.id
  name  TEXT NOT NULL,
  size  INTEGER NOT NULL,             -- size and mtime as of the last hash
  mtime INTEGER NOT NULL,             -- unix ms
  created_at INTEGER NOT NULL,        -- unix ms, when a scan added it
  status INTEGER NOT NULL,            -- 0 present, 1 missing. The file is also missing when
                                      -- any parent folder is
  status_scan_id INTEGER,             -- → scans.id, the scan or failed read that set the status
  added_scan_id  INTEGER,             -- → scans.id, the scan that found it as new
  sequence INTEGER NOT NULL
) STRICT;
CREATE UNIQUE INDEX files_location ON files(folder_id, name);   -- the rescan join
CREATE INDEX files_image   ON files(image_id);
CREATE INDEX files_added   ON files(added_scan_id);              -- the report's new list
CREATE INDEX files_missing ON files(folder_id) WHERE status = 1; -- the report's missing list
CREATE INDEX files_seq     ON files(sequence);

CREATE TABLE instances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL UNIQUE,           -- the user's id, one key space per project
  image_id INTEGER,                   -- → images.id, the truth. NULL: never resolved to a picture
  file_id  INTEGER,                   -- → files.id, a location hint. NULL: no file
  sequence INTEGER NOT NULL
) STRICT;
CREATE INDEX instances_image ON instances(image_id);  -- re-pointing on a content change
CREATE INDEX instances_file  ON instances(file_id);   -- re-pointing when a file goes
CREATE INDEX instances_seq   ON instances(sequence);

-- Subimages: fixed rectangles of an image, each in a namespace (a property: one per algorithm,
-- import or cut). Written through commits, like values. Separate from `images`: a project with
-- no namespace has empty subimage tables and nothing else changes.
CREATE TABLE subimages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  image_id     INTEGER NOT NULL,      -- → images.id
  namespace_id INTEGER NOT NULL,      -- → properties.id, the namespace (dtype 'namespace')
  x0 REAL NOT NULL, y0 REAL NOT NULL, -- 0..1, in the EXIF-rotated frame, quantized (§3 notes)
  x1 REAL NOT NULL, y1 REAL NOT NULL,
  sequence INTEGER NOT NULL
) STRICT;
CREATE UNIQUE INDEX subimages_box ON subimages(namespace_id, image_id, x0, y0, x1, y1);  -- one namespace = one range
CREATE INDEX subimages_image ON subimages(image_id);   -- the subimages of an image: overlays, purge
CREATE INDEX subimages_seq   ON subimages(sequence);

-- Locations. A folder stores a name and a parent, not a path: a move or relink is one row.
CREATE TABLE file_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dtype TEXT NOT NULL, name TEXT,
  root_url TEXT NOT NULL,             -- folder paths are relative to it: a relink is one write
  excludes TEXT,                      -- JSON list of relative paths removed from the project
  metadata TEXT,                      -- JSON, read once at open
  sequence INTEGER NOT NULL
) STRICT;

CREATE TABLE folders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,         -- → file_sources.id
  parent INTEGER,                     -- → folders.id. NULL: the source's root folder
  name TEXT NOT NULL,                 -- '' for the root. Path = root_url + names down from the root
  status INTEGER NOT NULL,            -- 0 present, 1 missing. Its subfolders and files are missing too
  status_scan_id INTEGER,             -- → scans.id
  sequence INTEGER NOT NULL
) STRICT;
CREATE UNIQUE INDEX folders_location ON folders(parent, name);
CREATE UNIQUE INDEX folders_root ON folders(source_id) WHERE parent IS NULL;  -- one root per source
CREATE INDEX folders_seq ON folders(sequence);

-- Scan results (note 04). Observed state: sequenced, not in entity_log, never tombstoned.
-- Small: a reader re-reads both whole when one has a row newer than its sequence.
CREATE TABLE scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,         -- → file_sources.id
  folder_id INTEGER,                  -- → folders.id, the scope. NULL: the whole source
  mode INTEGER NOT NULL,              -- 0 rescan folders, 1 rescan files, 2 failed read
  started_at INTEGER NOT NULL,        -- unix ms
  finished_at INTEGER,                -- unix ms. NULL: running or interrupted
  new_count INTEGER, missing_count INTEGER, changed_count INTEGER, back_count INTEGER,
  sequence INTEGER NOT NULL
) STRICT;

-- Changed files (same location, new hash) waiting for a choice. Rebuilt for its scope by each
-- rescan of files, which writes a `scans` row in the same transaction. No AUTOINCREMENT:
-- nothing refers to a pending change by id across rebuilds.
CREATE TABLE pending_changes (
  id INTEGER PRIMARY KEY,
  scan_id INTEGER NOT NULL,           -- → scans.id
  file_id INTEGER NOT NULL,           -- → files.id, already pointing to the new image
  old_image_id INTEGER NOT NULL,      -- → images.id, the image before the change
  decision INTEGER,                   -- NULL open, 0 values follow, 1 new picture
  sequence INTEGER NOT NULL
) STRICT;

-- Schema: small tables, results of entity_log like the values. No `operation` column
-- (deletions go to `tombstones`) and no `commit_id` (the last commit of a row is in entity_log).
CREATE TABLE property_groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, sequence INTEGER NOT NULL
) STRICT;

CREATE TABLE properties (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dtype TEXT,                         -- the property type (§4); 'namespace' for a namespace
  mode TEXT,                          -- 'image', 'instance' or 'subimage'
  name TEXT, access TEXT,
  tag_list_id INTEGER,                -- → tag_lists.id, for tag and multi_tags
  system_key TEXT,                    -- set for a system property (width, height, EXIF…)
  property_group_id INTEGER,          -- → property_groups.id
  namespace_id INTEGER,               -- → properties.id. Set: a 'subimage' property of one namespace
  sequence INTEGER NOT NULL
) STRICT;

CREATE TABLE tag_lists (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, sequence INTEGER NOT NULL
) STRICT;

CREATE TABLE tags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  list_id INTEGER,                    -- → tag_lists.id
  parents TEXT,                       -- JSON array of tag ids
  value TEXT, color INTEGER, sequence INTEGER NOT NULL
) STRICT;

-- History (§7, and §6 for the entity_log options) and the sequence counter.
CREATE TABLE commits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  group_id INTEGER,                   -- commits undone and redone as one
  source TEXT NOT NULL,               -- who wrote it: ui, import, scan, review, relink, or plugin:<name>
  timestamp INTEGER NOT NULL,         -- unix ms, UTC
  active INTEGER NOT NULL,            -- 0 once undone
  redoable INTEGER NOT NULL,          -- 1 while an undone commit can be redone; a new commit clears it
  undoable INTEGER NOT NULL,          -- 0 once it named a row deleted for good (§3, deletes)
  author TEXT                         -- the user
) STRICT;

-- One row per entity a commit touched. The entity is (table_id, k1, k2, k3): the table ids
-- and key order of the tombstones (§3, table ids). WITHOUT ROWID: the key is stored once.
CREATE TABLE entity_log (
  table_id  INTEGER NOT NULL,         -- §3, table ids
  k1        INTEGER NOT NULL,
  k2        INTEGER NOT NULL DEFAULT 0,   -- 0: not part of this key (ids start at 1)
  k3        INTEGER NOT NULL DEFAULT 0,   -- tag_id for the tag tables (4, 5, 7), else 0
  commit_id INTEGER NOT NULL,         -- → commits.id
  op        INTEGER NOT NULL,         -- 1 create, 2 update, 3 delete
  value     ANY,                      -- value tables (1, 2, 6): the value as in *_values.
                                      -- NULL for a delete and for every other table
  changes   TEXT,                     -- other entities: JSON object of the fields set.
                                      -- NULL for values, tags and deletes
  PRIMARY KEY (table_id, k1, k2, k3, commit_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX entity_log_commit ON entity_log(commit_id);              -- a commit's rows: undo
CREATE INDEX entity_log_tag    ON entity_log(k3) WHERE k3 > 0;        -- a tag's rows: tag undelete

CREATE TABLE sequence (id INTEGER NOT NULL) STRICT;   -- one row: the last sequence handed out (§7)
INSERT INTO sequence (id) VALUES (0);

-- User values, live rows only, on images, instances and subimages (no user file values,
-- note 03 §6). Property first in the key: one column = one contiguous range of one B-tree.
CREATE TABLE image_values (
  property_id INTEGER NOT NULL,       -- → properties.id
  image_id    INTEGER NOT NULL,       -- → images.id
  value       ANY NOT NULL,           -- native INTEGER | REAL | TEXT (§4). JSON only for a 'box' cell
  sequence    INTEGER NOT NULL,
  PRIMARY KEY (property_id, image_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX image_values_seq ON image_values(sequence);

CREATE TABLE instance_values (
  property_id INTEGER NOT NULL,
  instance_id INTEGER NOT NULL,       -- → instances.id
  value       ANY NOT NULL,
  sequence    INTEGER NOT NULL,
  PRIMARY KEY (property_id, instance_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX instance_values_seq ON instance_values(sequence);

CREATE TABLE subimage_values (
  property_id INTEGER NOT NULL,
  subimage_id INTEGER NOT NULL,       -- → subimages.id
  value       ANY NOT NULL,
  sequence    INTEGER NOT NULL,
  PRIMARY KEY (property_id, subimage_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX subimage_values_seq ON subimage_values(sequence);

-- tag and multi_tags: one row per (entity, tag), property first. See §8 Q5 for `tag`.
CREATE TABLE image_tag_values (
  property_id INTEGER NOT NULL,
  image_id    INTEGER NOT NULL,       -- → images.id
  tag_id      INTEGER NOT NULL,       -- → tags.id
  sequence    INTEGER NOT NULL,
  PRIMARY KEY (property_id, image_id, tag_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX image_tag_values_tag ON image_tag_values(tag_id);   -- tag delete only
CREATE INDEX image_tag_values_seq ON image_tag_values(sequence);

CREATE TABLE instance_tag_values (
  property_id INTEGER NOT NULL,
  instance_id INTEGER NOT NULL,
  tag_id      INTEGER NOT NULL,
  sequence    INTEGER NOT NULL,
  PRIMARY KEY (property_id, instance_id, tag_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX instance_tag_values_tag ON instance_tag_values(tag_id);
CREATE INDEX instance_tag_values_seq ON instance_tag_values(sequence);

CREATE TABLE subimage_tag_values (
  property_id INTEGER NOT NULL,
  subimage_id INTEGER NOT NULL,
  tag_id      INTEGER NOT NULL,
  sequence    INTEGER NOT NULL,
  PRIMARY KEY (property_id, subimage_id, tag_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX subimage_tag_values_tag ON subimage_tag_values(tag_id);
CREATE INDEX subimage_tag_values_seq ON subimage_tag_values(sequence);

-- Deletions, for delta sync only. `table_id` names the source table and k1..k3 hold its key
-- (ids and key order in §3, table ids). A key can appear more than once (deleted, set again,
-- deleted again), so no primary key. Deleted at project open and below the store's
-- sequence (§2).
CREATE TABLE tombstones (
  table_id INTEGER NOT NULL, k1 INTEGER NOT NULL,
  k2 INTEGER NOT NULL DEFAULT 0, k3 INTEGER NOT NULL DEFAULT 0,   -- 0: not part of the key
  sequence INTEGER NOT NULL
) STRICT;
CREATE INDEX tombstones_seq ON tombstones(sequence);
```

### Notes on the schema

- **Images.** Width, height, format and EXIF are image system values in `image_values` (with a
  `system_key` property), not columns of `images` or `files`. `hash` is binary: scripts read
  it with `hex(hash)`.
- **Files.** A missing file keeps its row: it holds the link to the image, the last path for
  *Relink…*, and the id that selections and instance hints use. A file is missing when its own
  `status` is 1 or when any parent folder's is. A missing folder is one row write, not one per
  file.
- **Folders.** Each source has exactly one root folder (`parent` NULL, `name` `''`), enforced by
  `folders_root`. `folders_location` cannot enforce it, since SQLite treats NULL parents as
  distinct.
- **Instances.** `image_id` is what the engine loads as the instance → image map, in one scan
  of `instances`. `file_id` is only a hint and is not followed to find the image. An instance
  with no file keeps its image.
- **Coordinates.** Subimage boxes and `box` cells use coordinates in 0..1, in the frame shown on
  screen (after EXIF rotation). Every writer must quantize them to 1e-4 with one formula,
  computed in double precision: `q(x) = round_half_even(x × 10000) / 10000`. In Python that is
  `round(x * 10000) / 10000`, in Rust `(x * 10000.0).round_ties_even() / 10000.0`. Both give
  the same double, which the subimage identity needs (an equal box must be an equal key). A
  coordinate outside 0..1, or a box with `x0 > x1` or `y0 > y1`, is refused. See §8 Q3 for
  storing integers instead.
- **Subimages.** A subimage is a fixed rectangle of an image that is an entity of its own:
  it has values, tags and vectors. Every subimage belongs to a namespace, a property with
  `dtype = 'namespace'`. Each algorithm, annotation import or cut (below) writes its own
  namespace, so subimages from different sources never mix: two namespaces can be compared, and
  one deleted or renamed without touching the other. Two namespaces finding the same box give
  two rows, each with its own values and vectors. A subimage's identity is (namespace, image,
  quantized rectangle), and its geometry never changes once written. A re-run that finds the
  same box upserts the same row and keeps its values.
  - Subimages hang off the image, not the file: copies of a photo share their subimages, and a
    move does not touch them.
  - No thumbnails are stored for subimages. The front crops the image's thumbnail, and a large
    preview crops the original on demand. Subimage vectors live in `media.db`, keyed by
    subimage id.
  - Subimage ids are their own id space. Instances point to images only, never to subimages.
  - `mode = 'subimage'` properties hold subimage values. With `namespace_id` set, the property
    belongs to that namespace (a detector's confidence or class) and is deleted with it. With
    it NULL, it applies to the subimages of any namespace (a person name, "false positive").
  - The namespace's value on an image is the list of its subimages, read from `subimages`,
    not stored. Image-side totals over subimages (count, union of their tags per namespace)
    are derived columns in the engine, never copied into image values: a tag set on the image
    and a tag reached through one of its faces stay distinct.
  - Subimages are written through commits and logged in `entity_log` (table ids 15, 6, 7), so
    a detector run or a namespace deletion can be undone. On a content change, subimages stay
    on the old image (note 04 §5.3). Purging an image deletes its subimages.
- **Boxes.** A `box` property (`mode` `image` or `instance`) holds rectangles that the user
  draws, moves and deletes, each with a name and a color. Its cell in `image_values` or
  `instance_values` is the whole list, as JSON text:
  `[[x0,y0,x1,y1,"name",color],…]`.
  - Coordinates follow the coordinate rule above. `color` is an INTEGER, as for the `color`
    type. `name` is free text and may be `""`.
  - An empty list is no row, like any missing value.
  - A box cell is always written whole: moving one box rewrites the cell. Its writes, history
    (`table_id` 1 or 2, with the JSON text in `value`), undo and tombstones are those of any
    value. There is no box id and no box table.
  - The backend and the plugin API must check the shape on every write: an array of 6-element
    arrays, four numbers by the coordinate rule, a string, an integer. A cell of another shape
    is refused, not stored. A cell written by an outside writer that does not parse is "no
    value" at load, with a warning (note 05 §3.2).
  - Boxes are not subimages. A box has no identity, no values of its own and no vectors,
    since its geometry changes with every edit. Names are free text, not tags.
  - JSON arrays, not objects or a binary blob: a blob loads 3× faster (§5) but scripts could
    not read it with plain SQL (§1, requirement 4). JSON arrays stay readable
    (`json_each(value)`) at under 300 ms for 2.5M boxes.
  - **Cut.** Cutting a box property into a namespace turns its boxes into subimages. Each box
    becomes a subimage of the box's image (for an instance box, the instance's image). Its
    name and color become values of a text property and a color property scoped to the
    namespace. The cut is a snapshot: editing the boxes later does not change the subimages.
    Cutting again upserts by subimage identity (namespace, image, box): an unchanged box finds
    its subimage, which keeps its values and vectors. A moved or new box gives a new subimage.
    A cut is one commit, so it can be undone. Open points: §8 Q6 and Q7.
- **History.** `entity_log` is the one record of which commit changed what: one row per entity
  a commit touched, with `op` and the changed fields. Result tables (every table with a
  `sequence` column except the observed state below) are its replay over active commits and
  carry no `commit_id`. A commit's changes are `WHERE commit_id = ?` (index
  `entity_log_commit`, which also covers the keys alone). An entity's commits are a range of
  the primary key, and its last one is the first active row in descending order. The logged
  entities, keyed with the table ids and key order of the tombstones:

  | entity | `table_id` | `k1`, `k2`, `k3` | logged in |
  |---|---:|---|---|
  | value | 1, 2, 6 | `property_id`, row id | `value`, native, as stored in the value table |
  | tag value | 4, 5, 7 | `property_id`, row id, `tag_id` | nothing: `op` 1 adds the row, 3 removes it |
  | instance | 10 | `id` | `changes`: `key`, `image_id`, `file_id` |
  | file | 11 | `id` | `changes`: `folder_id`, `image_id`, `name` |
  | folder | 12 | `id` | `changes`: `source_id`, `parent`, `name` |
  | file source | 13 | `id` | `changes`: `dtype`, `name`, `root_url`, `excludes`, `metadata` |
  | subimage | 15 | `id` (see §8 Q2) | `changes`: `image_id`, `namespace_id`, the box |
  | property, property group, tag, tag list | 20–23 | `id` | `changes`: every column but `sequence` |

  Unused key parts are 0, never NULL. A value row stores its value natively in `value`, not
  as JSON: values are 99% of the log, so this keeps the table small and makes an owner range
  read as fast as a column load (§5). `changes` is a JSON object only for the few multi-field
  entities. History compaction is not specified yet (§8 Q8).
- **Not logged.** `images` rows are content: created by scans, never changed, deleted only by
  a purge. Undoing a scan leaves its new image rows, which are orphans until purged.
  Observed state is not logged either (below).
- **Ids.** Id 0 is never used, so the engine can use 0 for "none" at every level (note 05 §2).
  Every id comes from `AUTOINCREMENT`. A writer that needs ids before it inserts (a client
  creating tags inside a commit, through the allocation routes of note 08 §2) reserves a range
  by §7 rule 4.
- **Observed and decided state.** `files.status`, `files.size`, `files.mtime`,
  `folders.status`, the `*_scan_id` columns, `scans` and `pending_changes` are written by scans
  and failed reads. They take a `sequence` like any write, so the engine sees them, but they
  have no `entity_log` entry and an undo never restores them (note 04 §6.3). Everything else is
  written through commits.
- **Deletes.** A deleted row takes the rows it owns with it (§3, table ids). There are two kinds
  of delete.
  - **Undoable:** properties (namespaces included), property groups, tags, tag lists,
    subimages, files (*Remove missing*, note 04 §6.2), folders and values. The delete is a
    commit. It logs the deleted row only, not the rows it owns. Undo re-inserts the row with
    its old id and re-resolves the rows it owns from `entity_log`, whose rows from the
    commits that wrote them are still active.
  - **Permanent:** images (purge, note 04 §6.6), instances and file sources. The delete writes
    no commit and no `entity_log` row. It deletes the row and the rows it owns, drops every
    `entity_log` row keyed by them, and sets `undoable = 0` on the commits those log rows
    belonged to and on the other commits of their `group_id`, which are undone as one. Such a
    commit can no longer be undone or redone, as a whole: there is no partial undo. The
    history shows it as such. Keeping that acceptable is the writer's job: the backend, and
    plugin authors, scope commits so that a permanent delete does not lock unrelated work
    (one import per commit, not an import mixed with other edits). A reference to a
    permanently deleted row resolves to NULL (an instance's `file_id` after its file source
    is deleted). Undoing the commit that created a row (an import's instances) is not a
    permanent delete: it is an undo like any other.
  - **Dead owners.** While a row is deleted by an undoable delete, or not created because the
    commit that created it is undone, re-resolution skips the rows it owns. Undoing an older
    commit that set a value of a deleted property writes nothing. The value comes back with
    the property, if its deletion is undone.
  - **Finding the owned rows in `entity_log`** (undo of a delete, drop of a permanent one):
    - a property is `k1`: one range of the primary key, `table_id = ? AND k1 = ?`, per value
      table;
    - an image, instance or subimage is `k2`: one short range, `table_id = ? AND k1 = ? AND
      k2 = ?`, per property of its mode;
    - a tag is `k3`: the partial index `entity_log_tag`. The query must repeat its condition,
      `WHERE k3 = ? AND k3 > 0`, or SQLite scans the whole table. The condition is `k3 > 0`
      and not `table_id IN (4, 5, 7)`: they select the same rows, but the `IN` form slows
      every insert, value rows included, by about 0.8 µs (§5);
    - the tags of a tag list and the properties of a namespace are found by reading the
      `table_id` 22 or 20 range and filtering on `changes`: both tables are small;
    - the subimages of a namespace have no indexed path yet: §8 Q2.

### Table ids

`table_id` names a table in `tombstones` and in `entity_log`, which store its key in k1..k3 in
the order below, with 0 for an unused part. The values are fixed constants, defined once in
the backend and in the plugin API. They are part of the file format: never renumber or reuse
one, only append. Gaps group the tables by kind. 0 and 3 are unused, so a missing value can't
pass for a real table.

| `table_id` | source table | k1 | k2 | k3 |
|---:|---|---|---|---|
| 1 | `instance_values` | `property_id` | `instance_id` | |
| 2 | `image_values` | `property_id` | `image_id` | |
| 4 | `instance_tag_values` | `property_id` | `instance_id` | `tag_id` |
| 5 | `image_tag_values` | `property_id` | `image_id` | `tag_id` |
| 6 | `subimage_values` | `property_id` | `subimage_id` | |
| 7 | `subimage_tag_values` | `property_id` | `subimage_id` | `tag_id` |
| 10 | `instances` | `id` | | |
| 11 | `files` | `id` | | |
| 12 | `folders` | `id` | | |
| 13 | `file_sources` | `id` | | |
| 14 | `images` | `id` | | |
| 15 | `subimages` | `id` | | |
| 20 | `properties` | `id` | | |
| 21 | `property_groups` | `id` | | |
| 22 | `tags` | `id` | | |
| 23 | `tag_lists` | `id` | | |

Not listed: `scans` and `pending_changes` (observed state, re-read whole), `commits`,
`entity_log` and `sequence` (not delta-synced). `images` (14) appears in `tombstones` only,
since image rows are not logged.

**One rule for owned rows: a row's tombstone stands for every row it owns.** The writer deletes
the owned rows in the same transaction, with no tombstone and no `entity_log` row of their own.
A reader that sees the tombstone drops the owned rows and cells it holds. Ownership is
transitive: a row owned by an owned row goes too.

| owner | owns |
|---|---|
| `images` (purge only) | its `image_values` and `image_tag_values` rows, its subimages |
| `instances` | its `instance_values` and `instance_tag_values` rows |
| `subimages` | its `subimage_values` and `subimage_tag_values` rows |
| `file_sources` | its `folders` and their `files` |
| `properties` | its value and tag rows. For a namespace, also its subimages and the properties scoped to it (`namespace_id`) |
| `tags` | its rows in the three tag tables |
| `tag_lists` | its tags |

A purge of 100k images with 20 properties writes 100k tombstones, not 2M. Deleting a
namespace of 1M subimages writes one. The undo cost of an undoable delete is in `entity_log`
(§5, history). Whether a delete can be undone is set per owner (§3, deletes).

Reading the deletes of one column since a reader's sequence:

```sql
SELECT k2 AS instance_id FROM tombstones
WHERE sequence > ? AND table_id = 1 AND k1 = ?;   -- k1 = property_id
```

A column load is then `SELECT instance_id, value FROM instance_values WHERE property_id = ?`:
a range scan with no filter. The reader must build the column straight from the row values,
without an intermediate value per cell: the bench measured a generic JSON value per cell at 2×
the cost (note 05 §5.2).

`WITHOUT ROWID` works best when rows are small. Long texts (descriptions) spill to overflow
pages either way, and `page_size=8192` keeps that rare.

## 4. Encoding per property type

The disk side is chosen so that each value decodes straight into the engine's column layout
(note 05 §3.6, the layout `bench/collection` measured). A writer must store exactly the SQLite
type of this table: `value` is `ANY`, so SQLite itself does not check it (note 05 §3.2 says
what a reader does with a wrong type).

| type | on disk (`value`) | engine column | notes |
|---|---|---|---|
| `number` | INTEGER or REAL, native | `f64` | already native today (NUMERIC affinity) |
| `checkbox` | INTEGER 0 / 1 | one byte | SQLite stores 0 and 1 in the row header, with no payload bytes |
| `date` | **INTEGER, unix ms** (meaning: §8 Q1) | `f64` ms, exact below 2^53 | removes the per-cell ISO parse |
| `color` | INTEGER | `f64` | |
| `text`, `url`, `path`, `image_link` | TEXT, raw UTF-8 | `u32` codes into a string dictionary | no JSON unquoting. Interning stays (150–200 ms at 1M distinct, `bench/collection` README, Load) |
| `tag`, `multi_tags` | `image_tag_values` / `instance_tag_values` / `subimage_tag_values` rows | CSR | property-first key. `tag` holds at most one row per cell (§8 Q5) |
| image id (system) | `image_id` INTEGER in `files` / `instances` / `subimages` / value tables | `u32` image id, used as the slot | the id comes from SQLite, so there is nothing to intern. Hex hashes only for the API, built on demand |
| `folder`, `id`, `size`, `mtime`, `created_at`, `status` | INTEGER in `files` / `instances` / `images` | integer columns | |
| file `name`, instance `key` | TEXT in `files` / `instances` | string dictionary | |
| `width`, `height` | INTEGER in `image_values` | `f64` | image system values, as `number` |
| `namespace` | rows of `subimages`, no value table | CSR image → subimage ids, per namespace | the namespace's column on images. Loaded from `subimages_box`: one namespace is one range |
| subimage box | four REAL in `subimages` | four `f32` | quantized by the writer (§3 notes) |
| `box` | TEXT, JSON array of `[x0,y0,x1,y1,"name",color]` | CSR row → boxes: four `f32`, name as a `u32` code into a string dictionary, color `u32` | the one JSON value, parsed at load (§5) |

## 5. Measured on the 1M bench db

Same synthetic data as `results/load/1000000/data.db`, rebuilt with the value tables above
(`page_size=8192`). The rebuild predates the image naming: it used a `sha1s` dictionary and
`sha1_*` value tables, with the same shape as `images` and `image_*`. The timings are for the
scan query alone, through the `sqlite3` CLI (`count`, `max(id)`, `max(value)` over the range),
so read the ratio rather than the absolute time. The Rust decode savings come on top of these.

| | rows | current | proposed |
|---|---:|---:|---:|
| text column (p1) | 920k | 96 ms | 68 ms |
| number column (p3) | 950k | 80 ms | 54 ms |
| date column (p5) | 950k | 91 ms | 56 ms |
| checkbox column (p6) | 900k | 86 ms | 52 ms |
| tags column (p7, the only tag property) | 2.49M | 186 ms | 151 ms |
| value tables + indexes on disk | | 356 MB | 181 MB |
| tag tables + indexes on disk | | 142 MB | 97 MB |

- Scalar scans are 30–40% faster and the tables are half the size.
- The bench has one tag property, so the current full-table scan reads only that property's
  rows anyway. With *k* tag properties, the current load reads *k* times more rows than it
  keeps. The proposed layout always reads just its own range.
- Expected end to end in the engine at 1M: date ≈ number (−45 ms from no parse), `base` down
  by the sha1 interning that integer image ids remove (≈150–200 ms of 276 ms). These are
  estimates from the load bench's breakdown. They must be re-measured once
  `bench/collection/load` reads this layout, before note 05 §5.4 uses them as targets.

The two benches below were scratch runs on 2026-11-16. They must be added to
`bench/collection` before implementation starts, so their numbers can be reproduced.

### Box encodings

1M image cells in `image_values` (the layout above), with 1–4 boxes each, 2.5M boxes in all.
There are 92k distinct names: mostly 50 class names, plus 10% unique names. Rust with
`rusqlite`, warm cache, median of 5. *Decode* builds the engine column: the CSR, four `f32`,
the color, and the name interned into a dictionary.

| encoding | value bytes | scan only | scan + decode |
|---|---:|---:|---:|
| JSON objects `{"x0":…,"name":…,"color":…}` | 211 MB | 48 ms | 404 ms |
| **JSON arrays `[x0,y0,x1,y1,"name",color]`** | **124 MB** | 52 ms | **284 ms** |
| binary blob (f32 ×4, u32, length + UTF-8) | 73 MB | 47 ms | 93 ms |

JSON arrays are the encoding (§3, boxes). The blob would be 3× faster and 40% smaller, at the
cost of a value that only the app and the plugin API can decode. A box column is loaded only
when a view draws it or an operator uses it, never at open unless asked.

### History

A synthetic history at 1M images: 9.0M log rows in 161k commits. It has four 1M-row value
imports, a 2.5M-row tag import, 1500 plugin commits of 667 rows, a 1M re-import, and 150k UI
commits of 1–5 rows on a skewed hot set, 5% of them undone. Rust with `rusqlite`, the settings
of §3, warm cache, median of 5, sizes from `dbstat` after `VACUUM`. *Undo* finds the commit's
keys through `entity_log_commit`, then resolves each entity.

| layout | size | 1M import | 2.5M tag import | undo of a 1M import | one property's rows (2M) | one tag's rows (top) |
|---|---:|---:|---:|---:|---:|---:|
| text key `[12,4051]`, JSON `changes`, `json_extract` tag index | 949 MB | 5.3 s | 18.0 s | 1.05 s | 646 ms | 49 ms |
| integer key, rowid table, JSON `changes` | 620 MB | 1.6 s | 5.0 s | 0.87 s | 588 ms | 43 ms |
| + `WITHOUT ROWID` + native `value` (tag index `IN (4,5,7)`) | 385 MB | 1.5 s | 4.9 s | 0.55 s | 119 ms | 67 ms |
| **§3: the same, tag index `k3 > 0`** | **385 MB** | **0.72 s** | **3.0 s** | **0.57 s** | **121 ms** | **69 ms** |

- From Python `sqlite3` (the plugin API), a 1M-row import takes 3.4 s with text keys and
  0.82 s with §3.
- The tag index condition alone halves import time. `table_id IN (4, 5, 7)` costs about
  0.8 µs on every insert, value rows included, while `k3 > 0` selects the same rows for
  nothing. Checked with the `sqlite3` CLI, 1M value rows: 0.57 s with `IN`, 0.35 s with
  `k3 > 0` and with no tag index at all. The cause was not looked into.
- Of the 385 MB, the table is 204 MB, `entity_log_commit` 139 MB (it holds the full key, as
  a secondary index of a `WITHOUT ROWID` table does) and `entity_log_tag` 42 MB.
- Small commits of 1–5 rows cost 80–105 µs in every layout: transaction overhead, not
  layout.
- Listing every row of one huge commit is slower without a rowid: 300 ms for 1M rows,
  against 92 ms. The undo path does not pay it, since it needs only the keys, which
  `entity_log_commit` covers.

## 6. Rejected options

- **Column snapshot cache.** The idea was to store each built column as a blob and read it on
  open instead of the value rows. Measured by `bench/collection/cache.sh` on cold files at 1M:
  a whole project open goes from 2.03 s to 636 ms. It is not used, for two reasons. The db gets
  opaque blobs that outside scripts and SQLite browsers cannot read. Any write, including an
  outside one, must also invalidate the cache, which needs triggers and version checks.
  Columns are always loaded from the value tables.

- **Other `entity_log` layouts.** Measured with the history bench (§5):
  - No tag index: 11% smaller and tag writes 1.6× faster, but a tag undelete scans every tag
    log row (50 ms at 3M, growing with the log). The index stays.
  - Tag index on `(table_id, k3)` for all rows: larger, and SQLite picks it for entity
    lookups, which doubles the undo time.
  - Tag index `WHERE table_id = 4 OR table_id = 5 OR table_id = 7`: inserts as fast as
    `k3 > 0`, but undoing a 1M import took 4.6 s instead of 0.57 s.
  - Primary key starting with `commit_id`, plus an entity index: listing a commit is 3×
    faster, but owner ranges and undo are 2× slower, for the same size.
  - `table_id` packed into `k1` (`k1 * 32 + table_id`): 5% smaller, 0–10% faster, but the key
    is no longer readable.
  - One `data ANY` column for both `value` and `changes`: 2% smaller, no faster, and the
    column then means two things.
  - No `entity_log_commit`: saves 36% of the log, but every undo starts with a full scan
    (150 ms at 9M rows, against 3 µs). A per-commit list of keys would replace it, but that is a
    derived copy (§1, requirement 4).

## 7. Reading and writing

Two writers exist: the backend, and plugins through the Python plugin API (note 09). Scripts
must only read: a script write that breaks these rules can be lost on the next undo. Both
writers follow the same rules, so the engine can catch up from any write by reading the changes
since its sequence.

### Writers

1. **One transaction, one sequence.** A write must open `BEGIN IMMEDIATE` (WAL lets readers go
   on), take `UPDATE sequence SET id = id + 1 RETURNING id`, and stamp every row it inserts or
   updates with that value. `sequence.id` is then the last sequence handed out. SQLite has one
   writer at a time, so sequences are in commit order.
2. **Decisions are commits.** Every write that the user may undo (values, tags, properties,
   subimages, imports, the decided part of a scan, report options, plugin results) must insert
   one `commits` row and one `entity_log` row per entity it changed, with the logged columns
   of §3. A value written without its log row is lost the next time an undo or redo
   re-resolves that entity. A large write may split into several commits of one `group_id`,
   undone as one.
3. **Every delete gets a tombstone** in the same transaction, except the rows its owner's
   tombstone stands for (§3, table ids).
4. **Ids come from `AUTOINCREMENT`.** A writer never picks an id itself, except an undo that
   re-inserts a row with its old id, and a range reserved in advance. A reservation is one
   write transaction: read the table's row in `sqlite_sequence` (insert it with the table's
   largest id, or 0, when it is missing), add *n*, and hand out the *n* ids above the old
   value. A reserved id that is never used is a hole, like a deleted id.
5. **Observed state** (§3 notes) is written without a commit, still with a sequence.
6. **Short transactions.** A writer holds the write lock only while it writes. A plugin builds
   its rows first and writes in batches (size: §8 Q4), so the backend's writes wait at most one
   batch. Every connection sets `busy_timeout` (§3, file settings).
7. **Undo and redo** belong to the backend: they flip `commits.active`, re-resolve the touched
   entities from `entity_log`, and write the result rows and tombstones under a new sequence.
   A new commit clears `redoable` on the undone ones of its author. A commit with
   `undoable = 0` is never flipped. Re-resolution skips the rows of a dead owner (§3,
   deletes).
8. **Permanent deletes** (§3, deletes) write no commit. In one transaction: the deletes and
   their tombstones, the drop of the `entity_log` rows keyed by the deleted rows, and
   `undoable = 0` on the commits those rows belonged to and on their groups.
9. **Typed values.** A writer must check each value against its property (§4, note 05 §3.2)
   before it writes, so a TEXT never lands in a number column.

### Readers

1. **One snapshot per catch-up.** The engine must read `sequence.id` and the changes in one
   read transaction. The version it builds then reflects the file exactly at that sequence
   (note 05 §2). Reading them in separate transactions could stamp a version with a sequence
   whose rows it did not read.
2. **Deletes before sets.** Within one window, a reader applies the tombstones first, then the
   rows. A cell deleted then set again is back in the value table, and the set must win. The
   same holds for rows: a deleted row that an undo re-inserts with its old id is alive again
   (ids are never reused, so it is the same row).
3. **Small tables whole.** `scans`, `pending_changes` and the schema tables are re-read whole
   when one of their rows is newer than the reader's sequence.
4. **Tombstone cleanup** belongs to the Project: at project open, and below the store's
   sequence while the backend runs (note 00 §5.2).

After a write, the engine catches up: at once for the backend's own writes, when the plugin
function returns for a plugin (note 05 §6.1), and through the one-second poll of `sequence.id`
for anything else. The Project's change follower decides when (note 00 §5.2).

## 8. Open questions

Each question gives the context, the options and a proposed answer. A question is closed by
editing the spec above and removing it here.

### Q1. What a `date` value means

**Context.** §4 stores a date as INTEGER unix ms, so a load does no parsing. That fixes the
encoding, not the meaning. Today the front treats dates as UTC wall-clock time: `DateInput`
shows and edits the UTC fields (`getUTCDate`, `getUTCMonth`), grouping buckets days, months
and years in UTC (`core/group/dateBuckets.ts`), and sorting and filtering compare `getTime()`.
The Python backend, on its side, writes `datetime.now()` (naive local time) for commit
timestamps. Once grouping moves to the backend engine, a day bucket needs a fixed rule, or two
clients in different time zones see different groups.

**Options.**

- (a) **Wall-clock time stored as if it were UTC.** "2024-05-03 14:00" is stored as the unix ms
  of 2024-05-03T14:00Z, whatever the user's zone. No time zone is applied anywhere: not in the
  engine, not in the front. It matches the front exactly. EXIF dates (local time with no zone)
  import as written. Two dates taken in different zones compare by their wall clocks, not by
  the true instant.
- (b) **True instants (UTC) plus a display zone.** Correct for comparing instants, but every
  day bucket, filter bound and display needs a zone. Imports without a zone have to guess one.
  Today's front behaviour changes.

**Proposed:** (a) for property values, written in §4 as "unix ms of the wall-clock time read as
UTC". `commits.timestamp` is a true instant in UTC ms, since it records when the write
happened, not a date the user typed.

### Q2. Finding a namespace's subimages in `entity_log`

**Context.** Deleting a namespace is undoable (§3, deletes). Its undo re-inserts the namespace
and must re-resolve its subimages from `entity_log`. A subimage is logged as `(15, id)`, with
its `namespace_id` inside the `changes` JSON, so the only way to find a namespace's subimages
is to read every subimage log row ever written and parse its JSON: at 1M subimages, a scan of
1M rows and 1M JSON parses for one undo, growing with every detector run. The same lookup is
needed to drop log rows when a namespace's subimages go with a purge. Tags of a tag list and
properties of a namespace have the same shape but are small tables, so a scan is fine there.

**Options.**

- (a) **Key a subimage by its namespace:** `(15, namespace_id, id)`, in `entity_log` and in
  `tombstones`. The subimages of a namespace become one range of the primary key, like the
  values of a property. Same size, same insert cost. A purge, which knows each subimage's
  namespace from the live row before it deletes it, still finds them.
- (b) Keep `(15, id)` and add a partial index on `json_extract(changes, '$.namespace_id')`
  for table 15. More bytes, an expression evaluated on every insert, and a key that hides one
  of its parts in JSON.
- (c) Make namespace deletion permanent. Simple, but a detector run that went wrong could not
  be undone, against the goal stated in §3 (subimages).

**Proposed:** (a). Nothing is implemented yet, so changing the key of table 15 costs nothing.
The subimage row of the table ids would read `15 | subimages | namespace_id | id |`.

### Q3. Coordinates as REAL or as integers

**Context.** A subimage's identity includes its four coordinates (`subimages_box`). With REAL
columns, identity holds only if every writer produces the exact same double for the same box.
§3 now fixes one quantization formula (`q(x)`, ties to even) so the backend and the plugin API
agree, but any writer that rounds differently (another language, a script that ignores the
rule) silently creates duplicate subimages instead of finding the existing one.

**Options.**

- (a) **REAL with the fixed formula** (the current text). Readable as-is in SQL. Identity
  depends on every writer applying `q` exactly.
- (b) **INTEGER in 1/10000 units** (0..10000). Equality is exact by construction, rows are
  smaller (SQLite stores small integers in 2 bytes, a REAL in 8: about 24 MB less per 1M
  subimages), and scripts read `x0 / 10000.0`. `box` cells would use the same units in their
  JSON, for one rule everywhere.

**Proposed:** (b), if the readability cost (`/ 10000.0` in scripts) is acceptable. Otherwise
keep (a) and have the plugin API refuse coordinates that are not already `q(x)`.

### Q4. Batch size for plugin writes

**Context.** SQLite has one writer. While a plugin writes a batch, a user edit from the UI waits
for the lock (§7, rule 6). Larger batches make a big import faster overall, since each
transaction costs 80–105 µs on top of its rows (§5, history). Smaller batches keep the UI
responsive. From Python, a 1M-row import with its log takes 0.82 s (§5), about 0.8 µs per row,
so 50k rows hold the lock for about 40 ms. Note 00 §10 asks the same question for a `disk` task
running next to a plugin, and note 09 §6 points here.

**Options.** A fixed row count per batch, or a time budget per batch (the plugin API commits
when a batch has held the lock for *t* ms).

**Proposed:** a time budget of 50 ms per batch, which the API can keep on any machine, with
every batch one commit of the call's `group_id` (note 09 §5.3). To be confirmed by a measurement:
the latency of a one-cell UI write while a plugin imports 1M rows, for a few budgets.

### Q5. A single `tag` cell can end up with two tags

**Context.** A `tag` property holds at most one tag per cell, but it is stored like
`multi_tags`: one row per (cell, tag), each row its own entity in `entity_log`. Setting a new
tag logs the removal of the old tag and the addition of the new one. With undo per author, out
of order (§7, rule 7), the rows can resolve independently into two live tags:

1. A sets X (commit 1: add X).
2. B sets Y (commit 2: remove X, add Y).
3. A sets Z (commit 3: remove Y, add Z).
4. B undoes commit 2. X resolves to commit 1 (alive), Y to commit 3 (removed), Z stays alive.
   The cell now holds X and Z.

Today's Python backend handles this at resolution time: it resolves each single-tag cell as a
whole and keeps the tag of the newest active commit (tag id breaks ties). §3 and §7 say nothing
about it, so a new implementation would get it wrong.

**Options.**

- (a) **Store `tag` as a scalar value:** the `tag_id` INTEGER in `image_values` /
  `instance_values` / `subimage_values`, logged as a value (table ids 1, 2, 6). The cell is then
  one entity and resolves like any value, with no special case. Deleting a tag reads the
  property ranges of the properties using its tag list (`WHERE value = ?` inside the range), and
  undeleting it reads their `entity_log` ranges: both are bounded by those properties' sizes,
  not indexed by tag. The engine still builds a CSR, so its load path is unchanged. Changing a
  property between `tag` and `multi_tags` moves its rows between tables.
- (b) **Keep rows, add a cell rule to resolution**, as today: after re-resolving tag rows of a
  `tag` property, re-resolve the whole cell and keep only the tag of the newest active commit.
  The resolver and every writer that resolves (backend only, since undo is backend-only) carry
  the special case.

**Proposed:** (a). It removes a correctness rule that every future resolver must remember, at
the cost of slower tag deletes on `tag` properties, which are rare.

### Q6. Cutting boxes again after boxes moved or were deleted

**Context.** A cut is a snapshot (§3, boxes). Cutting again finds unchanged boxes by identity,
and moved or new boxes give new subimages. A box that was moved or deleted since the last cut
leaves its old subimage behind, with the values and vectors it got since.

**Options.**

- (a) **Keep it**, and list such subimages in the cut's report, with an action to remove them
  (one undoable commit).
- (b) **Delete it** as part of the cut. The namespace then mirrors the boxes, but values set on
  the old subimage (a name, a "false positive" flag) are lost, unless the user undoes the cut.
- (c) Ask at each cut.

**Proposed:** (a). It never loses work silently, and the report keeps the namespace clean on
request.

### Q7. Cutting an instance box property: two instances, one box

**Context.** Subimages hang off images. Two instances of the same image (two samples of one
picture) that hold the same box map to one subimage identity (namespace, image, box), so the
cut merges them into one subimage. Their names or colors may differ, and the scoped text and
color properties hold one value per subimage.

**Options.**

- (a) **Merge on purpose.** The name and color come from the instance with the smallest id; the
  cut report lists the conflicts.
- (b) **Keep them apart** by adding the instance to the subimage identity. This breaks "subimages
  hang off the image" (note 03): vectors and overlays would no longer be shared by copies.
- (c) Refuse to cut an instance box property into a namespace where conflicts exist.

**Proposed:** (a). A subimage describes a region of the picture, so two equal boxes are one
region. Different names on it are a conflict in the data, which the report shows.

### Q8. History compaction

**Context.** `entity_log` grows with every commit: 385 MB at 9M rows in the history bench (§5),
and it is the largest part of the file. Note 00 §5.1 and the `/compact` route (note 08 §2) name
a compact operation, but no note defines it. Today's Python backend folds every commit up to a
horizon into a synthetic commit 0 (one snapshot row per live entity), deletes the folded commits,
and requires the horizon to stay behind every user's oldest undoable commit. In this layout,
`commit_id` refers to `commits.id`, which starts at 1, and `commits` has no row 0.

**Options.**

- (a) **Today's rule, ported:** a reserved `commit_id` 0 for the baseline (always active, never
  shown, no `commits` row), one `op` 1 row per live entity at the horizon, the folded commits
  deleted. Dead entities at the horizon lose their log rows, so their undo history goes.
- (b) **No compaction**, only the permanent deletes of §3 shrinking the log. The file keeps
  growing with edits.

**Proposed:** (a), specified here (the horizon rule, the effect on `undoable` and on
`group_id`, and which owner rules apply) before implementation. It bounds both the file size
and the length of the undo history, which note 04 §8 already ties to auto-purge.

### Smaller points

- **The author's last commit.** Undo looks for the author's newest active, undoable commit.
  Without an index, that is a backward scan of `commits` that grows when the author has been
  inactive for a long time. An index `commits(author, id)` costs a few MB at 1M commits.
  Proposed: add it if the history bench shows the scan above 1 ms.
- **Deleting a folder.** Folders are an undoable delete (§3, deletes), but the owner table does
  not list them, so a folder delete must tombstone and log each of its subfolders and files.
  Making folders owners would write one tombstone instead, but its undo would then need the
  files of a folder from `entity_log`, where `folder_id` is inside `changes`: the problem of Q2,
  on a table that can be large. Proposed: keep per-row deletes for folders, since a user rarely
  deletes a folder from the project (*Remove from project* goes through `excludes`, note 04).

### Decided or tracked elsewhere

- The periodic poll is decided by note 00 §5.2 (one second, for scripts and plugins outside a
  call). Whether it should use `PRAGMA data_version` is note 00 §10.
- Instance key type (text, or text plus an integer column): note 03 §11.
- How many `scans` rows to keep, and `file_sources.excludes` as JSON or as a table: note 04 §8.
