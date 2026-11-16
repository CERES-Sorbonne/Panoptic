# 05: The column store

Status 2026-11-06: specification, no implementation. Sources: the `data.db` layout of
[01-sqlite-layout.md](01-sqlite-layout.md), the front's `columnStore` / `dataStore`
(`panoptic_front/src/data/stores`) as the reference behaviour, and the `bench/collection`
measurements. The levels and row kinds are those of [03-elements.md](03-elements.md). Builds on
[06-collection-manager.md](06-collection-manager.md) and [07-slice-sending.md](07-slice-sending.md).

## 1. Role

The column store holds, in memory and per open project, the values that the collection engine
filters, sorts and groups on. It has three jobs:

1. **Load** the identity of images, files, instances and subimages, and the property values, from
   `data.db`.
2. **Update** them when `data.db` changes, whoever wrote the change.
3. **Notify** the engine of what changed, precisely enough for each collection to decide whether
   it has to recompute.

One store per project, shared by every collection of that project.

Out of scope: selection (per user session, note 07 §7.2), group trees, results, and anything a
collection computes. Thumbnails and media. Writing to `data.db`: the store only reads it.

## 2. Terms

- **Level**: image, file, instance or subimage (note 03 §1, note 01 §3). Each level has its own id
  space and its own columns.
- **Row kind**: the level a collection shows as rows: image, file or instance (note 03 §7).
  Subimages are a level for values but not a row kind yet (§10).
- **Slot**: the position of a row in the columns of its level. A slot is the row's id, so a
  column is indexed by id and cell 0 is "no value" (ids start at 1, note 01 §3). Ids are never
  reused, so a slot never denotes another row. Deleted ids leave holes. When the holes of a
  level pass a threshold (25% of its max id, note 04 §6.5), the next full reload (§6.5) maps
  ids to dense slots, in memory only.
- **Property mode**: the level a property's values live on. `image` → `image_values`,
  `instance` → `instance_values`, `subimage` → `subimage_values`. Tag properties use the matching
  `*_tag_values` table. Files carry system properties only.
- **Column**: the values of one property for every slot of its level.
- **Sequence**: the `data.db` write clock. Every write transaction takes the next sequence
  (note 01 §7), and every sequenced row carries the sequence of the write that last touched it.
- **Version**: one state of the store. Each version reflects `data.db` exactly up to one sequence.

## 3. What the store holds

### 3.1 Identity

| level | per id | from |
|---|---|---|
| image | alive or not | `images` |
| file | image, folder, alive or not | `files` |
| instance | image, file (a hint), alive or not | `instances` |
| subimage | image, namespace, alive or not | `subimages` |

These links are the row spaces of note 03 §8: a column at the image level is read from a file
or instance row through its image id. The reverse lookups (image → files, image → instances,
image → subimages, folder → files) are built when an operator needs them and cost the size of their
answer, not a scan of every slot.

### 3.2 Value domain per property type

The values the store gives to the engine must be the values the front reads today, so that the
golden tests of note 06 §6 hold. Values are stored natively (note 01 §4), so a load does no
parsing, except for `box`:

| property type | stored | value | "no value" |
|---|---|---|---|
| `number`, `color` | INTEGER or REAL | f64 | distinct from every number |
| `date` | INTEGER, unix ms UTC | f64 ms | same |
| `checkbox` | INTEGER 0 / 1 | true / false | distinct from false |
| `text`, `url`, `path`, `image_link` | TEXT | string | distinct from the empty string |
| `tag`, `multi_tags` | `*_tag_values` rows | list of tag ids | an empty list. The front treats `[]` and no value alike |
| `box` | TEXT, JSON array of `[x0,y0,x1,y1,"name",color]` (note 01 §3, boxes) | list of boxes: four f32, name, color | an empty list. The one type parsed at load |

A cell whose stored type does not match its property (TEXT in a number column, written by an
outside writer) is "no value" and counts as a load warning. It never fails a column. The same
holds for a `box` cell that does not parse.

### 3.3 System properties

They are columns like any other for the engine, but they are read from the identity tables or
derived:

| level | key | type | from |
|---|---|---|---|
| image | `hash` | text | `images.hash`, as hex |
| image | `size` | number | `images.size` |
| image | `width`, `height`, `format` | number / text | `image_values`, properties with a `system_key` (note 01 §3) |
| image | `files`, `missing files`, `instances` | number | derived (§3.4) |
| file | `folder` | folder | `files.folder_id` |
| file | `name`, `size` | text / number | `files` |
| file | `mtime`, `created_at` | date | `files` |
| file | `status` | present / missing | derived (§3.4) |
| file | `path` | path | derived (§3.4) |
| instance | `key` | text | `instances.key` |
| instance | `has file` | checkbox | derived (§3.4) |
| subimage | `namespace` | property id | `subimages.namespace_id` |
| subimage | box | four numbers | `subimages.x0 … y1` |

