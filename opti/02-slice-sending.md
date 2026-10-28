# 02: Tree slices, and many collections on one backend

Status 2026-10-20: design. It builds on [01-collection-manager.md](01-collection-manager.md).
Numbers come from `bench/collection` (`./wire.sh 1000000`, report in
`results/wire/report-1000000.md`).

## 1. Principle

The backend owns the **resulting tree**: groups from `groupBy`, the cluster overlay, custom
groups, the leftover bucket, sha1 piles, scores and selection. The UI asks for a **slice** of
that tree, a contiguous piece of it in display order with everything needed to draw it. The UI
builds the scroller lines from the slice and fits them to the screen.

So the split is:

| backend | UI |
|---|---|
| what is shown, in which order: the tree and every overlay | how it is shown: lines, images per line, sizes, heights |
| one slice format for every kind of group and position | header lines, image lines, pile lines, card lines, grid rows |
| answers "what is at entry `pos`" and "which entry starts line `L` under this line rule" | width, zoom, measured rows; turns pixels into lines and lines into entries |

The backend never sees a pixel. A resize, a zoom or a measured grid row is handled locally, with
no round trip.

What it costs per scroll at 1M images (server encode + JSC decode, no transport):

| | bytes | time |
|---|---:|---:|
| today: 7 full columns | 156.6 MB | 1.55 s (≥) |
| 200 images, 7 properties, JSON columns | 20 KB | 61 µs |
| 500 images, 7 properties, JSON columns | 50 KB | 155 µs |
| tree page with headers, 500 images, JSON columns | 55 KB | 193 µs |

## 2. Entries: a layout-free coordinate

The visible tree is flattened into **entries** in display order (DFS):

- a group's **header** is one entry, for every group whose parent chain is open;
- an open leaf contributes one entry per **position**: an image, or a pile in sha1 mode;
- a closed group contributes only its header.

An entry has a global ordinal `pos` in `[0, total)`. It does not depend on the screen. A view
(note 01 §3) has a `viewRev` that changes when open/closed changes the entry list. `rev`
changes when the result changes. A slice is addressed by `(rev, viewRev, pos range)`.

## 3. The tree slice

### 3.1 Request

```
tree.slice { req, key, rev, viewRev, ns, props: [propId...],
             chunks: [c0, c1, ...],   // chunk c = entries [c·256, (c+1)·256)
             images: true }           // false = headers only (see §4.2)
```

- Entries are grouped into aligned **chunks** of 256. The cache key is `(rev, viewRev, chunk)`,
  so overlapping requests and partial hits never happen.
- `props` = the properties the view draws. The image wall needs no property (the thumbnail
  comes from `sha1`); the grid needs its visible columns. A project with 60 properties does not
  send 60 columns.
- The server answers from the result with that `rev`, as long as it is alive (§6.6), so a
  slice always matches the chunks next to it.

### 3.2 Reply

Groups and position runs, in display order, as JSON columns. The bench shows a column layout is
25% smaller and 30% faster to decode than row objects, and `JSON.parse` decodes as fast as
msgpack in JSC.

```json
{ "req": 41, "rev": 7, "viewRev": 3, "chunk": 812, "from": 207872, "to": 208128,
  "context": [ {"id": 2, "depth": 1, "kind": "property", "value": "nomovi", ...} ],
  "groups": [ { "pos": 207880, "id": 1997, "parent": 2, "depth": 2,
                "kind": "property", "value": 2015, "name": null,
                "total": 31, "visible": 31, "masked": 0, "selected": 3,
                "closed": false, "score": null, "cluster": null } ],
  "runs":   [ { "pos": 207881, "group": 1997, "start": 0, "count": 31, "leafCount": 31,
                "ids": [...], "sha1": [...], "selected": "base64 bitset",
                "piles": null, "scores": null,
                "cols": { "3": [...], "7": [[1, 5], null, ...] } } ] }
```

- `context`: the ancestors of the first entry, so the UI can draw indentation and sticky
  parent headers for a chunk that starts deep in a group.
