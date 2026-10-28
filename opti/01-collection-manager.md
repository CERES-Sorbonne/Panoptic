# 01: Collection manager on the backend

Status 2026-10-20: design, nothing wired yet. `crates/panoptic-engine` has a columnar store
(`store.rs`), the schema (`schema.rs`), filter and sort ports (`filter.rs`, `sort.rs`), JS
semantics (`js.rs`) and cancellation (`cancel.rs`). `lib.rs` is still the cargo template, so
none of these modules are compiled or tested yet. There is no group tree, no piles, no
clusters, no collection object and no protocol.

## 1. Why move it

Today `CollectionManager` (`panoptic_front/src/core/CollectionManager.ts`) runs
filter → sort → group in the webview on `Int32Array`s of column-store slots. Each property
column is first downloaded whole. Measured on 1M synthetic images (`bench/collection`):

| | front today (JSC = webview) | Rust (8 threads) |
|---|---:|---:|
| full op suite (13 filters, 6 sorts, 7 groupings, 1 pipeline) | 22.2 s (V8 18.0 s) | 352 ms |
| search box (text + tags) | 5.5 s | 3.2 ms |
| group by tags (+ parents) | 1.85 s | 34 ms |
| memory retained by a group tree | 364–685 MB (1.2 GB by text) | 15–43 MB (89 MB by text) |
| loading 7 property columns | 157 MB of NDJSON, ≥ 1.43 s ingest | read from SQLite, no JSON |

The JS run at 10M was killed for lack of memory. The front cannot hold large projects, and
every heavy op freezes the UI for seconds. On the backend the same ops run in tens of ms, off
the UI thread, and the front only needs the 0.1–0.4 ms slices it displays (note 02).

## 2. What moves, what stays

Moves to the backend, per collection:

- the active slot set: deleted mask and `filterBySelection`;
- filter (property tree, folders, text query, plugin query scores);
- sort (property keys, score first);
- the group tree: `groupBy`, date steps, group sort options, stable ids through the persistent
  value index, tag parent expansion;
- the sha1 pile overlay, the cluster overlay and custom groups (split, merge, move, rename,
  delete, leftover bucket), and the plugin call that clusters a group;
- selection, one bitset per namespace;
- navigation: what the iterators do today (next/previous image or group, find an image, the
  display position of an id);
- counts and aggregations for charts, and the point arrays for the map.

Stays in the front:

- rendering and the scroller. The UI requests slices of the resulting tree (overlays
  included), builds the header, image, pile and grid lines from them and fits them to the
  screen: width, zoom, measured rows, scroll position. `ScrollLayout`
  (`components/scrollers/virtual/scrollLayout.ts`) keeps doing the pixel layout (note 02 §4);
- the slice cache and prefetching;
- optimistic display of edits until the backend confirms them;
- the tab and collection *state* as the user edits it. It is still persisted with the tab
  (`apiUpdateTabState`), and the backend reads it from there when a collection opens.

## 3. Concepts

- **Store**: one per loaded project, an immutable `Snapshot` of identity and typed columns,
  with `Arc` per column (`store.rs`). Deltas from data.db (our writes, plugin writes caught by
  the sequence poll) produce the next snapshot. Shared by every collection of the project.
- **Collection**: identified by `CollectionKey { tab_id, name }` (`name` = `main`, a panel,
  the selection modal, ...). It holds the state (`CollectionState` + `FilterState` +
  `SortState` + `GroupState` + custom groups and cluster overlay), the computed stages and a
  revision.
- **Stages**: `active → filtered → sorted → tree → piles/overlay`. Each stage is an immutable
  `Arc` value computed from the previous one. A state change recomputes from the first stage it
  affects.
- **Result**: an immutable `Arc<CollectionResult>` = (snapshot it was computed on, stages, rev).
  Every read (tree slice, seek, locate, selection counts) goes to one result, so the ids, order
  and values it returns are consistent with each other. Results are published with `ArcSwap`:
  readers never wait for a recompute.
