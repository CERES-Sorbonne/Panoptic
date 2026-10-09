# Lazy tree design — instant views over 100M rows (Tauri + Rust core)

Goal: the grouped/sorted/filtered tree that `TreeScroller` walks today, but **never
materialized**. Opening a view, or jumping to `groupId: "343239384"`, must cost
milliseconds regardless of row count; scrolling computes only the zone entering the
viewport. Context for this revision: the app is a **Tauri shell — all computation lives
in a Rust core process**, the webview only renders. SQLite stays the source of truth on
disk. Two engine designs behind one shared protocol: **A — SQL-resident** (the SQL
engine pre-filters/pre-orders; raw data never enters process memory) and **B — Rust
columnar** (columns resident/mmapped, tree materialized lazily). Undo/redo is out of
scope.

## 0. Why the current pipeline can't get there

`CollectionManager.update()` is eager end-to-end: full slot array O(N) → filter O(N) →
sort O(N log N) → `GroupManager.group()` builds **every** group with its
`slots: number[]` → `orderedIds` (full DFS permutation) → lines. Cost and memory are
O(N) before the first pixel, though the viewport shows ~50 rows. Moving that code to
Rust would make the passes 10–50× faster but it would still be the wrong shape: at 100M
rows an eager global sort is seconds and `orderedIds` is 400MB that the viewport never
reads. The design below changes the shape; Rust then makes the remaining small
computations effectively free.

## 1. The central insight: the tree is an ordering, not a structure

For a view spec `V = (filter, groupBy = [g₁ … g_d], sortBy)`, define per row (per
*membership*, see multi-tags below) the composite key

```
K = ( b₁, b₂, …, b_d, S, instance_id )
```

`bᵢ` = normalized bucket key at level i, `S` = leaf sort key. Then **the DFS order of
the tree's leaves is the lexicographic order of `K`**, and a group at depth i is exactly
the contiguous run sharing the prefix `(b₁ … bᵢ)`. So:

- a *group* is a key prefix: contiguous range + count, no node object, no slots array;
- an *iterator* is a cursor over the ordering; headers are emitted where the prefix
  changes between consecutive items;
- any jump (gid, scrollbar) is a *seek*.

**Sibling display order is deliberately NOT encoded in the key.** Groups can be ordered
by name, by count, by score — and tag renames would otherwise invalidate keys. Bucket
keys are therefore *fixed-width ids* (tag_id, date bucket int, number bucket int, string
dictionary id), and the display permutation of siblings lives in the spine (§3), which
directs the cursor from one prefix range to the next. Only the leaf sort key `S` must be
memcomparable (byte order = sort order, direction baked in by byte inversion).

### Multi-tag levels: rows become memberships

A multi-tag level maps one row to *several* buckets — its tags **plus their ancestors**
(today's `tagWithParents` semantics: an image tagged `siamese` also appears under
`cat`), deduplicated per (row, bucket), with one `untagged` bucket (id 0) for rows with
no tag. Formally the engine enumerates `(prefix, instance)` **memberships**, not rows:

- the same instance legitimately appears in several sibling groups (as today);
- group count = distinct instances in that prefix (the dedup happens at expansion);
- the root/totals count instances, not memberships — both numbers are kept in the spine
  (`count` = instances, memberships only matter as internal range sizes);
- *sorting by* a multi-tag property uses `S` = the row's ordered list of tag *ranks*
  (see §2.1), memcomparable-encoded as a length-prefixed sequence; untagged sorts last.

## 2. Stable, hashable group ids

```
gid(root)  = H64(viewless-root-seed)
gid(child) = H64( gid(parent) ‖ levelPropertyId ‖ bucketKeyBytes )
```