A file or instance row also reads every image column through its image (note 03 §8).

### 3.4 Derived columns

A derived column is computed from other columns and the schema, never read from `data.db`.
Requesting a derived column loads its inputs. It is recomputed whenever an input changes, and
its change is notified like any other.

| column | level | computed from |
|---|---|---|
| `path` | file | the folder's path (folder names up to the source's `root_url`) + `name` (today `dataStore.ts`, `_registerPathColumn`) |
| `status` | file | missing when its own `status` or any parent folder's is 1 (note 04 §4) |
| `files`, `missing files` | image | count of present / missing files per image |
| `instances` | image | count of instances per image |
| `has file` | instance | `file_id` set and that file present |
| subimage count, subimage tags | image | per namespace: the number of subimages, and the union of their tags (note 01 §3, subimages). Never copied into image values |
| box count, box names | image or instance, the box property's mode | per box property: the number of boxes, and the set of their names, for filters such as "has a box named cat" |

### 3.5 The schema

Properties (id, type, mode, namespace, system key), tags (id, list, parents), tag lists,
property groups, folders (id, source, parent, name, status) and file sources. The engine needs
it to interpret columns, to expand tag parents and to build paths, so it is versioned with the
columns: a version pairs the columns with the schema they were read under.

### 3.6 Layout

The `bench/collection` engine stores numbers and dates as `f64`, checkboxes as one byte,
strings dictionary-encoded (`u32` codes) with a lowercased dictionary built once, and tags as
CSR (offsets + flat ids). At 1M rows, 7 columns take 134 MB live (v8: 241 MB, JSC: 142 MB),
and all the filter, sort and group timings of note 06 §1 were measured on that layout. The store
must give the engine column access at least as direct as that: a typed slice per column, no
per-cell dispatch. Each level has its own columns, indexed by its slots.

## 4. Consistency

- **A computation reads one version.** From the start of a filter / sort / group to the end of
  the slices built on its result, every value comes from the same version (note 06 §3).
- **Readers never wait for writers, and writers never wait for readers.** A long
  computation on an old version does not delay an update, and an update does not stall a
  running computation.
- **Each version is exact at one sequence.** For a version at sequence `S`, every loaded column
  equals what a fresh load of `data.db` at `S` would give.
- **A column is complete or absent.** A property is either loaded for every slot of its level or
  not loaded at all. A change to a property that is not loaded never creates a partial column.
- **Versions are totally ordered** and their sequences never decrease, except across a full
  reload (§6.5), which is notified as one.
- An update to one property must not cost in proportion to the other properties (no copy of
  untouched columns).

## 5. Loading

### 5.1 Opening a project

Read in one read transaction, so that everything is at the same sequence `S`:

1. `S` = `sequence.id`, the last sequence handed out (note 01 §7);
2. the schema (§3.5);
3. the identity of every level (§3.1): `images`, `files`, `instances`, `subimages`, each ordered by
   `id`. The id order is the input order of every collection, and sort ties keep it, so it must
   be stated and not left to the query plan.

Then delete the tombstones (note 01 §2): the store is complete at `S` without them. No property
column is loaded at open. The first version is at `S`.

### 5.2 Loading columns on demand

`ensure(properties)` makes the given columns available and returns the first version that has
them all.

- Called by a collection before it computes (the properties of its filter, sort and grouping)
  and by a view for the properties it draws.
- **One load per column.** Concurrent requests for a column being loaded wait for that load.
- **Loads run in parallel** with each other, on their own read connections, on blocking
  threads, never on the async runtime that serves requests.
- **Columns requested together are published together**, in one version, so a collection opened
  at startup with 6 columns computes once and not 6 times.
- **Built directly from the rows** into the typed layout. The bench measured the path through a
  generic JSON value per cell at 2× the direct one (1.70 s against 916 ms for 7 columns at 1M).
- The reads, one range of one table each (note 01 §3):

| property | rows |
|---|---|
| `image` mode | `image_values WHERE property_id = ?` |
| `instance` mode | `instance_values WHERE property_id = ?` |
| `subimage` mode | `subimage_values WHERE property_id = ?` |
| tags | the matching `*_tag_values WHERE property_id = ?` |
| a namespace (`dtype = 'namespace'`) | `subimages WHERE namespace_id = ?`: its subimages, as image → subimage ids |
| system | the identity tables (§3.3) |

- Value tables hold live rows only, so a load filters nothing. A deleted property has no rows
  and no column.
- A tag column is read in key order, so each row's tags arrive together. The store must keep
  each row's tags whole. (The Python route today splits a row across two batches when a batch
  fills up, `bench/collection` README, Load.)

