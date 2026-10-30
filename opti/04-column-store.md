# 04: The column store

Status 2026-10-28: specification, no implementation. Sources: the `data.db` format written by
the Python backend, the front's `columnStore` / `dataStore` (`panoptic_front/src/data/stores`)
as the reference behaviour, and the `bench/collection` measurements. Builds on
[01-collection-manager.md](01-collection-manager.md) and [02-slice-sending.md](02-slice-sending.md).

## 1. Role

The column store holds, in memory and per open project, the values that the collection engine
filters, sorts and groups on. It has three jobs:

1. **Load** the instances and the property values from `data.db`.
2. **Update** them when `data.db` changes, whoever wrote the change.
3. **Notify** the engine of what changed, precisely enough for each collection to decide whether
   it has to recompute.

One store per project, shared by every collection of that project.

Out of scope: selection (per user session, note 02 §7.2), group trees, results, and anything a
collection computes. Thumbnails and media. Writing to `data.db`: the store only reads it.

## 2. Terms

- **Instance**: a row of `instances` (`id`, `sha1`, `file_id`). Several instances can share a sha1
  (duplicates) or a file.
- **Slot**: the dense position of an instance in the store, `0..n`. Columns are indexed by slot.
  A slot keeps denoting the same instance until a full reload (§6.5).
- **Property mode**: where a property's values live in `data.db`. `id` → `instance_values` (one
  value per instance), `sha1` → `sha1_values` (shared by every instance with that sha1), `file` →
  `file_values` (shared by every instance of that file). Tag properties use
  `instance_tag_values` / `sha1_tag_values`.
- **Column**: the values of one property for every slot.
- **Sequence**: the `data.db` write clock. Every write takes the next `sequence` id, and every
  sequenced row carries the sequence of the write that last touched it.
- **Version**: one state of the store. Each version reflects `data.db` exactly up to one sequence.

## 3. What the store holds

### 3.1 Instances

For each slot: instance id, sha1, file id, and whether the instance is deleted. Lookups needed by
the engine and the updates: instance id → slot, sha1 → slots, file id → slots. Each must cost the
size of its answer, not a scan of every slot.

### 3.2 Value domain per property type

The values the store gives to the engine must be the values the front reads today, so that the
golden tests of note 01 §6 hold:

| property type | value | "no value" |
|---|---|---|
| `number`, `color` | f64 | distinct from every number |
| `date` | epoch ms (UTC) as f64, from the stored ISO text | same |
| `checkbox` | true / false | distinct from false |
| `text`, `url`, `path`, `image_link` | string | distinct from the empty string |
| `tag`, `multi_tags` | list of tag ids, in stored order | an empty list. The front treats `[]` and no value alike |
| `folder` (system) | folder id | |

The conversions are the front's: a date text goes through `new Date(text).getTime()`, a number
through `Number(x)`, a checkbox through truthiness, a tag value that is not a list is "no value".
A cell that cannot be decoded is "no value" and counts as a load warning. It never fails a
column.

### 3.3 System properties

From `system_properties.py`. They are columns like any other for the engine, but they are read
from the structural tables:

| key | type | from |
|---|---|---|
| `id`, `sha1`, `file_id` | id / sha1 / number | `instances`, always present (they are the instances themselves) |
| `folder`, `format`, `width`, `height` | folder / text / number | `files`, through `file_id` |
| `name`, `created_at` | text / date | `files` |
| `path` | path | derived: the folder path prefix + `name` (§3.4) |

### 3.4 Derived columns

A derived column is computed from other columns and the schema, never read from `data.db`. Only
`path` today (`dataStore.ts`, `_registerPathColumn`): the path prefix of the folder (folders +
file sources) followed by the file name. Requesting a derived column loads its inputs. It is
recomputed whenever an input column or the folder tree changes, and its change is notified like
any other.

### 3.5 The schema

Properties (id, type, mode, system key, alive or not), tags (id, property, parents, alive or not)
and folders (id, parent, name, source). The engine needs it to interpret columns and to expand
tag parents, so it is versioned with the columns: a version pairs the columns with the schema
they were read under.

### 3.6 Layout

The `bench/collection` engine stores numbers and dates as `f64`, checkboxes as one byte,
strings dictionary-encoded (`u32` codes) with a lowercased dictionary built once, and tags as
CSR (offsets + flat ids). At 1M instances, 7 columns take 134 MB live (v8: 241 MB, JSC: 142 MB),
and all the filter, sort and group timings of note 01 §1 were measured on that layout. The store
must give the engine column access at least as direct as that: a typed slice per column, no
per-cell dispatch.

## 4. Consistency

- **A computation reads one version.** From the start of a filter / sort / group to the end of
  the slices built on its result, every value comes from the same version (note 01 §3).
- **Readers never wait for writers, and writers never wait for readers** (PLAN §2.3). A long
  computation on an old version does not delay an update, and an update does not stall a
  running computation.
- **Each version is exact at one sequence.** For a version at sequence `S`, every loaded column
  equals what a fresh load of `data.db` at `S` would give.