xxhash64-style incremental path hash. Deterministic and order-free: independent of
sibling rank, filter, and computation order — so `closed`/selection state keyed by gid
survives refilters (today's persistent `GroupValueIndex` contract), and
`seek("343239384")` works across sessions. The spine stores `gid → (parent_gid,
key bytes)`, so resolving a gid to its key prefix is one lookup; no ancestor walk.
All lazily computed artifacts are cached under `(viewHash, gid)`;
`viewHash = H(canonical spec)` namespaces caches while gids stay view-independent.

### 2.1 Dictionaries and ranks (small, shared by both designs)

- `tag_rank[property]`: tag_id → u32 rank in display order (name collation). Rebuilt on
  tag create/rename/merge — thousands of entries, microseconds. Used for spine sibling
  ordering and for multi-tag sort keys. A rename invalidates only rank-dependent
  artifacts (spine order, skeys that used ranks), lazily.
- `tag_expand[property]`: tag_id → sorted `&[bucket_id]` = {self} ∪ ancestors, from the
  tag DAG. Rebuilt on parent edits. This is the multi-tag expansion table.
- `string_dict[property]` for string group-bys: value → u32 id (per-view or persistent).

## 3. The spine: the only eager structure (and it's small)

`(gid, parent_gid, depth, key, display_rank, count?, cum_start?)` — size = number of
groups, not rows. Built top-down, lazily per level: level 1 on open; level i+1 only for
groups that are open *and* near the viewport. Counts are progressive (`NULL` allowed);
scrollbar geometry uses known `cum_start` prefix sums plus estimates, corrected as
counts arrive, with reflow anchored to the top visible gid so content never jumps.
`locate(fraction)` binary-searches the sums.

## 4. The shared protocol (webview ⇄ Rust core)

`GroupIterator` / `ImageIterator` stay as the JS facade; behind them, Tauri IPC to the
core. The commands:

```
open(view)                      → handle        (spine level-1 scheduled)
spine(h, fromGid?, depth, k)    → SpineRow[]
seek(h, {gid, offset?})         → cursor
read(h, cursor, k, dir)         → Chunk         (headers + id runs + next/prev cursor)
locate(h, fraction)             → {gid, offset}
totals(h)                       → {rows?, groups?, exact}
invalidate(h, ids?)             
```

IPC specifics that matter at this scale: ship `Chunk` as **raw binary**
(`tauri::ipc::Response` / ArrayBuffer — not JSON; a chunk is a few KB of u32s),
keep cursors opaque byte strings, and let the webview prefetch ±2 screens. Roundtrip
budget is ~0.1–0.5ms locally, invisible behind prefetch. Layout (images per line, pile
mode) stays in the webview; the core deals in logical rows only. Stale-response
discipline: every reply carries `(viewHash, generation)`; the UI drops mismatches
(the existing latest-wins token pattern).

---

## 5. Design A — SQL-resident: data never enters process memory

**Principle:** the database is designed for this one workload, from scratch. It is not a
normalized store that queries adapt to — it is a **collection of B-trees, each laid out
so that one access pattern of the tree engine is a pure range scan**. One rule generates
the entire schema:

> For every axis the UI can filter, group or sort on, keep one B-tree ordered
> `(axis, value, row_id)`. For every row, keep one reverse B-tree `(row_id → its
> values)`. Tables ARE their indexes (`WITHOUT ROWID`, PK = the access path); a second
> index exists only where a second access pattern truly exists. Values are typed columns
> (never JSON); an absent value is an absent row, not a NULL.

Reads — the 99% case — never scan, never parse, never join through a base row. Writes
pay O(log N) per B-tree touched. That is the correct trade for a browsing workload.

### 5.1 Base model

```sql
-- Rows. One physical table; sha1 piles are just another axis.
CREATE TABLE row (
    id   INTEGER PRIMARY KEY,
    sha1 BLOB NOT NULL,
    file INTEGER NOT NULL
);
CREATE INDEX row_by_sha1 ON row (sha1, id);

-- Scalar values: one table per type family. PK order (prop, val, id) IS the
-- filter/group/sort pushdown. number, date (epoch ms), checkbox, color → val_num.
CREATE TABLE val_num  (prop INTEGER, val REAL, id INTEGER,
    PRIMARY KEY (prop, val, id)) WITHOUT ROWID;
CREATE TABLE val_text (prop INTEGER, val TEXT COLLATE NOCASE, id INTEGER,
    PRIMARY KEY (prop, val, id)) WITHOUT ROWID;
-- reverse path: hydrate one row for display, invalidate one row on write
CREATE INDEX val_num_by_id  ON val_num  (id, prop);
CREATE INDEX val_text_by_id ON val_text (id, prop);

-- THE multi-tag table: memberships ancestor-EXPANDED and deduped AT WRITE TIME.
-- One row per (property, bucket_tag, row) where bucket_tag ∈ tags(row) ∪ ancestors.
-- ⇒ grouping or filtering by any tag, hierarchy included, is ONE contiguous range
--   scan. No closure join, no DISTINCT, not at any read, ever.
CREATE TABLE tag_index (prop INTEGER, tag INTEGER, id INTEGER,
    PRIMARY KEY (prop, tag, id)) WITHOUT ROWID;
CREATE INDEX tag_index_by_id ON tag_index (id, prop, tag);

-- The raw (unexpanded) assignment, kept for display/editing — and its PK (prop, id,
-- tag) is deliberately id-ordered: the 'untagged' bucket is an anti-merge-join of a
-- sorted id stream against this tree.
CREATE TABLE tag_set (prop INTEGER, id INTEGER, tag INTEGER,
    PRIMARY KEY (prop, id, tag)) WITHOUT ROWID;

-- Folder axis, same treatment: descendant-expanded at write time.
-- "rows under folder F" (any depth) = one range scan.
CREATE TABLE folder_index (folder INTEGER, id INTEGER,
    PRIMARY KEY (folder, id)) WITHOUT ROWID;

-- Small side tables (cached whole in the core, never in hot paths): properties,
-- tags(id, prop, name, parents), folders, tag_closure(tag, anc) — tag_closure is the
-- *maintenance source* for tag_index, not a read-path table — plus the tag_rank and
-- string dictionaries of §2.1.
```

Write costs, stated honestly (each fact lives in 2–3 trees — that *is* the design):

- set a scalar value: delete+insert in `val_*` and its `_by_id` mirror — 4 B-tree ops;
- tag a row: 1 `tag_set` row + (1 + ancestors) `tag_index` rows × 2 trees;
- move a tag under a new parent: rewrite the `tag_index` rows of the rows carrying that
  subtree's tags — a bounded, enumerable range rewrite (the affected ranges are read
  straight out of `tag_index`), done in one background transaction;
