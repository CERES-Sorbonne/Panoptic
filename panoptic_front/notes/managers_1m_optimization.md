# Filter / Sort / Group Managers — Analysis & 1M-Image Optimization

## Current Architecture

The three managers form a pipeline:

```
DataStore (all instances)
    ↓ FilterManager.filter()
  filtered Instance[]
    ↓ SortManager.sort()
  sorted Instance[]
    ↓ GroupManager.group()
  GroupTree (hierarchical, rendered by virtual scroller)
```

Each stage works synchronously on the full dataset on the main thread. CollectionManager orchestrates them and fires events downstream.

---

## FilterManager — Bottlenecks

### What it does
1. Optional text query search (linear scan of all string/tag properties per image)
2. Folder inclusion filter (Set lookup — cheap)
3. Recursive `FilterGroup` evaluation — sequential AND/OR chains

### Critical problems at 1M

| Problem | Location | Cost |
|---|---|---|
| `values = instances.map(i => i.properties[p.id])` | `applyFilter` L289 | Allocates 1M-element array per filter |
| `new Date(v)` for every image value | `applyFilter` L303 | 1M Date object allocations per date filter |
| `v.toLowerCase()` for every image value | `applyFilter` L311 | 1M string allocations per string filter |
| `valid`, `reject`, `test` arrays duplicated per filter group | `applyGroupFilter` L328 | Peak memory ≈ 3× image list size |
| Text search: inner loop over all textProps × tagProps per image | `filterByText` | O(n × props) with no short-circuit optimisation |
| Full re-filter on every state change | `update()` | Repeats work even when only 1 filter changed |

### Quick wins
- **Inline value access**: remove the `values = instances.map(...)` intermediate array. Compute `value = instance.properties[property.id]` inside the loop directly, removing 1M-element allocation per filter.
- **Pre-compute transformed filter values once** (lowercase, Date) before iterating images — currently done correctly for `filterValue` but not for the per-image values. Instead, compare lazily with early exit: `(operatorFunc(transformOnce(instance.properties[p.id]), filterValue))`.
- **AND short-circuit**: `applyGroupFilter` with AND already shrinks `test`, which is good. Extend this to bail out of the outer loop early if `test` becomes empty.
- **Typed bitset for filter results**: instead of `valid[]` / `reject[]` Instance arrays, maintain a `Uint8Array(instanceCount)` bitmask. Passes and fails become bit flips; merging AND/OR becomes bitwise AND/OR. Allocate once, reuse.

---

## SortManager — Bottlenecks

### What it does
1. `getSortableImages()` — builds `SortableImage[]` with parsed sort keys per property
2. `sortSortable()` — JS `.sort()` with multi-key comparator
3. `insertSort()` / `quadraticFindIndex()` — incremental re-sort for updates (binary search + linear tail)

### Critical problems at 1M

| Problem | Location | Cost |
|---|---|---|
| Creates 1M `SortableImage` objects `{ imageId, values: [] }` | `getSortableImages` L197 | 1M object + 1M inner array allocations |
| `sortParser[type](value)` called 1M times per sort property | `getSortablePropertyValue` L111 | Redundant parsing on every sort call |
| JS `.sort()` on array of objects — not cache-friendly | `sortSortable` L127 | Comparator receives object refs, indirect memory access |
| Full re-sort after any filter change passes new image list | `CollectionManager` | Cannot reuse previously computed sort order |
| `useDataStore()` called inside `getSortableImages` per batch | L199 | Minor but repeated store resolution |

### Quick wins
- **Precompute and cache sort keys**: maintain a `sortKeyCache: Map<propId, Float64Array | string[]>` keyed by `(propId, direction)`. Invalidate only when a property value changes, not on every sort call. For 1M images × 1 sort property, a `Float64Array(1M)` is 8 MB — cheap. JS `.sort()` on a parallel index array with TypedArray keys is dramatically faster.
- **Sort index instead of Instance[]**: maintain an `Int32Array` of image IDs as the sort result rather than `Instance[]`. Resolving to `Instance` for rendering is done on-demand and only for the visible window.
- **Incremental update is already good** — `insertSort` with binary search is the right approach. Its correctness depends on the precomputed sort key cache above.