- `kind`: `property | cluster | custom | leftover | all`. The cluster overlay and custom
  groups arrive as ordinary groups with their metadata (`cluster: {function, inputs}`,
  `masked`, `visible`). The UI does not need to know how the overlay was built.
- `start` / `leafCount`: where the run sits in its leaf. The UI places it on the leaf's lines
  (§4.1).
- `piles` (sha1 mode): one record per position: `{size, ids?}`. `ids` only when the pile is
  open.
- `scores`: per image when a similarity search is active. `groups[].score` per group.

### 3.3 Client loading

- **Prefetch**: chunks of the viewport, one screen ahead in the scroll direction, half a screen
  behind.
- **Fast scroll** (scrollbar drag, page down): draw placeholders and request only the latest
  viewport, once per frame. Chunks skipped over are never requested.
- **One batch in flight per view.** New needs while it is in flight are merged into the next
  batch, and chunks that leave the prefetch area before being sent are dropped from it.
- **Cache**: LRU over chunks, capped (e.g. 100 chunks ≈ 25k entries ≈ 2.5 MB). Thumbnails keep
  their own HTTP cache by sha1, as today.

### 3.4 Server

`tree.slice` reads the published `Arc<CollectionResult>`. It never queues behind a recompute and
is answered on a blocking thread (µs of work). For each view, the server keeps the visible
groups with their first `pos` in a prefix array, so finding the group at a `pos` is a binary
search. The array is rebuilt on every `viewRev`, in µs for thousands of groups and ms for 1M.
Per view, a newer `tree.slice` request replaces an older one that has not started yet.

## 4. Building the scroller from slices

### 4.1 Lines

The UI owns a **line rule**: positions per line for each depth (from the width and image size),
and the height of a header, an image line, a pile line and a card line for each depth. It is the
same arithmetic `treeLines.ts` and `cardLineSize` do today. A leaf with `leafCount` positions
has `ceil(leafCount / perLine(depth))` lines, and line `k` shows positions
`[k·perLine, (k+1)·perLine)`. A run is placed on those lines from its `start`. A line whose
positions are not all cached yet is drawn with placeholders for the missing cells.

On resize the rule changes, the lines are rebuilt locally from the cached chunks, and the
scroll anchor (first visible entry) is kept.

### 4.2 Scroll height and seeking

A virtual scroller needs the total height, and the entry at any pixel (scrollbar drag, restore
a position, scroll to an image). Slices alone do not give that. Two modes:

**Small tree** (visible groups ≤ a threshold, ~20k, which covers most projects): the UI asks once
per `viewRev` for `tree.slice {images: false}` over all chunks. That is every group entry with its
counts and no images, about 50 B per group in JSON. With it, the UI builds the full layout
locally. `ScrollLayout` (`components/scrollers/virtual/scrollLayout.ts`) already does exactly
this in O(groups), including measured grid rows, through its `LayoutSource`. Images then
come by chunk. No seek request is ever needed.

**Large tree** (e.g. grouping by text, ~N groups):

- The **summary** of each `viewRev` carries layout stats: for each depth, the header count and
  a histogram of open-leaf position counts `[[count, leaves], ...]`. The UI computes the exact
  number of lines for any rule as `Σ leaves · ceil(count / perLine)`, and from it the total
  height. The histogram is small: distinct leaf sizes that add up to at most E positions are at
  most √(2E), about 1.4k at 1M.
- `tree.seek {key, rev, viewRev, rule: perLine[], line}` → the `pos` that starts line `line`,
  and `tree.seek {..., pos}` → its line. The server evaluates the same division the UI uses,
  over the view's prefix array. It does not build lines: it only converts between lines and
  entries. The rule is a few numbers, re-sent on resize.
- The UI turns pixels into lines with its line heights. With measured grid rows, unmeasured
  lines use the estimate and the anchor is corrected after measuring, as `ScrollLayout` does
  for a measured leaf.

### 4.3 Opening and closing groups

