# 03: SQLite layout for the backend engine

Status 2026-10-29: proposal, nothing changed on disk. §3 is the full `data.db` schema and the
one source of truth for it: notes [05-elements.md](05-elements.md) (images, files, instances)
and [06-moves-and-deletions.md](06-moves-and-deletions.md) (rescans, missing files) describe the
model and the behaviour, and refer here for tables and columns. Builds on
[01-collection-manager.md](01-collection-manager.md) §5.1. Numbers come from the
`bench/collection` load bench (`results/load/report-1000000.md`), from a copy of its 1M
`data.db` rebuilt in the value layout below (timed with the `sqlite3` CLI, warm cache, median
of 5), and from the real project `~/panoptic-projects/express` (150k images, 457 MB `data.db`).

## 1. Goal

`data.db` is the project's source of truth on disk. The db is a store, not a query engine. Its interface is four operations:

1. **Load a property column.** On open, and when a column is first needed, read all values of
   one property and build the engine's typed column (note 04 §3.6). This is the hot read path.
2. **Write values.** User edits, imports and plugin results: from one cell to a whole column
   in one transaction. Each write gets a `sequence` and an `entity_log` entry for history and
   undo.
3. **Read changes since a `sequence`.** A reader that is behind (the engine after a plugin
   wrote, a plugin process) asks for the values, deletes and schema changes
   newer than its last `sequence`, without reloading whole columns.
4. **Stay readable from outside.** Plugins and scripts read and write the file with plain
   SQL. Every value is in a typed column of a documented table: no opaque blobs, no state that
   only the app can decode, no derived copy that a direct write would leave stale.

The layout is chosen for these four operations, not for ad-hoc queries.

## 2. Performance points

What each operation of §1 costs, and how the layout handles it. Numbers are at 1M instances
from `bench/collection`.

### Column load

The cost is the bytes read from disk plus the work per row. A cold open (file not in the OS
cache) costs about twice a warm one: 1.60 s against 782 ms for the 7 bench columns
(`results/cache/report-1000000.md`).

- **Read only the property's rows, in one pass.** The key starts with `property_id`, so one
  column is one contiguous range of one B-tree. Tables are `WITHOUT ROWID`: the row is
  stored in the key's B-tree, so a load is one sequential read, with no second lookup per row
  into a rowid table.
- **No decode per cell.** Values are stored as native SQLite types that map straight to the
  engine's column (§4): numbers as INTEGER / REAL, dates as unix ms INTEGER, checkboxes as
  0 / 1, text as raw UTF-8. No JSON text to unquote, no ISO date to parse (a parsed date
  column loads in 129 ms against 85 ms for a number column).
- **Small rows.** The disk read scales with table size, so every row byte counts on a cold
  open. Images are referred to by an integer `image_id` into `images`, not by the
  40-character hex sha1 string of today's format. That also removes today's sha1 interning,
  which is most of the identity load (276 ms).
- **Live rows only.** Deleted values are removed from the value tables (their record goes to
  `tombstones`), so a load reads no dead rows and filters nothing.

### Writes

The cost is one B-tree update per table and per index, plus the `entity_log` entry.

- **Few indexes.** Each value table has its key and a `sequence` index. Tag tables also have
  a `tag_id` index, used only to delete a tag. No index on a column that every row shares
  (like an `operation` flag), and no index that repeats a primary key.
- **Batches in one transaction.** WAL with `synchronous=NORMAL`: a commit appends to the WAL
  without an fsync per write.
- **History is the largest cost.** `entity_log` and its indexes are 244 MB of the 457 MB of
  express. Its key encoding is the main lever (§6).

### Changes since a sequence

The cost must scale with the number of changes, not with the table.

- Every value table and every large structural table (`images`, `files`, `instances`,
  `folders`) has an index on `sequence`, so "what changed since S" is a range read. The other
  tables are small and read whole.
- Deletes are read from `tombstones` (indexed by `sequence`), since a deleted row is gone from
  its table. The table is pruned once every reader is past a sequence (§8).

### Outside access

Not a speed cost, but it limits the options above. Tables are `STRICT` with typed columns, and
every speed-up must keep the data readable and writable with plain SQL. Derived copies that
a direct write would leave stale are out, which is why the column cache in §6 is rejected.

## 3. Proposed schema