---

## GroupManager — Bottlenecks

### What it does
1. `computePropertySubGroup()` — assigns every image to property-keyed groups
2. Builds `GroupValueIndex` (nested Maps) to deduplicate group keys
3. Stores `images: Instance[]` at every group node (including non-leaf nodes)
4. `sortGroupImages()` per group after rebuild
5. `computeImageOrder()` — full iterator traversal to assign absolute image order
6. `saveImagesToGroup()` — builds reverse index `imageToGroups: { imgId → groupId[] }`

### Critical problems at 1M

| Problem | Location | Cost |
|---|---|---|
| `Instance[]` references stored at every group level | `Group.images` | Root holds 1M refs; leaf groups hold subset — 2× duplication |
| `[...group.key, keyValue]` spreads array per image per property | `computePropertySubGroup` L1066 | 1M array allocations per grouping level |
| `new Set()` + `tag.allParents` expansion per image for tag-type properties | L1048 | 1M Set allocations when grouping by tags |
| `sortGroupImages(group, order)` called for every group in the index | L526 | Redundant sort for non-leaf groups; each leaf sort is O(k log k) |
| `computeImageOrder()` creates an `ImageIterator` per step | L577 | Creates iterator objects for 1M images |
| `removeImageToGroups`: `indexOf` on `imageToGroups[img.id]` arrays | L1101 | O(group-count) per image during updates |
| Full rebuild `group()` called on every filter or sort change | | O(n) across 1M images every time |

### Quick wins
- **Don't store images in non-leaf groups** (groups with Property children): they are fully redundant — the leaf groups cover all images. Remove `group.images` from parent nodes; compute group image count by summing children. This alone halves memory.
- **Store image IDs (`number`) not `Instance` references in groups**: resolving `Instance` from ID is O(1) via `dataStore.instances[id]`. Cuts group image array memory by 2–4× on 64-bit depending on Instance object size.
- **Pre-bucket images by property value before tree construction**: scan images once into `Map<value, imageId[]>`, then build the group tree from the map entries. Eliminates per-image key array creation and nested Map traversal.
- **Reuse `tagWithParents`** — it's already computed outside the image loop in `computePropertySubGroup`. The same logic in `addInstanceToGroups` recomputes it inside the image loop — move it outside.
- **Replace `imageToGroups` array indexOf with Set**: `imageToGroups: { imgId → Set<groupId> }` gives O(1) deletion instead of O(n) `indexOf`.

### Date grouping — eliminate `Date` objects from the hot path

`closestDate()` is called once per image in `computePropertySubGroup`. It currently allocates **2 `Date` objects + 1 ISO string per image** — 3M short-lived objects for 1M images.

The bucket key is ultimately a group identity value. It does not need to be a `Date` or string — it just needs to be a number that is equal for images in the same bucket and sortable.

**Sub-day units (Second, Minute, Hour, Day, Week):**

`DateUnitFactor` for these units is already in seconds; multiplied by 1000 gives milliseconds. The bucket is pure integer arithmetic on the epoch-ms value stored in the column:

```ts
function dateBucketKey(epochMs: number, stepSize: number, unit: DateUnit): number {
    const stepMs = stepSize * DateUnitFactor[unit] * 1000
    return Math.floor(epochMs / stepMs) * stepMs   // epoch ms of bucket start — no Date needed
}
```

**Month:** represent as `year * 12 + month` — a naturally sortable integer:

```ts
function monthBucketKey(epochMs: number, stepSize: number): number {
    // one Date only to extract year/month — but see note below
    const d = new Date(epochMs)
    const monthIndex = d.getUTCFullYear() * 12 + d.getUTCMonth()
    return Math.floor(monthIndex / stepSize) * stepSize
}
```

**Year:** just the UTC year integer:

```ts
function yearBucketKey(epochMs: number, stepSize: number): number {
    const year = new Date(epochMs).getUTCFullYear()
    return Math.floor(year / stepSize) * stepSize
}
```

Month and Year still call `new Date()` once to extract year/month from epoch ms — but with the columnar date store (dates stored as `Float64` epoch ms), these calls happen only for **unique date values** encountered during the scan, not once per image. In practice that means tens to hundreds of `Date` objects instead of 1M.