- move a folder: same shape on `folder_index`.

### 5.2 Per-view tables

```sql
-- The ordering itself. WITHOUT ROWID ⇒ the table IS the B-tree, PK order = DFS order.
CREATE TABLE view_idx_<viewHash> (
    gkey BLOB,                -- b₁…b_d concatenated, fixed-width per level (u32/i64 ids)
    skey BLOB,                -- memcomparable leaf sort key, direction baked in
    id   INTEGER,             -- instance id (repeated per membership at multi-tag levels)
    PRIMARY KEY (gkey, skey, id)
) WITHOUT ROWID;
CREATE INDEX idx_vi_id ON view_idx_<viewHash> (id);    -- reverse map for invalidation

CREATE TABLE view_spine_<viewHash> (
    gid INTEGER PRIMARY KEY, parent_gid INTEGER, depth INTEGER,
    gkey_prefix BLOB, display_rank INTEGER,
    count INTEGER, cum_start INTEGER          -- NULLable: progressive
);
CREATE INDEX idx_spine_walk ON view_spine_<viewHash> (parent_gid, display_rank);
```

### 5.3 Build — index-only merges of pre-sorted streams

Because every base tree is already in `(prop, value, id)` order, building a view
partition is *stream plumbing*, never computation:

- **a filter predicate** = one or a few contiguous ranges of one tree → sorted id
  streams; AND/OR = merge-intersect/union of sorted streams (SQLite does this as
  index-only joins; the Rust side can equally drive the cursors itself);
- **a scalar group level** is free: bucket is a monotone function of `val`, and the
  stream is already in `val` order — gkey assignment happens on the fly, no sort;
- **a multi-tag group level IS `tag_index`**: already expanded, already deduped,
  already `(bucket, id)`-ordered — one range scan per bucket. The `untagged` bucket is
  the anti-merge of the filtered id stream against `tag_set(prop, id)`;
- **the leaf sort key** joins each id against `val_*(sortProp)` via the PK — and under
  anchor-first scheduling partitions are viewport-sized, so even this join touches
  thousands of entries, not millions.

Sketch for `groupBy = [multiTag P₁, date P₂]`, sort by number P₃ — every table in the
plan is read in PK order, index-only:

```sql
INSERT OR IGNORE INTO view_idx_<h>          -- PK (gkey,skey,id) absorbs any residue dup
SELECT enc2(t.tag, date_bucket(v2.val, :step)),   -- gkey
       enc_skey(v3.val, t.id),                    -- skey
       t.id
FROM tag_index t                                  -- expanded + deduped at write time
JOIN val_num v2 ON v2.prop = :P2 AND v2.id = t.id
JOIN val_num v3 ON v3.prop = :P3 AND v3.id = t.id
WHERE t.prop = :P1 AND t.tag = :anchorBucket      -- anchor-first: one partition
  AND <filter ranges>;
-- enc* are tiny Rust scalar UDFs (rusqlite create_scalar_function), or plain integer
-- arithmetic when the key is single-level.
```

Spine counts fall out of the same write (one row per `(bucket, id)` ⇒ `COUNT(*)` *is*
the distinct-instance count at a multi-tag level; only the rare multi-tag-under-
multi-tag stacking needs `COUNT(DISTINCT id)`):

```sql
INSERT INTO view_spine_<h> (gid, …, count)
SELECT …, COUNT(*) FROM view_idx_<h> GROUP BY gkey_prefix_level(gkey, :i);
```

**Anchor-first scheduling** makes open() instant: resolve the anchor gid → build only
`WHERE b₁ = anchorBucket` first (one partition), serve the viewport from it, fill the
other partitions by viewport distance in a background task; each finished partition
upserts its spine rows with exact counts.

### 5.4 Serving

- Within a group, or across groups whose display order equals key order:
  `WHERE (gkey,skey,id) > cursor ORDER BY gkey,skey,id LIMIT 256` — one B-tree descent
  + sequential leaf read, **O(log N + K)**, sub-ms warm.
- When siblings are display-permuted (by name rank, by count): walk
  `view_spine (parent_gid, display_rank)` and issue one range scan per group — two
  queries instead of one, same asymptotics.
- Jump to gid: spine PK lookup → range scan from `gkey ≥ prefix`. Exact count of one
  group on demand: `COUNT(DISTINCT id)` over its prefix range — proportional to the
  group, background.
- Maintenance on a data commit: look up the touched ids in `idx_vi_id`, delete +
  re-derive those memberships, adjust spine counts by delta; or mark the view stale and
  rebuild lazily (writes are rare next to scroll reads). View tables are pure caches —
  LRU-drop inactive ones.

Honest worst case: complete scrollbar exactness over a filter matching all 100M rows
needs the full build — a one-off background O(N) *inside SQLite* per view spec.
Interaction starts after the anchor partition; nothing interactive waits on O(N).

---

## 6. Design B — Rust columnar core: preload (mmap), then lazy-materialize

**Principle:** columns live in the Rust process; the tree is computed lazily per
viewport, never stored. With no JS limits this becomes the primary engine: 100M-row
passes are memory-bandwidth problems (~400MB per u32 column, ~50ms/pass single-thread,
~10ms with rayon), and `unsafe`-free Rust (`sort_unstable`, `select_nth_unstable`,
roaring-rs, rayon) covers every kernel needed.

### 6.1 Data model

- **Column cache file per project**, written by the core, **memory-mapped** on open
  (mmap ⇒ "load" is O(1); the OS pages in only what passes touch). Layout per property:
  - scalar: `value: [u32|i64|f64; N]` + null bitmap (slot-indexed, like today's
    columnStore);
  - **multi-tag: CSR** — `offsets: [u32; N+1]`, `tag_ids: [u32; M]` (M = total
    assignments). This is the multi-tag representation: per-row tag list is
    `tag_ids[offsets[s]..offsets[s+1]]`;
  - strings: dictionary + `[u32; N]` codes.
  - Built once from SQLite (streamed, parallel decode), then maintained incrementally
    from the existing sequence-delta sync; never rebuilt wholesale.
- **Filter result**: roaring bitmap over slots; compacted into the **view buffer**: one
  `Vec<u32>` whose recursive `[start,end)` ranges *are* the tree (§6.2).
- Spine/NodeState cache: `FxHashMap<(viewHash, gid), NodeState>` with LRU,
  `NodeState = { counted, partitioned, sorted_to }`.

### 6.2 The lazy radix tree — one buffer, in-place partitions

