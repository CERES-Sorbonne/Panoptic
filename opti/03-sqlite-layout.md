# 03: SQLite layout for the backend engine

Status 2026-10-20: proposal, nothing changed on disk. Builds on
[01-collection-manager.md](01-collection-manager.md) §5.1. Numbers come from the
`bench/collection` load bench (`results/load/report-1000000.md`), from a copy of its 1M
`data.db` rebuilt in the layout below (timed with the `sqlite3` CLI, warm cache, median of 5),
and from the real project `~/panoptic-projects/express` (150k images, 457 MB `data.db`).

## 1. Principle

With the engine doing filter, sort and group in memory, SQLite never runs a `GROUP BY` or an
`ORDER BY` for the UI. It only has to:

1. **load one property column** into a typed `Column` (`store.rs`) with one sequential read;
2. take small writes cheaply;
3. return what changed since a `sequence` (deltas, plugin writes).

So the layout is chosen for range scans by property and for decode-free values, not for
queries.

## 2. What costs today

| issue | where | cost |
|---|---|---|
| `value` is declared `JSON`: text is stored quoted (`"arde"`), dates as ISO text (`"2015-01-09T13:26:07.061Z"`), checkboxes as `true` / `false` text | `instance_values`, `sha1_values`, `file_values` | a JSON decode per cell, plus a date parse: date loads in 129 ms against 85 ms for a number column (1M) |
| rowid tables with a composite primary key | the value and tag tables | each row lives in two B-trees. A column load walks the key index, then fetches every row by rowid |
| `instance_tag_values` key is `(instance_id, property_id, tag_id)` | tags | loading one tag property scans the whole table (`SCAN instance_tag_values`) |
| tombstones stay in the result tables, with an index on `operation` | value and tag tables | every load filters on `operation`. The index almost never narrows a lookup (nearly every row has the same value), but each write still pays for it (54 MB at 1M) |
| sha1 is 40-character hex `TEXT` | `instances`, `files`, `sha1_*` | 41+ bytes per row and per index entry. Interning 1M sha1 strings is most of the 276 ms `base` load |
| `idx_entity_log_entity` repeats the `entity_log` primary key column for column | `entity_log` | 50 MB on express, write cost, no use |

## 3. Proposed schema

```sql
PRAGMA journal_mode=WAL;  PRAGMA synchronous=NORMAL;
PRAGMA page_size=8192;    PRAGMA mmap_size=1073741824;  PRAGMA temp_store=MEMORY;

-- sha1 dictionary: everything else refers to an image content by a dense integer
CREATE TABLE sha1s (
  id   INTEGER PRIMARY KEY,           -- = Identity.sha1 code in the engine, no interning
  hash BLOB NOT NULL UNIQUE           -- 20 raw bytes
) STRICT;

CREATE TABLE files (
  id INTEGER PRIMARY KEY, folder_id INTEGER, sha1_id INTEGER NOT NULL,
  name TEXT, width INTEGER, height INTEGER, format TEXT,
  created_at INTEGER,                 -- unix ms
  ahash BLOB,                         -- 8 bytes
  sequence INTEGER NOT NULL
) STRICT;

CREATE TABLE instances (
  id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL,
  sha1_id INTEGER NOT NULL, sequence INTEGER NOT NULL
) STRICT;

-- Scalar values, live rows only. Same shape for sha1_values (sha1_id) and file_values (file_id).
-- Property first in the key: one column = one contiguous range of one B-tree.
CREATE TABLE instance_values (
  property_id INTEGER NOT NULL,
  instance_id INTEGER NOT NULL,
  value       ANY NOT NULL,           -- native INTEGER | REAL | TEXT, never JSON
  sequence    INTEGER NOT NULL,
  PRIMARY KEY (property_id, instance_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX instance_values_seq ON instance_values(sequence);

-- tag and multi_tags: one row per (entity, tag), property first. Same for sha1_tag_values.
CREATE TABLE instance_tag_values (
  property_id INTEGER NOT NULL,
  instance_id INTEGER NOT NULL,
  tag_id      INTEGER NOT NULL,
  sequence    INTEGER NOT NULL,
  PRIMARY KEY (property_id, instance_id, tag_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX instance_tag_values_tag ON instance_tag_values(tag_id);   -- tag delete only
CREATE INDEX instance_tag_values_seq ON instance_tag_values(sequence);

-- Deletions, for delta sync only. Pruned once every reader is past their sequence.
CREATE TABLE tombstones (
  table_id INTEGER NOT NULL, k1 INTEGER NOT NULL, k2 INTEGER NOT NULL, k3 INTEGER,
  sequence INTEGER NOT NULL
) STRICT;
CREATE INDEX tombstones_seq ON tombstones(sequence);
```

A column load is then `SELECT instance_id, value FROM instance_values WHERE property_id = ?`:
a range scan with no filter, read through `ValueRef` without allocating.