`view.setOpen {groups, open}` bumps `viewRev` and replies with the entry ranges that appeared
or disappeared (`inserted [pos, n]` / `removed [pos, n]`). The UI shifts its cached chunks
instead of refetching them. In the small-tree mode it also gets the header entries of the
opened groups. The result and `rev` do not change.

## 5. Navigation without a tree in the UI

- **Position** = `pos`, or `(groupId, index)` inside a leaf.
- `locate {key, rev, viewRev, id}` → `pos` (scroll to image, preview). If the image is in a
  closed group, the reply says which groups to open.
- `step {key, rev, viewRev, from, by: image|group, dir}` → `pos`, for keyboard navigation and
  preview next/previous across group borders. The UI answers it locally when the target is in a
  cached chunk.
- Shift-click range selection sends the two `pos`. The server selects the display-order range
  between them.

## 6. Invalidation

| event | server push | UI |
|---|---|---|
| new result (state change, structural delta, cluster op) | `result {key, rev, viewRev, summary, reason}` | fetch the viewport chunks for the new `rev` (+ group entries in the small-tree mode); keep drawing the old rev until they arrive, then swap in one frame; keep the scroll anchor with `locate(firstVisibleId)` (nearest group when it is gone) |
| value change on properties this collection does not filter/sort/group by | `values {key, ids, cols}` when ≤ 5k ids, else `stale {key, props}` | patch cached runs / refetch visible chunks for those props; same rev |
| selection op | reply `{ns, selRev, counts}` | ids ops: patch bits in cache; group / range / all ops: refetch `selected` of cached chunks (bits only) |
| own property edit | (one of the two above) | optimistic: an overlay `{id → value}` applied over the cache until the push confirms |

Rule: a push never carries entries the UI did not ask for. It only says what changed, and the
UI pulls what it shows.

## 7. Many collections, one backend

### 7.1 Who opens collections

A tab's main collection, its panels (recommendations, selection modal with
`filterBySelection`, cluster scroller), several windows on the same tab, and in the browser
deployment several clients. All of them live in one process, on one store per project.

### 7.2 Registry

```
Engine (per project)
 ├─ store: ArcSwap<Snapshot>                         shared columns + per-snapshot caches
 ├─ collections: RwLock<FxHashMap<CollectionKey, Arc<CollectionSlot>>>
 │    CollectionSlot { state: Mutex<State>, result: ArcSwap<CollectionResult>,
 │                     job: Mutex<Job>, views: Vec<ViewId>, active_views: u32, last_access }
 └─ views: per connection, ViewId → { key, open groups, viewRev, entry prefix, props, ns, outbound queue }
```

- `CollectionKey = { tab_id, name }`. Two views of the same key (same tab in two windows)
  share the collection, because the state is the tab's. Each view has its own open/closed set
  and properties.
- **Selection is per user session**, not per collection. Today `global` in `columnStore` is
  shared by every tab of the client. The bitsets live on the session, and a view names the
  namespace it reads.

### 7.3 Scheduling

- **One rayon pool per process**, sized to the cores. A collection job is itself parallel, so
  running many at once only oversubscribes: at most 2 collection jobs run at a time.
- **Two queues**: *interactive* (a collection with an active view, or one a user op targets)
  and *background* (dirty hidden collections, cache warm-up). A new interactive job cancels a
  running background job, which goes back to its queue.
- **Per collection**: one running job and one pending state. A newer `setState` replaces the
  pending one and merges the reload kind (max, as `maxReloadKind` does today), then cancels the
  running job if the new kind restarts at an earlier stage.
- Reads (`tree.slice`, `tree.seek`, `locate`, `step`, selection counts) never enter the queues.

### 7.4 Deltas across collections

`apply_delta` returns `Changes`: the changed slots and their properties. For each collection:

- none of its filter/sort/group properties touched → a `values` push to its views, no
  recompute;
- touched and active → interactive incremental job (note 01 §5.4);
- touched and hidden → marked dirty only, recomputed when a view activates it (what
  `setDirty` + `runState.active` do today).

### 7.5 Sharing work

- Per snapshot, shared by all collections: loaded columns, pre-lowered dictionaries, sort key
  columns, tag expansions.