```sql
PRAGMA journal_mode=WAL;  PRAGMA synchronous=NORMAL;
PRAGMA page_size=8192;    PRAGMA mmap_size=1073741824;  PRAGMA temp_store=MEMORY;

-- Identity: image (content), file (location), instance (sample). Note 05.
-- AUTOINCREMENT on the three: an id is never reused, so it is the engine slot.

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
  status INTEGER NOT NULL,            -- 0 present, 1 missing. Also missing if a parent folder is
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
CREATE INDEX folders_seq ON folders(sequence);

-- Scan results (note 06). Observed state: sequenced, not in entity_log, never tombstoned.
-- Small: a reader re-reads both whole when one has a row newer than its sequence.
CREATE TABLE scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  folder_id INTEGER,                  -- scope. NULL: the whole source
  mode INTEGER NOT NULL,              -- 0 rescan folders, 1 rescan files, 2 failed read
  started_at INTEGER NOT NULL,        -- unix ms
  finished_at INTEGER,                -- unix ms. NULL: running or interrupted
  new_count INTEGER, missing_count INTEGER, changed_count INTEGER, back_count INTEGER,
  sequence INTEGER NOT NULL
) STRICT;

-- Changed files (same location, new hash) waiting for a choice. Rebuilt for its scope by each
-- rescan of files, which writes a `scans` row in the same transaction.
CREATE TABLE pending_changes (
  id INTEGER PRIMARY KEY,
  scan_id INTEGER NOT NULL,           -- → scans.id
  file_id INTEGER NOT NULL,           -- → files.id, already pointing to the new image
  old_image_id INTEGER NOT NULL,      -- → images.id, the image before the change
  decision INTEGER,                   -- NULL open, 0 values follow, 1 new picture
  sequence INTEGER NOT NULL
) STRICT;

-- Schema: small tables, minus today's `operation` column (deletions go to `tombstones`).
CREATE TABLE property_groups (
  id INTEGER PRIMARY KEY, name TEXT, commit_id INTEGER, sequence INTEGER NOT NULL
) STRICT;

CREATE TABLE properties (
  id INTEGER PRIMARY KEY, dtype TEXT,
  mode TEXT,                          -- 'image' or 'instance' (today: 'sha1', 'id', 'file')
  name TEXT, access TEXT,
  tag_list_id INTEGER, system_key TEXT, property_group_id INTEGER,
  commit_id INTEGER, sequence INTEGER NOT NULL
) STRICT;

CREATE TABLE tag_lists (
  id INTEGER PRIMARY KEY, name TEXT, sequence INTEGER NOT NULL
) STRICT;

CREATE TABLE tags (
  id INTEGER PRIMARY KEY, list_id INTEGER, parents TEXT,   -- JSON array of tag ids
  value TEXT, color INTEGER, commit_id INTEGER, sequence INTEGER NOT NULL
) STRICT;

-- Versioning (see §6 for entity_log options) and the sequence counter.
CREATE TABLE commits (
  id INTEGER PRIMARY KEY, group_id INTEGER,
  source TEXT NOT NULL,               -- who wrote it. Rescans use scan, review, relink (06 §6.3)
  timestamp INTEGER NOT NULL,         -- unix ms (today: TIMESTAMP text)
  active INTEGER NOT NULL, author TEXT
) STRICT;

CREATE TABLE entity_log (
  entity_type TEXT NOT NULL, entity_key TEXT NOT NULL, commit_id INTEGER NOT NULL,
  op INTEGER NOT NULL, changes TEXT, sequence INTEGER,
  PRIMARY KEY (entity_type, entity_key, commit_id)
);
CREATE INDEX entity_log_commit ON entity_log(commit_id);   -- idx_entity_log_entity dropped

CREATE TABLE sequence (id INTEGER);

-- User values, live rows only, on images and instances (no user file values, note 05 §6).
-- Property first in the key: one column = one contiguous range of one B-tree.
CREATE TABLE image_values (
  property_id INTEGER NOT NULL,
  image_id    INTEGER NOT NULL,       -- → images.id (today: `sha1`, 40-char hex TEXT)
  value       ANY NOT NULL,           -- native INTEGER | REAL | TEXT, never JSON
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

-- tag and multi_tags: one row per (entity, tag), property first.
CREATE TABLE image_tag_values (
  property_id INTEGER NOT NULL,
  image_id    INTEGER NOT NULL,       -- → images.id (today: `sha1` TEXT, first in the key)
  tag_id      INTEGER NOT NULL,
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

-- Deletions, for delta sync only. `table_id` names the source table and k1..k3 hold its key
-- (ids and key order in the table below). A key can appear more than once (deleted, set
-- again, deleted again), so no primary key. Pruned once every reader is past their sequence.
CREATE TABLE tombstones (
  table_id INTEGER NOT NULL, k1 INTEGER NOT NULL, k2 INTEGER, k3 INTEGER,
  sequence INTEGER NOT NULL
) STRICT;
CREATE INDEX tombstones_seq ON tombstones(sequence);
```