`WITHOUT ROWID` works best when rows are small. Long texts (descriptions) spill to overflow
pages either way, and `page_size=8192` keeps that rare. The store's `typed` load path
(01 §5.1) must stay: the generic `serde_json::Value` path costs 2× typed.

## 4. Encoding per property type

The disk side is chosen so that each value decodes straight into the column type
`store.rs` already uses.

| type | on disk (`value`) | engine column (`store.rs`) | notes |
|---|---|---|---|
| `number` | INTEGER or REAL, native | `Column::Num` (`f64`, NaN = none) | already native today (NUMERIC affinity) |
| `checkbox` | INTEGER 0 / 1 | `Column::Bool` (`u8`) | SQLite stores 0 and 1 in the row header, with no payload bytes |
| `date` | **INTEGER, unix ms UTC** | `Column::Num` (`f64` ms, exact below 2^53) | removes the per-cell ISO parse |
| `color` | INTEGER | `Column::Num` | |
| `text`, `url`, `path`, `image_link` | TEXT, raw UTF-8 | `Column::Str` (`u32` codes + `StrDict`) | no JSON unquoting. Interning stays (≈150 ms at 1M distinct, see §6) |
| `tag`, `multi_tags` | `instance_tag_values` rows | `Column::Tags` (CSR) | property-first key. A scalar `tag_id` column for `tag` would save little, since the engine holds both as CSR |
| sha1 | `sha1_id` INTEGER | `Identity.sha1` (`u32`) | the code comes from SQLite, so there is nothing to intern. Hex strings only for the API, built on demand |
| `ahash` | BLOB(8) | `u64` | |
| `folder`, `width`, `height`, `id` | INTEGER in `files` / `instances` | `ColRef::FolderNum` / `Int` | unchanged |

## 5. Measured on the 1M bench db

Same synthetic data as `results/load/1000000/data.db`, rebuilt with the schema above
(`page_size=8192`). The timings are for the scan query alone, through the `sqlite3` CLI
(`count`, `max(id)`, `max(value)` over the range), so read the ratio rather than the absolute
time. The Rust decode savings come on top of these.

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
  by the sha1 interning (≈150–200 ms of 276 ms). These are estimates from the load bench's
  breakdown. Re-measure once `bench/collection/load` can read this layout.

## 6. Options not in the default

- **Column snapshot cache**:
  `column_cache(property_id INTEGER PRIMARY KEY, sequence INTEGER, data BLOB)` holds the raw
  little-endian column (optionally zstd-compressed). On open, read the blob and apply the
  deltas newer than its `sequence`. A cold load of a column becomes about one blob read. It is
  a cache: the value tables stay the truth, and the cache can be dropped at any time.
- **Strings dictionary on disk**: `strings(id, text)` and `value = string id` would remove
  text interning at load. It costs a dictionary that plugins must maintain when they write
  directly, plus garbage collection of unused strings. Only worth it if text loads still
  dominate after §5.
- **`entity_log` keys as integers**: today `entity_key` is a JSON text compared byte for
  byte (`pyjson.rs` reproduces CPython's `json.dumps` for this). Typed columns `k1`, `k2`, `k3`,
  `entity_type` as a small INTEGER and `changes` as msgpack BLOB would make it smaller and
  drop that constraint. `entity_log` and its indexes are 244 MB of the 457 MB of express.

## 7. Compatibility

[`PLAN.md`](../technical_docs/rust_port/PLAN.md) goal 4 says the on-disk format stays
byte-compatible with the Python backend. Sections 3–4 break that, so they need:

- a data.db v3 migration, in Python, in `panoptic.migration` (legacy projects already go
  through it);
- the plugin SDK's read and write helpers (P1-D) written against v3 from the start.

Do it before P1-A (`panoptic-db`) and P1-D freeze the format. Once plugins read the files
directly, every layout change is a migration they must follow too.

Possible today without breaking the format:

1. drop `idx_entity_log_entity` (the primary key already covers it);
2. drop the `operation` indexes on the value and tag tables;
3. put `property_id` first in the `instance_tag_values` / `sha1_tag_values` key. The
   Python code addresses these rows by column name, so only the `CREATE TABLE` and a table
   rebuild change. Check `entity_schema.py` before relying on that.

## 8. Open questions

- `commit_id` on value rows: the resolver writes it (`resolver.py:150`) and the schema dropped
  it above. `data_reader.py`, `project.py` and `project_routes.py` mention `commit_id`. Check
  whether any of them reads it from value rows before dropping it.
- Dates: unix ms UTC, or a naive local time like `pytime.rs` keeps for `TIMESTAMP` columns?
  The front compares `getTime()`, which is UTC ms.
- Tombstone pruning: what sequence is "every reader is past it", given plugin processes that
  poll on their own?