### 5.3 Loading while the db moves

A column is read at sequence `C`, while the store may have moved on to sequence `T`. Before the
column joins a version, it must be brought to that version's sequence:

- `C < T`: apply to the column the changes of its property in `(C, T]`;
- `C > T`: the store first catches up to at least `C` (§6.1), then the case above.

Test: writes landing between the read of a column and its publication must all be in the
published column (§9).

### 5.4 Targets

At 1M rows, warm OS cache. Measured by `bench/collection/load` on the Python backend's current
`data.db` format. Note 01 §5 measured the new layout's scans 30–40% faster, so these targets are
upper bounds:

| | target | measured by the bench |
|---|---:|---:|
| open (identity) | ≤ 300 ms | 276 ms, mostly sha1 interning that integer image ids remove |
| one scalar column (number, label, checkbox) | ≤ 100 ms | 84–98 ms |
| text, ~1M distinct values | ≤ 260 ms | 253 ms |
| date | ≤ 130 ms | 129 ms (≈ 85 ms with dates stored as integers, note 01) |
| tags, 2.5M rows | ≤ 200 ms | 182 ms |
| 7 columns | < 1 s | 916 ms |

SQLite alone is 65–70 ms of a scalar column. The rest is decoding and string interning. Note 01's
layout lowers both.

## 6. Updates

### 6.1 Sources, and one path for all of them

`data.db` changes through:

- the backend's writer: commits from the UI, imports, scans and report options (note 04);
- undo and redo, which enable or disable commits and re-resolve the rows they touched;
- plugins, which write `data.db` directly through the Python plugin API while the backend runs
  one of their functions (note 09);
- a script that writes despite note 01 §7 (scripts should only read).

All of them reach the store by one path: read the changes since the store's sequence, turn them
into store changes, publish one new version. The Project's change follower (note 00 §5.2)
triggers it: after each transaction, undo or redo of the writer; at the end of a plugin
function, since the backend called it; on a periodic poll of `sequence.id` for anything else. At most one catch-up runs at a time. A trigger during a
catch-up schedules exactly one more, so a burst of writes costs a few catch-ups and not one per
write. Our own writes are not applied to the store directly: one path keeps one order of
application.

A catch-up reads, for the window `(T, S]`: the tombstones, then the rows with a newer
`sequence` of every sequenced table (note 01 §2), in one read transaction.