The group key becomes a plain `number` in all cases. The ISO string key (`keyValue.toISOString()`) is eliminated entirely. Display components convert the integer key back to a human-readable string at render time (`new Date(key).toLocaleDateString(...)`) — once per group header, not per image.

| Unit | Bucket key | `Date` allocs per 1M images (now) | After |
|---|---|---|---|
| Second / Minute / Hour / Day / Week | epoch ms (`number`) | 2M | **0** |
| Month | `year×12+month` (`number`) | 2M | **~unique months** |
| Year | year (`number`) | 2M | **~unique years** |
| Group key string | eliminated | 1M ISO strings | **0** |

---

## DataStore Storage Layer — Root Cause Analysis

### Current layout (row-oriented)

```
Instance (JS object, ~100 bytes V8 overhead)
└── properties: { [propId]: any }   ← another JS object per instance + V8 hash table
    ├── 3: "some string"            ← boxed string pointer
    ├── 5: 42.0                     ← boxed number (heap double or Smi)
    └── 8: [1, 3, 7]               ← array object + boxed ints

instances: { [id]: Instance }       ← hash map over 1M entries
```

For 1M images × 20 properties: **~300–500 MB in JS object overhead alone**, before counting actual values. Every filter, sort, or group operation must traverse this scattered object graph — random memory access, defeating CPU prefetching.

### Columnar layout proposal

One flat typed array per property, indexed by a compact **slot** (0-indexed integer, not the instance ID):

```ts
// Slot management — O(1) lookup both ways
instanceSlot: Map<instanceId, slot>   // id → column index
slotToId:     Int32Array              // column index → id

// Per property, pick the matching column type:

numberColumn[propId]: Float64Array(1M)
// numbers, dates-as-epoch-ms, width, height, color
// NaN sentinel for "not set"
// 8 MB per property — contiguous, CPU-prefetchable

boolColumn[propId]:   Uint8Array(1M)
// checkboxes; 0=false, 1=true, 255=not set
// 1 MB per property

stringColumn[propId]: (string | null)[]
// text, path, url — strings can't escape the JS heap
// similar cost to now, but at least pointer-array is sequential

// Tags: CSR (Compressed Sparse Row) — same format used in sparse matrices
tagColumn[propId]: {
    offsets: Int32Array(1M + 1),  // offsets[slot]..offsets[slot+1] = tag range for slot
    values:  Int32Array,          // all tag IDs concatenated
}
// empty slot: offsets[i] == offsets[i+1]
// slot i has tags: values[offsets[i] .. offsets[i+1]]

// Inverted index for tags — built once on load, maintained incrementally
tagInverted[tagId]: Int32Array    // sorted slot indices of all images with this tag
```

### Why contiguous memory matters

`instances.map(i => i.properties[propId])` — current filter inner loop — does 1M random heap reads (one per Instance object) + 1M hash-table lookups (`properties[propId]`).

`numberColumn[propId][slot]` — a sequential scan of 8 MB of contiguous `Float64Array`. The CPU prefetcher loads 64-byte cache lines (8 doubles at a time) automatically. The entire column fits comfortably in L3 cache on modern hardware.

For numeric/date filters the difference is: **memory-random-access-bound (slow) → L3-cache-bound (fast)**.

### Tag inverted index — the big win for tag filters

```ts
tagInverted[tagId]: Int32Array   // sorted slot indices
```

| Operator | Current | With inverted index |
|---|---|---|
| `containsAny([3, 7])` | O(n × 2) scan | Sorted merge of `tagInverted[3]` ∪ `[7]` → O(result) |
| `containsAll([3, 7])` | O(n × 2) scan | Sorted intersection → O(min size) |
| `containsNot([3])` | O(n × 1) scan | Complement of `tagInverted[3]` → O(n) but no inner loop |

Update cost on property change: remove/insert slot from sorted `Int32Array` — O(k log n) per changed image.

### What columnar storage does NOT help

- `string like` / regex: strings can't be TypedArrays; O(n) scan is unavoidable
- Sparse properties (90% of images have no value): columns still allocate 1M slots. Mitigate with a `Uint8Array` presence bitmask per property (125 KB each)