- **A column is complete or absent.** A property is either loaded for every slot or not loaded at
  all. A change to a property that is not loaded never creates a partial column.
- **Versions are totally ordered** and their sequences never decrease, except across a full
  reload (§6.5), which is notified as one.
- An update to one property must not cost in proportion to the other properties (no copy of
  untouched columns).

## 5. Loading

### 5.1 Opening a project

Read in one read transaction, so that everything is at the same sequence `S`:

1. `S` = the current maximum sequence;
2. the schema (§3.5);
3. every instance, ordered by `id`. The slot order is the input order of every collection, and
   sort ties keep it, so it must be stated and not left to the query plan.

No property column is loaded at open. The first version is at `S`.

### 5.2 Loading columns on demand

`ensure(properties)` makes the given columns available and returns the first version that has
them all.

- Called by a collection before it computes (the properties of its filter, sort and grouping)
  and by a view for the properties it draws.
- **One load per column.** Concurrent requests for a column being loaded wait for that load.
- **Loads run in parallel** with each other, on their own read connections, and never on an
  async runtime worker.
- **Columns requested together are published together**, in one version, so a collection opened
  at startup with 6 columns computes once and not 6 times.
- **Built directly from the rows** into the typed layout. The bench measured the path through a
  generic JSON value per cell at 2× the direct one (1.70 s against 916 ms for 7 columns at 1M).
- The reads per mode:

| property | rows |
|---|---|
| `id` mode | live rows of `instance_values` for the property |
| `sha1` mode | live rows of `sha1_values`, each value written to every slot of the sha1 |
| `file` mode | live rows of `file_values`, each value written to every slot of the file |
| tags | live rows of `instance_tag_values` or `sha1_tag_values` for the property, alive tags only |
| system | `instances` / `files` (§3.3) |

- "Live" excludes tombstoned rows (`operation` = DELETE). A property that is not alive (its
  creation was undone) has no column: its values are dormant, as `get_delta` treats them.
- Reading a tag column must group each instance's tags whole. The Python route splits an
  instance across two batches when a batch fills up, and the front then keeps only the second
  part (`bench/collection` README, Load, 67 instances at 1M). The store must not reproduce that.

### 5.3 Loading while the db moves

A column is read at sequence `C`, while the store may have moved on to sequence `T`. Before the
column joins a version, it must be brought to that version's sequence:

- `C < T`: apply to the column the changes of its property in `(C, T]`;
- `C > T`: the store first catches up to at least `C` (§6.1), then the case above.

Test: writes landing between the read of a column and its publication must all be in the
published column (§9).

### 5.4 Targets

At 1M instances, warm OS cache, measured by `bench/collection/load` on the current `data.db`
format:

| | target | measured by the bench |
|---|---:|---:|
| open (instances) | ≤ 300 ms | 276 ms |
| one scalar column (number, label, checkbox) | ≤ 100 ms | 84–98 ms |
| text, ~1M distinct values | ≤ 260 ms | 253 ms |
| date | ≤ 130 ms | 129 ms (≈ 85 ms once dates are stored as integers, note 03) |
| tags, 2.5M rows | ≤ 200 ms | 182 ms |
| 7 columns | < 1 s | 916 ms |

SQLite alone is 65–70 ms of a scalar column. The rest is decoding and string interning. Note 03's
layout lowers both.

## 6. Updates

### 6.1 Sources, and one path for all of them

`data.db` changes through:

- the backend's writer: commits from the UI and from plugin actions routed through the backend;
- undo and redo, which enable or disable commits and re-resolve the rows they touched;
- plugin processes writing directly with the SDK (PLAN §2.5), which send `db.changed`;
- structural writes: imports (instances, files, folders) and deletes.

All of them reach the store by one path: read the changes since the store's sequence, turn them
into store changes, publish one new version. Triggers: the writer after each commit, undo or
redo; `db.changed`; a periodic check as a safety net. At most one catch-up runs at a time. A
trigger during a catch-up schedules exactly one more, so a burst of writes costs a few catch-ups
and not one per write. Our own writes are not applied to the store directly: one path keeps one
order of application.