- **Stage cache** keyed by the hash of the state prefix: `(snapshot, active set, filter)` →
  filtered, `+ sort` → sorted. It holds weak references, so a stage lives only as long as some
  result uses it. Two tabs with the same filter compute it once. The main collection and the
  modal collection of the same tab share their snapshot and columns anyway.

### 7.6 Memory

What a result keeps at 1M (bench): sorted order 4 MB, filtered mask + slots ≤ 4 MB, group tree
15–45 MB (90 MB grouping by text). A result also pins its snapshot, but a delta copies only the
columns it touched, so an old snapshot costs only those columns.

- Budget: configurable, with a default to set (e.g. 1 GB or a share of RAM).
- Over budget: drop the **results** of collections with no active view, least recently used
  first. Their state stays. Reactivating one recomputes it (20–200 ms at 1M; the worst case is sort + group by text), with the summary
  of the dropped result shown meanwhile.
- A result asked for by an in-flight `tree.slice` (§3.1) is kept alive by that request. Past that, a
  request for a rev that is gone gets `gone {rev}` and the front moves to the current rev.
- Columns no collection has used for a while can be unloaded (optional, later).

### 7.7 Lifecycle

- A view is created by `view.open` and removed by `view.close` or the connection's end.
- A collection with no views stays alive for a grace period (60 s, so a page reload finds it
  warm), then it is closed.
- Each connection has one outbound queue. Pending `result` pushes for the same collection
  collapse to the latest rev, and slice replies the client has superseded are dropped.

## 8. The exception: the map

`MapView` draws every point. It gets one binary frame per rev: ids u32 + x, y f32 + group
colour u16, 14 B × N = 14 MB at 1M. It is decoded for free and uploaded as is. Values on hover
come through the same property columns as a slice. Tiles or level of detail only if 10M+ makes
the frame too large.

## 9. Implementation steps

Backend (note 01 §7 steps 6–8):

1. Entry flattening per view (prefix array over visible groups), `tree.slice` with every group
   kind and overlay, layout stats, `tree.seek`, `locate`, `step`. Tests: slices concatenated
   over all chunks equal a brute-force DFS of the tree, overlays included; seek and the stats
   line count agree with a brute-force line build for random rules.
2. Registry, views, scheduler with both queues, coalescing, stage cache, memory budget and
   eviction. Tests: cancel latency, eviction order, interactive before background.
3. The WebSocket messages and pushes of §3–§6, documented in
   `technical_docs/rust_port/VIEW_PROTOCOL.md`.

UI (note 01 §7 step 9):

4. Chunk cache + per-view request batcher + prefetch + placeholders.
5. Small-tree mode: a `LayoutSource` over the header entries, so `ScrollLayout` and the line
   builders (`treeLines.ts`, `gridLines.ts`) keep working, reading positions from cached runs.
   Switch the image wall, `TreeScroller`, `GridScroller` and `ClusterScroller`.
6. Large-tree mode: total height from the stats, pixel → line → `tree.seek`, anchor correction
   for measured rows.
7. Rev swap with anchor restore, `values`/`stale` pushes, optimistic overlay, selection bits.

Measurement:

8. `bench/collection`: end-to-end `tree.slice` latency through the socket (localhost and
   Tauri), and a scripted scroll at 1M: chunks fetched, bytes, frames over 16 ms, in both modes.

## 10. Open questions

- The thresholds: small vs large tree (~20k groups?), incremental vs full recompute (~1%?),
  chunk size (256 entries?), cache cap, memory budget default. Set them from step 8.
- Can the large-tree mode replace the small-tree mode everywhere, so there is one code path?
  It costs a `tree.seek` round trip per scrollbar jump.
- Do card lines and grid rows need anything else in the line rule (rows per property under a
  card, multi-line text)? Measured rows are local either way.
- Should a hidden collection with a cheap state (no grouping) recompute in the background right
  away instead of on activation?
- Browser deployment: is one rayon pool shared fairly between users, or do we need a per-user
  share?