### Memory comparison at 1M images, 20 properties

| Storage | Memory |
|---|---|
| Current row-dict overhead | ~300–500 MB |
| Columnar: 5 numeric × Float64Array(1M) | 40 MB |
| Columnar: 10 tag properties (CSR, avg 3 tags/image) | ~160 MB |
| Tag inverted index (avg 1000 images/tag × 500 tags) | ~2 MB |
| **Net saving** | **~300 MB + dramatically better cache behavior** |

### Migration strategy — dual write, no breaking change

`Instance.properties` is referenced throughout display components and editors. Rather than a big-bang rewrite:

1. In `importInstanceValuesArray`, `importImageValuesArray`, `importFileValuesArray` — these already iterate values in bulk. Populate the column store alongside the existing `instance.properties[propId] = value`.
2. Refactor FilterManager, SortManager, GroupManager to read from columns.
3. Display components, property editors, all other consumers continue reading `instance.properties` unchanged.
4. In `applyCommit`, update both stores on every property change.

No change to the public API of the store. Migration can be done manager by manager.

---

## Architectural Proposals — Ranked by Impact

### Why Backend SQL Offloading Would NOT Help Here

The intuitive argument — "SQLite with indexes beats a JS scan" — breaks down for this data model for two reasons:

**1. The data is already in memory on the frontend.**
The dataStore loads all instances upfront. An in-memory scan beats a SQLite read + serialization + HTTP round-trip for every interactive operation (live filter typing, sort change, group toggle). The network overhead alone adds 10–100 ms per interaction.

**2. Property values resist SQL indexing.**
Properties use an entity-attribute-value pattern: `instance.properties[propId]` can be a number, string, date, or `number[]` (tags). In SQL this maps to either a JSON column (no index on extracted values) or an EAV table `(instance_id, property_id, value text)` (index only useful for exact/prefix string matches). Tag containment (`containsAny([3, 7, 12])`) cannot be expressed as a single B-tree lookup at all — it requires a junction table `(instance_id, tag_id)` with separate index scans per tag, then a set union.

**When backend offloading WOULD make sense:** only if combined with never loading 1M items into the frontend at all (full cursor-based pagination, partial dataStore). That changes the problem from "optimize 1M-image computation" to "never hold 1M images client-side" — a much larger architectural shift.

---

### 1. Precomputed Inverted Indexes per Property (highest impact, medium work)

This is the approach used by search engines (Lucene) and columnar databases (DuckDB). Build typed per-property indexes once on load, invalidate incrementally on data changes.

```ts
// Numeric / date properties — sorted parallel arrays
numberIndex[propId] = {
    values: Float64Array,   // sorted property values, length = instanceCount
    ids:    Int32Array,     // imageId at each position
}
// filter >= X: binary search → O(log n) to find cutoff, slice ids array

// Tag properties — inverted index
tagIndex[tagId]: Int32Array  // sorted imageIds that have this tag
// containsAny([3,7,12]): sorted merge of tagIndex[3], [7], [12] → O(result size)
// containsAll([3,7]): intersection of tagIndex[3] ∩ tagIndex[7] → O(smaller set)

// String properties — sorted index for prefix/startsWith, full scan for like
stringIndex[propId] = {
    values: string[],
    ids:    Int32Array,
}
```

**Complexity change:**
| Operator | Current | With index |
|---|---|---|
| `number >= X` | O(n) scan | O(log n + result) |
| `containsAny(tags)` | O(n × tags) | O(result) merge |
| `containsAll(tags)` | O(n × tags) | O(min tag size) intersection |
| `string startsWith` | O(n) | O(log n + result) |
| `string like` (regex) | O(n) — unavoidable | O(n) — unavoidable |

For highly selective filters (return < 10% of images) the gain is 10–100×. For unselective filters the index result is close to n and the gain is smaller, but the approach naturally short-circuits AND chains early.

**Maintenance cost**: on property value update for k images, update k entries in the affected index. Index is sorted so insert/delete is O(k log n) — fine for typical write patterns.

### 2. Typed Array Sort Keys + Sort Index (high impact, low effort)

Replace `SortableImage[]` with flat typed arrays cached per property:

```ts
// Built once, invalidated when property values change
sortKeyCache[propId]: Float64Array   // parsed sort key per image slot
sortIndex: Int32Array                // image IDs in sorted order
```

`Float64Array.sort()` with a typed comparator is 5–10× faster than sorting an `Instance[]` with a multi-key object comparator. For multi-property sort, maintain one `Float64Array` per sort key and compose comparisons.

`insertSort` / `quadraticFindIndex` already does the right thing for incremental updates — it just needs the cached keys to avoid reparsing 1M values on each call.

### 3. Web Worker Computation (high UX impact, medium work)

Move all three managers off the main thread. The data is read-only during computation so it can be shared via `SharedArrayBuffer` or transferred as `ArrayBuffer`.

```
Main thread:   UI, Vue reactivity, event emission
               ↕ postMessage (state diffs only)
Worker thread: FilterManager, SortManager, GroupManager
               → returns Int32Array of result image IDs
```

Does not reduce algorithmic complexity but eliminates main-thread jank entirely. The virtual scroller continues rendering smoothly while the worker computes. Pairs well with #1 (inverted indexes live in the worker's memory).

### 4. Incremental / Dirty-Only Recomputation (medium impact, low effort)

`updateSelection()` in all three managers already implements this partially. Make it the primary path:

- Filter change on property P → only re-evaluate images that have property P set (tracked via the inverted index above)
- Sort property change → only rebuild the sort index for the current filtered set, not all 1M
- Group option change → only re-bucket images in affected leaf groups

This is a natural complement to #1 — the inverted index tells you exactly which images are affected by a filter change without scanning all 1M.

### 5. Progressive Rendering (low effort, immediate UX gain)

Even without changing algorithms, process in chunks via `requestIdleCallback`:

```ts
async function filterChunked(images: Instance[], chunkSize = 50_000) {
    let result = []
    for (let i = 0; i < images.length; i += chunkSize) {
        const chunk = images.slice(i, i + chunkSize)
        result.push(...applyGroupFilter(state.filter, chunk, ...))
        await yieldToMain()   // requestIdleCallback or setTimeout(0)
    }
    return result
}
```

The virtual scroller only renders ~100 rows — commit the visible window after the first chunk, continue in background.

---

## Estimated Effort vs. Gain

| Proposal | Effort | Perf gain | Memory gain |
|---|---|---|---|
| Remove intermediate `values[]` array in FilterManager | 1 day | Medium | High |
| Sort key cache (Float64Array) | 2 days | High | Low |
| Store only IDs in groups (not Instance[]) | 2 days | Low | High |
| Pre-bucket grouping (avoid per-image key alloc) | 3 days | High | Medium |
| Progressive chunked rendering | 2 days | High (UX) | None |
| Inverted indexes per property | 1–2 weeks | Very High | Low |
| Web Worker for computation | 1 week | High (UX) | None |

---

## Recommended Sequence

1. **Short term** (days, isolated refactors, no API changes):
   - Inline filter values — remove `instances.map(...)` intermediate array
   - Sort key cache with `Float64Array` — eliminate 1M object allocations per sort
   - Replace `imageToGroups` arrays with `Set` — O(1) deletion
   - Remove `images` array from non-leaf group nodes — halve memory

2. **Medium term** (weeks, higher impact):
   - Inverted indexes per property type — changes filter from O(n) scan to O(result) lookup
   - Web Worker — moves all computation off the main thread

3. **Long term** (only if still insufficient after above):
   - Backend offloading combined with full pagination architecture — never load 1M items client-side. This is the right answer only if the dataset grows beyond what a browser tab can hold in memory (~500 MB practical limit).

---

## Additional Requirements Given the New ColumnStore Design

The proposals above were written against the current row-oriented `Instance.properties` store. With the new ColumnStore (`new_data_store_design.md`) the data layer changes enough that several proposals collapse, several become free, and a few new concerns emerge.

### 1. `requireFullColumn` as a mandatory prerequisite

Every manager run must start with a column fetch for each property it reads. This is already shown in the design doc's `runFilter` sketch, but it has pipeline implications:

```ts
async function run(state: PipelineState) {
    const propIds = [
        ...extractFilterProps(state.filter),
        ...extractSortProps(state.sort),
        ...extractGroupProps(state.group),
    ]
    // Single awaited batch — deduped by the store, fires one request per unloaded propId
    await Promise.all(propIds.map(id => columnStore.requireFullColumn(id)))
    // All three managers now read synchronously — no further await inside hot loops
    filter()
    sort()
    group()
}
```

Waiting at the top of the pipeline means the hot loops in all three managers are fully synchronous. Never await inside a scan loop.

### 2. Slot-based pipeline — replace `Instance[]` throughout

The current pipeline passes `Instance[]` between stages. With the ColumnStore the natural currency is a `Uint8Array` bitmask (one byte per slot, 1 = passes). This eliminates every array allocation in the pipeline:

```
FilterManager  → Uint8Array(slotCount)   bitmask of passing slots
SortManager    → Int32Array              sorted slot indices (subset of passing slots)
GroupManager   → Int32Array per group    slot indices in each group
```

- **FilterManager** writes into a pre-allocated `Uint8Array(slotCount)` and returns it. AND chains are `mask[slot] &= passes`. OR chains are `mask[slot] |= passes`. No `valid[]` / `reject[]` arrays.
- **SortManager** takes the bitmask, collects passing slots into an `Int32Array`, and sorts that index array using pre-built typed key arrays (see §3 below). No `SortableImage[]`.
- **GroupManager** iterates the sorted `Int32Array` from SortManager; slots are already in display order so no per-group sort is needed.

The `deletedMask` from the ColumnStore must be ANDed into the filter bitmask before any manager reads it:

```ts
// First pass, O(n/8) with bitwise if packed, or O(n) byte scan
for (let slot = 0; slot < columnStore.slotCount; slot++) {
    if (columnStore.deletedMask[slot]) bitmask[slot] = 0
}
```

### 3. Sort key cache is now the column itself

The `sortKeyCache[propId]: Float64Array` proposed in the SortManager section does not need to be a separate structure. For numeric and date properties the ColumnStore already holds `columnData[propId].data` as a `Float64Array` indexed by slot. SortManager reads it directly:

```ts
// Build sort index from passing slots
const passing = []
for (let slot = 0; slot < slotCount; slot++) {
    if (filterMask[slot]) passing.push(slot)
}
const sortIndex = new Int32Array(passing)
sortIndex.sort((a, b) => column[a] - column[b])   // column = columnData[propId].data
```

`Float64Array.sort()` with a numeric comparator on an `Int32Array` of ~100k slots is sub-millisecond. The cache invalidation problem from the old design vanishes — the column IS the cache and is already kept fresh by the ColumnStore's commit path.

For string properties the column is `(string | null)[]`. Pre-sort a parallel `Float64Array` of numeric keys via a string hash or interned index if needed; otherwise locale-compare directly (acceptable for <100k filtered results).

For tag properties, grouping order is typically by tag name, not by the raw CSR values. Maintain a `Map<tagId, sortRank>` built once from the tag list (already loaded eagerly) and use it as the key array.

### 4. FilterManager: CSR scan for tag containment + `requireTagInverted`

The inverted index proposal in §Architectural Proposals is partially implemented by `columnStore.requireTagInverted(propId)`. For `containsAny` / `containsAll` operators, call `requireTagInverted` instead of `requireFullColumn` and use the inverted index directly:

```ts
// containsAny([t1, t2]) — union of inverted lists → O(result)
const slots = sortedMerge(tagInverted[t1], tagInverted[t2])
for (const slot of slots) bitmask[slot] = 1

// containsAll([t1, t2]) — intersection → O(min list size)
const slots = sortedIntersect(tagInverted[t1], tagInverted[t2])
for (const slot of slots) bitmask[slot] = 1
```

For `containsNone` / `notContains` the complement is still O(n), but it is a simple bitmask inversion with no inner loop over tags.

When `requireTagInverted` is NOT yet loaded (first call), fall back to the CSR scan from `requireFullColumn`. Both paths write the same bitmask output.

For **text search** (`filterByText`), the hot path is unchanged — it must scan string columns. Pre-lowercase the column once when loaded into the store (store alongside the raw value, or transform in-place if display rendering uses the raw column separately).