### Notes on the schema

- **Images.** Width, height, format and EXIF are image system values in `image_values` (with a
  `system_key` property), not columns of `images` or `files`.
- **Files.** A missing file keeps its row: it holds the link to the image, the last path for
  *Relink…*, and the id that selections and instance hints use. A file is missing when its own
  `status` is 1 or when any parent folder's is. A missing folder is one row write, not one per
  file.
- **Instances.** `image_id` is what the engine loads as the instance → image map, in one scan
  of `instances`. `file_id` is only a hint and is not followed to find the image. An instance
  with no file keeps its image.
- **Ids.** Id 0 is never used, so the engine can use 0 for "none" at every level (05 §8).
- **Observed and decided state.** `files.status`, `folders.status`, the `*_scan_id` columns,
  `scans` and `pending_changes` are written by scans and failed reads. They take a `sequence`
  like any write, so delta readers see them, but they have no `entity_log` entry (06 §6.3).
  Everything else is written through commits.
- **What changed from today's columns.** `sha1` becomes `image_id`. `folders.path` is dropped
  (derived from the names). `file_sources.sync_status` is replaced by `scans`. `files.width`,
  `height`, `format` move to image values. `instances` gains `key` and `image_id`, and drops
  `sha1`. `file_values` is dropped.

### Tombstone table ids

`table_id` values are fixed constants, defined once in the backend (a Python `IntEnum`) and
mirrored in the engine. They are part of the file format: never renumber or reuse one, only
append. Gaps group the tables by kind. Nothing is frozen yet, but the rule is kept already:
renamed tables keep their id, 3 (the dropped `file_values`) stays retired, `images` is appended.

| `table_id` | source table | k1 | k2 | k3 |
|---:|---|---|---|---|
| 1 | `instance_values` | `property_id` | `instance_id` | |
| 2 | `image_values` (was `sha1_values`) | `property_id` | `image_id` | |
| 3 | retired (was `file_values`) | | | |
| 4 | `instance_tag_values` | `property_id` | `instance_id` | `tag_id` |
| 5 | `image_tag_values` (was `sha1_tag_values`) | `property_id` | `image_id` | `tag_id` |
| 10 | `instances` | `id` | | |
| 11 | `files` | `id` | | |
| 12 | `folders` | `id` | | |
| 13 | `file_sources` | `id` | | |
| 14 | `images` | `id` | | |
| 20 | `properties` | `id` | | |
| 21 | `property_groups` | `id` | | |
| 22 | `tags` | `id` | | |
| 23 | `tag_lists` | `id` | | |

0 is left unused, so a missing value can't pass for a real table. Not listed: `scans` and
`pending_changes` (observed state, re-read whole), `commits`, `entity_log` and `sequence`
(not delta-synced).

An `images` tombstone is only written by a purge (06 §6.2). It stands for the image and all
its values: the value rows are deleted with it but get no tombstone of their own, and a reader
drops every cell of that image. A purge of 100k images with 20 properties writes 100k rows,
not 2M.

Reading the deletes of one column since a reader's sequence:

```sql
SELECT k2 AS instance_id FROM tombstones
WHERE sequence > ? AND table_id = 1 AND k1 = ?;   -- k1 = property_id
```

Deletes are applied before the sets of the same window: a cell deleted then set again is
back in the value table, and the set must win. The same holds for rows: a deleted row that an
undo re-inserts with its old id is alive again (ids are never reused, so it is the same row).

A column load is then `SELECT instance_id, value FROM instance_values WHERE property_id = ?`:
a range scan with no filter, read through `ValueRef` without allocating.

`WITHOUT ROWID` works best when rows are small. Long texts (descriptions) spill to overflow
pages either way, and `page_size=8192` keeps that rare. Columns must still be built
directly from the rows (04 §5.2): the bench measured a generic JSON value per cell at 2× that.

## 4. Encoding per property type