- **rev**: increases on every published result. Every reply carries it, and the client drops
  replies for an older rev.
- **View**: one client's look at a collection: the open/closed groups, the visible properties,
  the subscription, and the entry list they produce (the visible tree in display order,
  versioned by `viewRev`, note 02 §2). Several views can share one collection (note 02 §7).

## 4. API

### 4.1 Engine (Rust, `panoptic-engine`)

```rust
pub struct Engine { /* store: ArcSwap<Snapshot>, collections: Registry, scheduler: Scheduler */ }

impl Engine {
    pub fn apply_delta(&self, delta: Delta) -> Changes;            // new snapshot, marks dirty collections
    pub fn open(&self, key: CollectionKey, state: CollectionState) -> CollectionHandle;
    pub fn close(&self, key: &CollectionKey);
}

impl CollectionHandle {
    pub fn set_state(&self, patch: StatePatch) -> Pending<Rev>;    // diffs → ReloadKind, schedules, latest wins
    pub fn result(&self) -> Arc<CollectionResult>;                 // lock-free current result
    pub fn subscribe(&self) -> watch::Receiver<Rev>;               // pushed on every publish
    pub fn set_active(&self, active: bool);
    // structural ops on the group tree (one new rev each)
    pub fn cluster(&self, group: GroupId, req: ClusterRequest) -> Pending<Rev>;
    pub fn split(&self, group: GroupId, groups: Vec<CustomGroup>) -> Rev;
    pub fn merge(&self, groups: &[GroupId]) -> Rev;
    pub fn move_images(&self, from: GroupId, to: GroupId, ids: &[InstanceId]) -> Rev;
    pub fn rename_group(&self, group: GroupId, name: &str) -> Rev;
    pub fn delete_groups(&self, target: GroupId) -> Rev;
    pub fn select(&self, ns: &str, op: SelectOp) -> SelectionCounts;
}

impl CollectionResult {
    pub fn rev(&self) -> Rev;
    pub fn summary(&self) -> Summary;                              // totals, group count, scores?, piles?
    pub fn entries(&self, view: &ViewState) -> Arc<Entries>;       // visible tree flattened, per viewRev (note 02 §2)
    pub fn tree_slice(&self, e: &Entries, chunk: u32, opts: &SliceOpts) -> TreeSlice; // groups + runs, overlays included (note 02 §3)
    pub fn stats(&self, e: &Entries) -> LayoutStats;               // per depth: headers + leaf-size histogram (note 02 §4.2)
    pub fn seek(&self, e: &Entries, rule: &LineRule, to: SeekTarget) -> SeekResult; // line <-> entry (note 02 §4.2)
    pub fn locate(&self, id: InstanceId) -> Option<Position>;      // (group, position) — scroll-to, preview
    pub fn step(&self, from: Position, by: Step) -> Option<Position>;   // next/prev image or group
    pub fn selection(&self, ns: &str, group: Option<GroupId>) -> SelectionCounts;
}
```

All compute runs on the engine's rayon pool and takes a `CancelToken`. Async callers
(`panoptic-api`) await a oneshot and never compute on a tokio worker.

### 4.2 Client operations (`panoptic-api`, WebSocket)

One WebSocket per client. Messages carry `{ req, key, ... }`, and the server pushes
`result {key, rev, summary, reason}` after every publish. The wire format and the caching rules
are in note 02. How today's `CollectionManager` maps to the protocol:

| `CollectionManager` today | backend message | notes |
|---|---|---|
| constructor + `col.isReady` watch | `collection.open {key}` | the state is read from the tab; reply = rev + summary |
| `filterManager/sortManager/groupManager.state` watches, `requestReload(kind)` | `collection.setState {key, patch}` | the server derives the reload kind (§5.2); debounce stays client-side (50 ms) |
| `setGroupOption`, `delGroupOption`, `setSha1Mode`, `sortGroups` | `collection.setState` | `sha1Mode` = piles stage only |
| `result`, `version`, `hasResult` | `result` push, `tree.slice` | the UI keeps slices of the tree, never the tree |
| `getGroupIterator`, `getImageIterator`, `findImageIterator` | `tree.slice`, `locate`, `step` | iterators become entry positions: `pos`, or `(groupId, index)` |
| `toggleGroup`, `openGroup`, `closeGroup` | `view.setOpen {key, groups, open}` | bumps the view's `viewRev` (entry list), not the result's `rev` |
| selection (`toggleAll`, `selectImages`, `toggle*Iterator`, `isGroupSelected`, namespaces) | `selection.apply {ns, op}` | ops: ids, group, position range (shift-click), all, none; slices carry selected bits |
| `cluster`, `isClustering`, `clusterError`, `onCluster` | `group.cluster`, `progress` push | the backend calls the plugin, so the run survives the UI |
| `addCustomGroups`, `moveImagesToGroup`, `renameGroup`, `split`, `merge`, `deletePile`, `delCustomGroups`, `clearCustomGroups`, `clusterEmptyBucket`, `drainCluster` | `group.<op>` | one rev per op |
| `updateInstances` / `setDirty` (data listener) | none: the backend applies the delta | value-only changes are pushed as `values` (note 02 §6) |
| `settle()` | await the `result` push with `rev ≥` the op's rev | each op replies with the rev it will produce |
| `setActive`, `dispose` | `view.active`, `collection.close` | the backend keeps or drops the result (note 02 §7) |
| `getRequiredColumns` | none | the backend loads the columns itself |

## 5. Performance strategy

### 5.1 Store

- Columns are loaded from SQLite into typed columns: `f64` for numbers and dates (NaN = none),
  `u8` checkboxes, dictionary strings with a pre-lowercased dictionary, CSR tags. There is no
  JSON per cell. A column is loaded the first time any collection needs it, then shared.
- Derived per-snapshot caches are shared by every collection: the sort key column of a
  property (the expensive part of a sort) and the tag expansion (tag → itself + parents). They
  are rebuilt lazily when a delta touches the column.
- A delta copies only the columns it touches (`Arc` per column). Old snapshots are freed when
  no result pins them anymore.

### 5.2 Staged recompute

The front's reload kinds (`filter > sort > group > sortGroups`) become the stage to restart
from, with two more:

| change | restarts at | kept |
|---|---|---|
| filter tree, query, folders, `filterBySelection` | filtered | — |
| sort keys | sorted | filtered |
| `groupBy`, date step | tree | filtered, sorted |
| group sort options | tree order (re-sort children only) | buckets |
| `sha1Mode` | piles | tree |
| open/closed groups | the view's entry list (`viewRev`) | the whole result, same rev |
| visible properties | nothing | everything (slices just ask other columns) |

### 5.3 Algorithms (all already measured in `bench/collection/rust`)

- filter: one bitmask per leaf, AND/OR on words; string predicates run once per dictionary
  entry, not once per slot; tags through the expansion;
- sort: every key turned into an order-preserving integer, packed with the input position into
  a u64/u128, then an integer sort (parallel for large inputs). Ties keep the input order, as
  in the TS packed key;
- group: stable counting sort into buckets (a bucket keeps the sorted order), dense ids for
  sparse keys, persistent value index for stable group ids, slot → leaves CSR instead of
  `imageToGroups: Map<number, Set>`;
- layout: a prefix array over the visible groups. Any position lookup is a binary search
  (6 µs to rebuild for 3.6k groups).

### 5.4 Incremental updates

A delta gives the changed slots. When they are few (threshold to measure, around 1% of N),
the collection re-tests those slots against the filter, moves them in the sorted order (remove
and insert by key) and between buckets, the same thing `updateSelection` does today in TS.
Above the threshold it recomputes from the filtered stage: at 1M that is 20–50 ms, cheaper
than a long incremental path. Either way the result is a new rev.