`wait_for(sequence)` resolves once the store has a version at that sequence or later. A route
that writes and then reads (and the engine's `settle`, note 01 §4.2) uses it.

### 6.2 What a change does

| change in `data.db` | in the store |
|---|---|
| new instances | new slots, appended. Their sha1-mode and file-mode values for the loaded columns are read from `data.db` in the same catch-up |
| an instance id that comes back after a delete (`instances.id` has no `AUTOINCREMENT`, so SQLite can reuse the largest id) | treated as a new instance, not as the old deleted one |
| instance deleted | the slot is marked deleted. Structural rows are hard-deleted and do not appear in `get_delta`: deletes by the backend's writer are passed on from the writer, plugin deletes need §8 |
| value written, loaded property | the cells of its instances: one for `id` mode, every instance of the sha1 or file otherwise |
| value tombstoned (removed or undone), loaded property | the same cells become "no value" |
| tag junction rows, loaded property | the whole tag list of each touched (instance or sha1, property), read again, alive tags only |
| any change to a property that is not loaded | nothing loaded. It is still reported (§7) |
| tag deleted | the tag id is removed from every loaded tag column |
| tag parents changed | columns unchanged, the schema changes (the engine's tag expansion depends on it) |
| folder renamed or moved | the `path` column is recomputed |
| property created | nothing to load. It can be known empty right away |
| property deleted, or its creation undone | its column is dropped |
| property type changed to another kind of value (text ↔ number ↔ tags), or mode changed | its column is dropped and loaded again on the next `ensure` |
| property type changed within a kind (number ↔ date) | values unchanged, the change is reported so the engine drops what it derived from them |

A write that sets a cell to the value it already has is not a change. Undo and redo re-resolve
rows and often rewrite identical values, and these must not make collections recompute.

### 6.3 Ordering and idempotency

- Inside one catch-up, new instances are applied before values, so a value for a new instance
  always finds its slot.
- A catch-up may deliver a row the store already has. Applying it again must change nothing.

### 6.4 Targets

To be set from measurements (§9), with these starting points at 1M instances:

- one edit from the UI: in a new version within 10 ms of the commit;
- 100 edits landing within 50 ms: at most 2 versions;
- a plugin writing one property for every instance: in one version, in less time than loading
  that column from scratch.

### 6.5 Full reload

The store reloads from scratch (open + every column that was loaded) when:

- the current maximum sequence of `data.db` is **below** the store's: the file was replaced or
  restored;
- the project is opened again;
- compaction changed rows without moving the sequence forward, if it can (§8).

Slots are renumbered. The reload is published as one version, flagged so that every collection
recomputes from scratch and anything holding slot-indexed data drops it.

## 7. Notifying

### 7.1 Content

Each new version comes with a change record:

| field | content |
|---|---|
| versions | the previous and the new version, and the new sequence |
| values | per property: the slots whose value really changed |
| added | the new slots |
| deleted | the slots marked deleted |
| loaded | the columns that became available |
| dropped | the columns removed or waiting for a reload |
| schema | the properties, tags and folders that changed, by id and by kind of change (§6.2) |
| unloaded properties | the properties changed in `data.db` that have no column |
| reload | true for a full reload (§6.5): everything else is moot |

The changed slots are given per property, so that a collection grouping on property A can tell
that a change to property B does not concern it. A record's size grows with the number of changed
cells, and stays within a few bits per slot even when every slot of a column changes.

### 7.2 Delivery

- **One consumer**: the engine, which fans out to collections and views (note 02 §7.4).
- **In order, none lost.** Records are delivered in version order and never dropped or merged
  away. A collection that misses a record loses which slots changed. If the consumer falls
  behind, consecutive records may be merged into one, provided the merge keeps every changed
  slot.
- **Cheap for the store.** Delivering a record does not run the consumer's work. The store does
  not wait for collections.

### 7.3 What the engine does with it

Not part of the store, recalled here because it defines what the record must carry (note 02
§7.4): a collection whose filter, sort and grouping do not use any property of `values` sends a
`values` push to its views and does not recompute. One that uses them and is visible recomputes
incrementally from the changed slots (note 01 §5.4). One that is hidden is marked dirty. A
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
- The budget and the eviction order are those of note 02 §7.6.

## 9. Acceptance tests

1. **Load parity**: a `data.db` written by the Python backend (fixture projects, every property
   type and mode, system properties, deleted and dormant properties, duplicates by sha1) loads
   into the same values as the front's `columnStore`, slot for slot.
2. **Replay**: after a random sequence of commits, undos, redos, imports, deletes, tag and
   property deletes, and schema changes, the current version equals a fresh load at the same
   sequence. The most important test.
3. **Interleaving**: writes between the read of a column and its publication end up in the column
   (§5.3).
4. **No partial column**: a write to an unloaded property leaves it unloaded and is reported in
   `unloaded properties`.
5. **No-op writes**: undo then redo of a commit reports only the cells whose value changed.
6. **Notification**: every changed cell of the replay test appears in exactly the records of the
   versions that changed it, per property.
7. **Performance**: the targets of §5.4 and §6.4, through `bench/collection/load` extended with
   updates: an edit on a 1M and a 10M column, a burst of 100 edits, a 1M-row plugin write.

## 10. Open questions

- Instance deletes by a plugin process do not appear in `get_delta`. Should there be a tombstone
  table (note 03 §3 proposes one), or should `db.changed` trigger a comparison of instance ids?
- Does `compact(horizon)` keep sequences increasing and the result rows unchanged? If it does,
  it needs no reload.
- Unload policy for columns: time, memory budget, or both?
- What may a single edit cost on a 10M column, given that readers keep older versions? Set the
  bound from the measurements of §9.7.
- Thresholds: the catch-up coalescing delay, the dictionary rebuild ratio, the encoding switch of
  changed slots between a list and a bitset.