The disk side is chosen so that each value decodes straight into the engine's column layout
(04 §3.6, the layout `bench/collection` measured).

| type | on disk (`value`) | engine column | notes |
|---|---|---|---|
| `number` | INTEGER or REAL, native | `f64` | already native today (NUMERIC affinity) |
| `checkbox` | INTEGER 0 / 1 | one byte | SQLite stores 0 and 1 in the row header, with no payload bytes |
| `date` | **INTEGER, unix ms UTC** | `f64` ms, exact below 2^53 | removes the per-cell ISO parse |
| `color` | INTEGER | `f64` | |
| `text`, `url`, `path`, `image_link` | TEXT, raw UTF-8 | `u32` codes into a string dictionary | no JSON unquoting. Interning stays (≈150 ms at 1M distinct, 04 §5.4) |
| `tag`, `multi_tags` | `image_tag_values` / `instance_tag_values` rows | CSR | property-first key. A scalar `tag_id` column for `tag` would save little, since the engine holds both as CSR |
| image id (system) | `image_id` INTEGER in `files` / `instances` / value tables | `u32` image id, used as the slot | the id comes from SQLite, so there is nothing to intern. Hex hashes only for the API, built on demand |
| `folder`, `id`, `size`, `mtime`, `status` | INTEGER in `files` / `instances` / `images` | integer columns | |
| `width`, `height` | INTEGER in `image_values` | `f64` | image system values, as `number` |

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
  estimates from the load bench's breakdown. Re-measure once `bench/collection/load` can read
  this layout.

## 6. Options not in the default

- **Column snapshot cache: rejected.** The idea was to store each built column as a blob and
  read it on open instead of the value rows. Measured by `bench/collection/cache.sh` on cold
  files at 1M: a whole project open goes from 2.03 s to 636 ms. It is not used, for two
  reasons. The db gets opaque blobs that outside scripts and SQLite browsers cannot read.
  Any write, including an outside one, must also invalidate the cache, which needs triggers
  and version checks. Columns are always loaded from the value tables.

- **`entity_log` keys as integers**: today `entity_key` is a JSON text compared byte for
  byte, so every writer must reproduce CPython's `json.dumps` exactly. Typed columns `k1`, `k2`, `k3`,
  `entity_type` as a small INTEGER and `changes` as msgpack BLOB would make it smaller and
  drop that constraint. `entity_log` and its indexes are 244 MB of the 457 MB of express.

## 7. Compatibility

[`PLAN.md`](../technical_docs/rust_port/PLAN.md) goal 4 says the on-disk format stays
byte-compatible with the Python backend. Sections 3–4 break that, so they need:

- a data.db v3 migration, in Python, in `panoptic.migration` (legacy projects already go
  through it). Besides the value encoding, it builds `images` from today's sha1s, gives each
  instance a key and an `image_id`, fills `files.size` and `mtime` with one `stat` per file
  (a file not found is missing), turns folder paths into names and parents, and moves
  `file`-mode properties to image or instance values (§8);
- the plugin SDK's read and write helpers (P1-D) written against v3 from the start.

Do it before P1-A (`panoptic-db`) and P1-D freeze the format. Once plugins read the files
directly, every layout change is a migration they must follow too.

Possible today without breaking the format:

1. drop `idx_entity_log_entity` (the primary key already covers it);
2. drop the `operation` indexes on the value and tag tables;
3. put `property_id` first in today's `instance_tag_values` / `sha1_tag_values` key. The
   Python code addresses these rows by column name, so only the `CREATE TABLE` and a table
   rebuild change. Check `entity_schema.py` before relying on that.

## 8. Open questions

- `commit_id` on value rows: the resolver writes it (`resolver.py:150`) and the schema dropped
  it above. `data_reader.py`, `project.py` and `project_routes.py` mention `commit_id`. Check
  whether any of them reads it from value rows before dropping it.
- Dates: unix ms UTC, or a naive local time as the Python backend writes `TIMESTAMP` columns?
  The front compares `getTime()`, which is UTC ms.
- Tombstone pruning: what sequence is "every reader is past it", given plugin processes that
  poll on their own?
- v3 migration of today's data. Every file has an instance today, while a folder import
  creates none in note 05. Keep them all (key = today's id), or only those with instance
  values? And `file`-mode values: to image values when every file of an image agrees, with a
  report of the conflicts, as an import does (05 §6)?