`wait_for(sequence)` resolves once the store has a version at that sequence or later. A route
that writes and then reads (and the engine's `settle`, note 06 §4.2) uses it.

### 6.2 What a change does

| change in `data.db` | in the store |
|---|---|
| new image, file, instance or subimage | its slot becomes alive. A new file or instance shows the loaded image columns of its image at once |
| row deleted (tombstone) | the slot is marked dead, and so is every row the tombstone stands for: an image's subimages, an instance's or a property's cells (note 01, table ids) |
| row re-inserted with its old id (undo) | the slot is alive again: deletes apply before sets (§6.3) |
| file or instance re-pointed to another image | its image link changes; every image column it reads changes for that row |
| value written, loaded property | the cell of its row |
| value deleted (tombstone), loaded property | the cell becomes "no value" |
| tag rows, loaded property | the tag list of each touched (row, property), read again |
| any change to a property that is not loaded | nothing loaded. It is still reported (§7) |
| subimage written or deleted, namespace loaded | the image → subimages lists of its image, and the derived subimage columns |
| tag deleted | the tag id is removed from every loaded tag column |
| tag parents changed | columns unchanged, the schema changes (the engine's tag expansion depends on it) |
| folder renamed or moved | `path` is recomputed for its subtree |
| folder or file status changed | the file `status` column, and the image counts through it |
| property created | nothing to load. It can be known empty right away |
| property deleted (`properties` tombstone) | its column is dropped. For a namespace, its subimages and scoped properties go too |
| property type changed to another kind of value (text ↔ number ↔ tags), or mode changed | its column is dropped and loaded again on the next `ensure` |
| property type changed within a kind (number ↔ date) | values unchanged, the change is reported so the engine drops what it derived from them |

A write that sets a cell to the value it already has is not a change. Undo and redo re-resolve
rows and often rewrite identical values, and these must not make collections recompute.

### 6.3 Ordering and idempotency

- Inside one catch-up, tombstones are applied first, then new rows, then values. A cell or row
  deleted then set again in the window ends alive, and a value for a new row always finds its
  slot.
- A catch-up may deliver a row the store already has. Applying it again must change nothing.

### 6.4 Targets

To be set from measurements (§9), with these starting points at 1M rows:

- one edit from the UI: in a new version within 10 ms of the commit;
- 100 edits landing within 50 ms: at most 2 versions;
- a plugin writing one property for every row: in one version, in less time than loading
  that column from scratch.

### 6.5 Full reload

The store reloads from scratch (open + every column that was loaded) when:

- `sequence.id` is **below** the store's sequence: the file was replaced or restored;
- the project is opened again;
- the holes of a level pass the remap threshold (§2), at a quiet moment.

Slots may be renumbered. The reload is published as one version, flagged so that every
collection recomputes from scratch and anything holding slot-indexed data drops it.

## 7. Notifying

### 7.1 Content

Each new version comes with a change record:

| field | content |
|---|---|
| versions | the previous and the new version, and the new sequence |
| values | per property: the slots whose value really changed |
| links | per level: the file and instance slots whose image changed |
| added | per level: the slots that became alive |
| deleted | per level: the slots marked dead |
| loaded | the columns that became available |
| dropped | the columns removed or waiting for a reload |
| schema | the properties, tags, folders and sources that changed, by id and by kind of change (§6.2) |
| unloaded properties | the properties changed in `data.db` that have no column |
| reload | true for a full reload (§6.5): everything else is moot |

The changed slots are given per property, so that a collection grouping on property A can tell
that a change to property B does not concern it. A change to an image column also concerns the
file and instance rows of that image: the engine maps it through the row space. A record's size
grows with the number of changed cells, and stays within a few bits per slot even when every
slot of a column changes.

### 7.2 Delivery

- **One consumer**: the engine, which fans out to collections and views (note 07 §7.4). The web
  Project also turns the `schema` field into a `data.changed` event for the clients (note 00 §6).
- **In order, none lost.** Records are delivered in version order and never dropped or merged
  away. A collection that misses a record loses which slots changed. If the consumer falls
  behind, consecutive records may be merged into one, provided the merge keeps every changed
  slot.
- **Cheap for the store.** Delivering a record does not run the consumer's work. The store does
  not wait for collections.

### 7.3 What the engine does with it

Not part of the store, recalled here because it defines what the record must carry (note 07
§7.4): a collection whose filter, sort and grouping do not use any property of `values` sends a
`values` push to its views and does not recompute. One that uses them and is visible recomputes
incrementally from the changed slots (note 06 §5.4). One that is hidden is marked dirty. A
`reload` record makes every collection recompute from scratch.

### 7.4 Cache keys

The engine caches per column (sort keys, lowercased dictionaries, tag expansions, the inverted
tag index). Each column has its own change counter, bumped only when its values change, so a
cache stays valid across versions that do not touch its column.

## 8. Memory

- Versions no computation or result uses any more are freed.
- A column no collection or view has used for a while is unloaded, unless an open collection
  filters, sorts or groups on it. The next `ensure` loads it again.
- String dictionaries accumulate strings that no cell uses any more after edits. They are
  rebuilt when the unused share passes a threshold, which bumps the column's change counter
  (§7.4).
- The budget and the eviction order are those of note 07 §7.6.

## 9. Acceptance tests

1. **Load parity**: fixture projects written through the backend's writer (every property type
   and mode, every level, system and derived columns, deleted properties, duplicate images,
   missing files and folders, subimages) load into the values the fixture declares, slot for slot.
   The same fixture data loaded by the front's `columnStore` from today's format gives the same
   values, so the golden tests of note 06 §6 compare like with like.
2. **Replay**: after a random sequence of commits, undos, redos, scans, imports, deletes, tag
   and property deletes, purges and schema changes, the current version equals a fresh load at
   the same sequence. The most important test.
3. **Interleaving**: writes between the read of a column and its publication end up in the column
   (§5.3).
4. **No partial column**: a write to an unloaded property leaves it unloaded and is reported in
   `unloaded properties`.
5. **No-op writes**: undo then redo of a commit reports only the cells whose value changed.
6. **Notification**: every changed cell of the replay test appears in exactly the records of the
   versions that changed it, per property.
7. **Plugin writes**: a plugin writing through the plugin API while the backend writes too ends
   in the same version as a fresh load once the function returns.
8. **Performance**: the targets of §5.4 and §6.4, through `bench/collection/load` extended with
   updates: an edit on a 1M and a 10M column, a burst of 100 edits, a 1M-row plugin write.

## 10. Open questions

- Unload policy for columns: time, memory budget, or both?
- What may a single edit cost on a 10M column, given that readers keep older versions? Set the
  bound from the measurements of §9.8.
- Thresholds: the catch-up coalescing delay, the dictionary rebuild ratio, the remap share of
  holes, the encoding switch of changed slots between a list and a bitset.
- Subimages as a row kind: a view of one namespace (one tile per subimage, cropped from the
  image's thumbnail) needs subimage rows in the engine. The store already holds subimage
  columns; is the row kind wanted?