### 5.5 Never blocking, latest wins

Each collection has at most one computation in flight. A newer state cancels the older one
through its `CancelToken`, which is checked once per chunk in the parallel loops. Visible
collections get priority over hidden ones (note 02 §7). Tree slices and seeks
read the published result and never wait for a recompute.

### 5.6 Targets (from PLAN P4/P5 gates)

- p95 filter + sort + one grouping < 100 ms at 1M (bench: 19 ms for compound filter > sort >
  tags);
- slice round trip < 5 ms on localhost, with server + decode ≈ 0.1–0.4 ms measured;
- no main-thread task > 50 ms in the front while filtering, sorting, grouping or scrolling.

## 6. Semantics parity

The Rust results must be the same as the TS engine's, including ordering ties, dates, loose
equality and UTF-16 string order (`js.rs`). Checks:

- golden tests: a node harness runs the TS managers on fixture projects and dumps slot lists
  and tree hashes, and `cargo test` compares them. `bench/collection` already does this on
  synthetic data for 27 ops;
- the same fixture runs through the protocol (P4 gate), so the API layer cannot drift.

## 7. Implementation plan

Each step ends green on `cargo test -p panoptic-engine` and does not break the current front.

1. **Make the engine compile.** Declare the modules in `lib.rs`, add unit tests for store,
   filter and sort, and port the TS goldens harness (fixtures in `panoptic_back/test/` or
   `crates/panoptic-engine/tests/fixtures`).
2. **Group tree** (`group/`): port `computePropertySubGroup`, date buckets, group sort options,
   value index, tag parents and scores from `GroupManager.ts` + `core/group/*`. Start from
   `bench/collection/rust/src/group.rs`, which already matches the TS checksums. Goldens.
3. **Piles and overlays** (`group/piles.rs`, `group/overlay.rs`): sha1 piles, the cluster
   overlay, custom groups, the leftover bucket and their ops. Goldens on op sequences.
4. **Store loading and deltas**: fill `Snapshot` from `panoptic-db` (typed reads per property
   mode: id, sha1, file, system properties), apply the sequence deltas, and cache sort keys and
   tag expansions per snapshot.
5. **Collection** (`collection.rs`): state, stages, reload-kind diff, publish through `ArcSwap`,
   cancel, the incremental path with its threshold, and `settle` semantics via revs.
6. **Read API** (`result.rs`, `entries.rs`, `slice.rs`): summary, entry flattening per view,
   tree slices with every group kind and overlay, layout stats, seek, locate, step. Selection
   bitsets and ops (`selection.rs`).
7. **Registry and scheduler** (`registry.rs`): many collections, priorities, eviction
   (note 02 §7).
8. **Protocol** (`panoptic-api`): WebSocket messages of §4.2, pushes, encoding (note 02 §3),
   written down in `technical_docs/rust_port/VIEW_PROTOCOL.md`. Extend `bench/collection` to
   time a slice end to end through the socket.
9. **Front `RemoteCollection`** behind a flag, with a public surface as close to
   `CollectionManager` as possible. Port the views one by one: image wall and `GridScroller`,
   `TreeScroller`, preview navigation, selection, `ClusterScroller`, `MapView`, graph and
   `RecommendView`, which read columns directly today.
10. **Remove** the front compute (`core/FilterManager`, `SortManager`, `GroupManager`,
    `group/*`), the full-column streams and `columnStore` once no view needs them.

## 8. Open questions

- socket.io (parity with today's `socketStore`) or a plain WebSocket for the view protocol.
- Should the open/closed state of groups be per view (today it lives on `Group.view.closed`,
  shared by the views of a tree) and is it persisted with the tab?
- Plugin text search: the backend calls the plugin and keeps the scores per collection.
  Confirm this fits the plugin protocol (P1-D).
- `RecommendView` and the graph view read columns directly. Which aggregations do they need
  from the backend?