Materializing a node's children = a **stable counting sort of the node's range** of the
view buffer (two passes: histogram → scatter). No per-group allocations; perfectly
cache-linear; embarrassingly parallel across sibling nodes with rayon.

Multi-tag levels need the membership expansion, which changes the buffer length — so a
multi-tag partition *replaces* the node's range with an **expanded range** in a fresh
buffer segment: for each slot, walk its CSR list, map through `tag_expand` (self +
ancestors), dedup the per-row bucket set (rows have ~1–10 tags; a 64-bit stack bitset
over the row's bucket list suffices), then histogram + scatter the *(bucket, slot)*
memberships. Counts per bucket = distinct slots, exact, produced by the same pass.
Untagged rows scatter into bucket 0. Memory: the expansion exists **only for the
node being partitioned**, not globally — a viewport path touches a vanishing fraction.

- `open(view)`: filter bitmap (parallel column scans + roaring ops) → compact → level-1
  partition. **No global sort, ever.** ~2 passes over the touched columns: at 100M ≈
  100–300ms cold (page-in), tens of ms warm.
- `seek(gid)/read(k)`: descend the gid path, partitioning only along it (each level a
  shrinking range), then sort lazily **only the leaf window**:
  `select_nth_unstable` (Floyd–Rivest) to cut the top `sorted_to + k`, `sort_unstable`
  the window; `sorted_to` grows with scrolling; leaves < 64k rows just sort fully.
  Sort keys come straight off the mmapped columns; multi-tag sort key = ordered
  `tag_rank` list per row (cheap to compare directly — no encoding needed in-process).
- Scrolling inside computed zones: pointer walking, microseconds. Sibling display order
  (name rank / count / score): sort the node's children array — spine-sized, trivial.
- `invalidate(ids)`: flip filter bits for the touched slots, dirty the gids they belong
  to (reverse lookup via the partition ranges along cached paths), re-partition lazily
  on next touch — the per-range equivalent of today's `updateSelection`.

### 6.3 Cost profile (100M rows, K≈256 viewport)

| Operation | Cost |
|---|---|
| open project | mmap: O(1); cold pages stream in on first pass |
| open view | O(N) filter+compact, vectorized+parallel: 10²ms cold, 10¹ms warm |
| expand/scroll into a group | counting-sort of that range + O(range + k log k) window sort |
| scroll inside computed zone | O(k) memory walk |
| jump to gid | partition along one ancestor path (shrinking ranges) |
| counts | exact, free (same pass as partition) |
| memory | mmapped columns (OS-managed) + 4B/membership view buffer + spine |

---

## 7. A vs B under a Rust core — revised verdict

| | A — SQL-resident | B — Rust columnar |
|---|---|---|
| process memory | ~0 (SQLite page cache) | view buffer + mmap residency (OS-evictable) |
| open view (cold) | ms (anchor partition; full build backgrounded O(N) in SQL) | 10²ms full pass; no background debt |
| scroll | sub-ms queries, prefetch-hidden | µs, memory |
| counts | progressive (estimates until built) | exact immediately |
| multi-tags | `tag_index`: expanded+deduped at write, read = range scan | CSR + expand table, dedup in-pass |
| writes | per-id index maintenance or lazy rebuild | bit flips + lazy re-partition |
| extra storage | per-view index tables (duplicated orderings) | one column cache file |
| complexity risk | key encoding, view-table lifecycle, SQL UDFs | column cache format + incremental sync |

The JS memory/speed ceiling was the main argument for A; a Rust core removes it. **B
becomes the primary engine**: exact counts for free, no per-view disk artifacts, no key
encoding subtleties, and the same mmap trick erases its old cold-start weakness. The
base model of §5.1 is worth having either way — B's column-cache extraction becomes
pure sequential PK scans of the same trees — and §5.2's per-view tables remain the
fallback tier for memory-starved machines or datasets whose *columns* outgrow RAM+disk
budgets — behind the same protocol, invisible to the UI.

## 8. Billions of rows — where each design hits its wall

The scaling story is entirely about which operations are O(N). Interactive reads never
are, in either design — what breaks at 10⁹+ is everything else. Raw constants on a
desktop (NVMe ~3–7GB/s sequential, 16–64GB RAM, SQLite bulk-sorted insert ~1–5M rows/s
single-core):

| N (memberships) | u32 column | B: full pass (cold) | A: full view build | A: view_idx on disk |
|---|---|---|---|---|
| 100M | 0.4GB | ~0.1–0.5s | ~1–2 min bg | ~3–5GB |
| 1B | 4GB | ~1–3s | ~10–20 min | ~30–50GB |
| 10B | 40GB | ~10–30s (disk-bound) | hours | ~300GB+ |

And multi-tags multiply: a multi-tag level at avg 3 tags + ancestors makes the
membership count 5–10× the row count. At 10⁹ base rows a *globally* expanded level is
10¹⁰ memberships — global expansion must simply never happen at this scale, in either
design (both already expand per-partition; at billions that stops being an optimization
and becomes the only legal mode).

**Where B dies.** B's contract is "O(N) once per view open, then memory-speed". That
contract fails twice, at different points:

1. **~0.5–2B**: the *view buffer* (4B/membership) plus the touched columns exceed RAM.
   mmap keeps it *correct* (OS pages in/out), but every filter pass becomes a full
   sequential disk scan: open-a-view latency drifts from 0.1s to 10s+. Mitigable —
   only view-relevant columns touched, zone-maps per column chunk to skip pages,
   filter caching — but the O(N)-per-view-open term is structural.
2. **~10B**: single columns (40GB) rival the disk budget; even one cold pass is ~10s+
   of pure I/O. No in-process trick survives this: **B is out as the global engine.**

**Where A survives — and what it costs.** A's interactive path is O(log N + K) B-tree
seeks: at 10⁹ that's one extra tree level, still sub-millisecond warm. The *query
shape* — seek into a prebuilt ordering, never scan — is the only shape that works at
billions. But A's own O(N) terms must be amputated:

- **Full per-view builds become unpayable** (minutes–hours, tens of GB per view spec).
  Anchor-first partial building stops being a warm-up optimization and becomes the
  permanent regime: only visited partitions of `view_idx` ever exist; LRU evicts cold
  partitions; the "background debt" is simply never paid in full.
- **Exact counts die with the full build.** Scrollbar geometry and group counts move
  permanently to *estimates*: a persistent ~1M-row uniform sample table (with weights)
  answers any group-by/filter count in milliseconds at ±1–3%; visited groups get exact
  counts from their built partitions. The progressive-counts machinery of §3 stops
  being a transition state and becomes the steady state.
- **SQLite itself becomes the bottleneck** before the design does: single-threaded
  query execution, one writer, O(G) range counts (a 100M-row group counts in minutes
  cold). At ~1B+ the same design wants an OLAP substrate under the same protocol:
  sorted Parquet/DuckDB (or columnar files + DataFusion) where a grouped aggregate
  over 10⁹ rows is a 1–3s parallel scan and prefix ranges prune via row-group
  zone-maps. Nothing above §4 changes — spine, gids, cursors, anchor-first — only the
  storage engine answering the range scans.

**The convergence point.** At billions the two designs stop being alternatives and
become the two halves of one system: an **A-shaped outer tier** (global ordering,
seeks, sampled counts, partial partitions on disk) that *feeds* a **B-shaped inner
tier** — the anchored partition (the 1–10M rows around the viewport / the open branch)
pulled into the in-memory columnar engine, where scrolling, regrouping and re-sorting
of the visible zone run at memory speed. The protocol of §4 already permits this: the
UI seeks by gid; whether the chunk came from a B-tree page or a resident column is
invisible.

Rule of thumb for when each is "the only option":

- **≤ ~100M**: B alone, as specified in §6. A is an optimization, not a need.
- **~100M–1B**: B still primary if RAM ≥ columns + view buffer; A (partial builds +
  estimates) otherwise. Pick per machine at `open()` time, not per codebase.
- **~1B–10B**: A's shape is mandatory (seek-only interaction, sampled counts, partial
  materialization); B survives only as the inner zone engine. Plain SQLite is at its
  limit — plan the OLAP substrate.
- **> ~10B**: single-desktop assumptions (one NVMe, one process) are the binding
  constraint, not the design — that's server/cluster territory, where the same
  protocol fronts a remote engine.

The sentence to keep: **define the total order, give every prefix a stable hash, and
make iteration a seek — then "the tree" is just cursor bookkeeping, in whichever engine
holds the bytes.**