### 5. GroupManager: date bucketing is free with Float64Array columns

`closestDate()` currently allocates 2 `Date` objects + 1 ISO string per image. With the ColumnStore, dates are stored as `Float64` epoch ms. The `dateBucketKey` arithmetic from the date-grouping section of this document works directly on those values with zero object allocation. The hot path becomes:

```ts
const dateCol = columnStore.columnData[propId].data   // Float64Array
for (const slot of sortedSlots) {
    const key = dateBucketKey(dateCol[slot], stepSize, unit)
    // key is a plain number — hash into group bucket
}
```

No `new Date()` inside the scan loop. The `Date` constructor is called only once per unique bucket key to build the display label, done outside the scan.

### 6. Incremental update path: `onChange` replaces `dirtyInstances`

The ColumnStore emits `onChange({ propIds, instanceIds })` after every commit. The managers need to adapt their `updateSelection` methods to work with slot indices rather than `Instance` references:

```ts
columnStore.onChange.on(({ propIds, instanceIds }) => {
    const relevant = propIds.some(id => activeProps.has(id))
    if (!relevant) return

    const dirtySlots = instanceIds.map(id => columnStore.slotMap.get(id)!)

    if (dirtySlots.length <= INCREMENTAL_UPDATE_THRESHOLD) {
        // Re-evaluate filter bitmask only for dirty slots — reads sparse[slot] directly
        for (const slot of dirtySlots) {
            const passes = evaluateFilter(state.filter, slot)
            filterMask[slot] = passes ? 1 : 0
        }
        // Sort: remove and re-insert dirty slots using binary search on sortIndex
        sortManager.updateSlots(dirtySlots)
        // Group: rebucket dirty slots only
        groupManager.updateSlots(dirtySlots)
    } else {
        runFullRecompute(propIds)
    }
})
```

`updateSlots` for SortManager is the existing `insertSort` logic, now operating on slot indices and reading key values directly from the typed array column (O(1) per slot, no parsing).

### 7. Web Worker + SharedArrayBuffer — now viable

The original Web Worker proposal required serializing `Instance[]` (structured clone of 1M objects — prohibitively slow). With the new ColumnStore the data is already in typed arrays, which can be transferred or shared:

- `Float64Array`, `Int32Array`, `Uint8Array` columns: transferable as `ArrayBuffer` (zero copy) or shareable via `SharedArrayBuffer`.
- `filterMask`, `sortIndex`, `groupBuckets`: built in the Worker, transferred back to the main thread.
- String columns remain on the main thread; string-based filter and group operations either stay on the main thread or the strings are passed as a flat serialized blob.

The practical split:

```
Main thread:   ColumnStore (owns typed arrays), Vue reactivity, event emission
Worker:        FilterManager, SortManager, GroupManager
               reads from SharedArrayBuffer columns (zero-copy, concurrent-safe for reads)
               writes filterMask + sortIndex into a separate ArrayBuffer
               posts result back as a transfer (not a copy)
```

This requires the ColumnStore to allocate columns in `SharedArrayBuffer` from the start (a one-line change to the allocation site). The Worker computes entirely without touching the Vue-reactive layer.

### 8. What the new design makes redundant

| Old proposal | Status with ColumnStore |
|---|---|
| Separate `sortKeyCache` per property | Superseded — Float64Array column IS the key cache |
| Custom inverted index build on load | Superseded — `requireTagInverted` provides it on demand |
| `instances.map(i => i.properties[p.id])` inline removal | Superseded — column access replaces all property dict reads |
| Store slot IDs not Instance refs in groups | Already enforced — GroupManager receives Int32Array of slots |
| `new Date()` elimination in date grouping | Free — dates are epoch ms Float64 values from the column |

The proposals that remain relevant and require explicit work:
- Slot-based bitmask pipeline (replacing `Instance[]` + `valid[]`/`reject[]` arrays)
- AND short-circuit in the filter scan loop
- Pre-lowercase string columns at load time
- `sortedMerge` / `sortedIntersect` utilities for tag inverted lists
- SharedArrayBuffer allocation site in ColumnStore to unlock the Web Worker path
