# GroupManager Redesign — Implementation Plan & Open Questions

Related: [[group_tree_structure_redesign]], [[tree_scroller_computelines_optimization]],
[[managers_1m_optimization]]

This note is the **action doc**: current code state vs. design intent, phased plan, and
unresolved questions that must be answered before code can be written.

---

## Resolved Decisions

---

### Q1 — Primary storage: per-leaf arrays (incremental wins)

**Tradeoffs:**

| | Single packed `Int32Array` | Per-leaf `Int32Array[]` |
|---|---|---|
| Access by global pos | O(1) direct | O(log #groups) via prefix-sum |
| Sequential scan | Best — one contiguous buffer, CPU prefetcher loves it | Near-equal — leaf arrays are small; gaps between them are few |
| Insert / remove one slot | **O(n)** — must shift the entire tail | **O(leaf size)** — only the affected leaf changes |
| 1k values change group | Re-pack entire n-slot buffer | Patch only the affected leaves; `orderedIds` cache is rebuilt lazily |
| Full rebuild | O(n) concat | O(n) total across all leaves |
| Memory | 4 MB (1M × Int32) + rowToLeaf 4 MB | Same, split across leaves + `prefixCounts` Int32Array (tiny) |

**Decision: per-leaf is the primary structure.** Each leaf owns its own `Int32Array`. A global `orderedIds: Int32Array` (instance IDs — see Q3) is a derived cache rebuilt lazily before `computeLines` via `TypedArray.set()` calls. Incremental updates patch leaf arrays only; the cache is marked stale and rebuilt at display time.

A `prefixCounts: Int32Array` (one entry per leaf, DFS order, cumulative sum of leaf sizes) enables O(log #groups) binary search for "which leaf does global position p belong to" — needed for cursor arithmetic.

---

### Q2 — Reverse lookup: `Map<instanceId, Set<groupId>>`

**Tradeoffs:**

| | `Map<instanceId, Set<groupId>>` | `Map<slot, Set<leafGroupId>>` | `rowToLeaf` scan (no map) |
|---|---|---|---|
| Lookup by instance ID | O(1) — direct | O(1) but need slotMap first | O(total) — unusable |
| Lookup by slot | need instanceIds[slot] first | O(1) — direct | — |
| Memory | ~100 MB at 1M (Map+Set V8 overhead) | Same | 0 |
| Alignment with leaf storage | natural — leaves store instance IDs (Q3) | mismatch if leaves store IDs | — |
| Incremental maintenance | add/delete per instance change | same | — |

**Decision: `Map<instanceId, Set<groupId>>`** — keeps the existing structure, fixes only `indexOf` → `Set.delete`. Since leaf nodes will store **instance IDs** (not slots, see Q3), this map uses the same currency as the leaf data. The slot-indexed alternative would add an unnecessary translation layer.

The existing `imageToGroups` field is renamed to a `Map` but otherwise stays. Replaces `splice(indexOf)` with `set.delete(groupId)` — O(1) instead of O(groups).

---

### Q3 — Result datatype: instance IDs everywhere in the tree

**Decision:** Leaf nodes store **instance IDs** (not slots). `orderedIds: Int32Array` is the global output. Slots are used only during the computation phase (reading column values to determine group keys), then immediately converted to instance IDs before storing.

Why: downstream of GroupManager there is no computation. The UI lazy-loads property values via `InstanceData` keyed by instance ID. ImageLine.vue and PileLine.vue will read `orderedIds[offset + k]` → instanceId directly, with no slot knowledge needed. Exposing slots to the UI would be a leaky abstraction requiring every consumer to query ColumnStore.

Custom cluster groups: cluster instances come from external sources (similarity search etc.) and are already identified by instance ID. They are stored as `Int32Array` of instance IDs in the cluster's leaf node — same format as property-grouped leaves, no special casing.

Re-concatenation cost on cluster injection: **affordable** (already O(cluster size) in current code). `orderedIds` cache is rebuilt lazily before the next `computeLines`.

**Conversion boundary:**
```
FilterManager → Int32Array of slots
SortManager   → Int32Array of sorted slots
GroupManager  → receives sorted slots; converts slot→instanceId on leaf insert
GroupTree     → stores and exposes instance IDs; cursor.pos indexes orderedIds
```

Re-bucketing in incremental path: `updateSelection` receives instance IDs → looks up slot via `col.slotMap.get(id)` → reads column value → determines group key. Two O(1) lookups, not a structural issue.

---

### Q4 — Date bucketing: epoch-ms arithmetic, all units

**col.readSlot returns `Date` objects** for date columns. Normalize at the read boundary: `date.getTime()` → epoch-ms number, cached per unique raw value via `Map<Date, number>` (or just call `.getTime()` inline — `Date.getTime()` is trivial, no allocation). Then all bucketing is pure integer arithmetic:

```ts
// Sub-day (Second, Minute, Hour, Day, Week)
const stepMs = stepSize * DateUnitFactor[unit] * 1000
bucketKey = Math.floor(epochMs / stepMs)          // integer, no Date object

// Month
const totalMonths = year * 12 + month             // extracted once per unique epochMs
bucketKey = Math.floor(totalMonths / stepSize)    // integer

// Year
bucketKey = Math.floor(utcYear / stepSize)        // integer
```

`closestDate()` is **deleted**. Bucket key is always a `number`. Display labels (`"Jan 2024"`, `"2024-03-15"`) are computed from the integer key once per group header at render time, not in the hot path.

`new Date()` in the scan loop: **0 allocations**. One `Date` constructor per unique raw column value to normalize (tens to hundreds, not 1M).

---

### Q5 — GroupManager input: sorted `Int32Array` from SortManager

**Decision:** `GroupManager.group(sortedSlots: Int32Array)` receives the sorted slot array directly from SortManager. `GroupManager.sort()` is **deleted** — re-sorting means re-grouping with the new slot order; the caller invokes `group(newSortedSlots)` again. `ImageOrder = { [slot]: pos }` is **removed** from the GroupManager API. `sortGroupSlots()` is **deleted** — SortManager's sorted input + stable bucket sort makes per-group slot sorting free.

---

### Q6 — Cursors: zero-alloc mutating

**Decision:** `ImageCursor.next()` and `prev()` mutate `this` and return `this | null`. Zero allocation per step. Since TreeScroller is being refactored (Q7), `line.data: ImageIterator[]` is replaced by descriptor lines that don't embed cursor objects. `_shiftSelect` becomes a plain integer range loop over `orderedIds`.

`GroupIterator` / `ImageIterator` class names are kept as thin facades for external API compat, but their internals become integer cursors. `clone()` copies two integers (`groupId`, `localIdx`) — trivially cheap.

---

### Q7 — ImageLine.vue / PileLine.vue: in scope for Phase 3

**Decision:** Changing both components is in scope as part of Phase 3 (TreeScroller descriptor lines). `line.data` becomes `{ groupId: number, offset: number, len: number }` and cells resolve `orderedIds[offset + k]` directly. SHA1 piles: each "pile position" is a sub-range `[offset, offset+pileSize)` within the sha1 leaf's range; `line.type = 'piles'` signals the component to read the range as a pile.

---

### Q8 — `computeImageOrder` and `imageIteratorOrder`: deleted

**Decision:** Delete both. `getImageOrder()` is replaced by `cursor.pos` (the global position in `orderedIds`). Before deleting, grep all call sites of `getImageOrder` and `imageIteratorOrder` to confirm no serialised state or backend protocol uses them. If any UI feature needs "the N-th image globally", it reads `cursor.pos` directly.

---

### Q9 — Stable group IDs: persist GroupValueIndex across rebuilds

**Problem:** `group()` currently resets `this.result.valueIndex = new GroupValueIndex()` (L418), assigning fresh IDs in insertion order. If grouping order changes, the same logical group gets a different ID → view state (open/closed) is silently lost.

**Decision:** Make `GroupValueIndex` **persistent**. Do not reset it on `group()`. New key paths get new IDs; existing key paths keep their IDs. After each rebuild, do a cleanup pass: any ID that was in the old index but not found in the new tree is removed. View state transfer (`if (lastIndex[id]) group.view = ...`) then works correctly by construction — same key = same ID = preserved view.

Edge case: date step-size change (different bucket boundaries → different key paths → new IDs → view resets). This is correct behaviour — a step-size change produces semantically different groups.

---

### Q10 — Incremental updates: full rebuild on first load, incremental thereafter

**Decision:** `group(sortedSlots)` performs a full build — called once on first load and on any `groupBy` configuration change (add/remove property, change step size). After that, `updateSelection(updated, removed)` is the only path for data changes (property value edits, new/deleted instances from filter changes).

Incremental algorithm for a set of dirty instance IDs:
1. Look up `Map<instanceId, Set<leafGroupId>>` → old leaf groups for each dirty ID
2. Remove instanceId from each old leaf's `Int32Array`
3. Re-evaluate group key: `col.slotMap.get(id)` → slot → `col.readSlot(propId, slot)` → bucket key
4. Insert instanceId into new leaf(s) (creating leaf if needed)
5. Walk parent chain of changed leaves: update group sort if needed
6. Mark `orderedIds` cache stale; rebuilt lazily before next `computeLines`
7. Emit `onResultChange` with `{ type: 'incremental', affectedGroupIds }`

Cost for 1k changes in a 1M dataset: O(1k × depth × log(leaf_size)) — never touches the 999k unchanged slots. `addInstanceToGroups` is kept, unified with `computePropertySubGroup` logic to eliminate the current code duplication (tagWithParents hoisted outside the slot loop in both paths).

---

## 1. Where the Code Stands Today

The prior notes describe the "current" GroupManager from an older version. The actual code
in `src/core/GroupManager.ts` is partially modernised. Here is the real baseline:

| Item | Old notes assumed | Actual code today |
|---|---|---|
| `Group.images: Instance[]` | was the main problem | **Replaced**: `Group.slots: number[]` (slot indices) ✓ |
| Iterator allocation per step | full `new ImageIterator(...)` per step | **Still present**: `nextImages()` L1198–1214 does `this.clone()` + `new ImageIterator(...)` per step |
| `computeImageOrder()` | full iterator walk assigning order | **Still present** L467–477; called after every `group()` and `updateSelection()` |
| `imageToGroups` | `{ [instanceId]: number[] }`, `indexOf` | **Still present** L68; uses instance IDs (not slots), `splice(indexOf)` removal |
| `imageIteratorOrder` | `{ [groupId]: { [imgIdx]: number } }` | **Still present** L70; nested plain objects, rebuilt every rebuild |
| `[...group.key, keyValue]` spread per slot | problem per slot | **Still present** L869: 1M array spreads per grouping level |
| `closestDate` Date allocations | 3M Date objects per 1M images | **Still present** L129–163 |
| `sortGroupSlots(group, order)` | sorts slots via plain object lookup | **Still present** L209–211; `order` is `ImageOrder = { [slot]: pos }` |
| TreeScroller `computeImageLines` | pushes `ImageIterator` per image into lines | **Still present** TreeScroller L199–218; `newLine.push(imgIt)` |

**Net**: the biggest wins (removing `Instance[]`, slot-indexing) are done. The remaining hot
costs are:
1. Iterator object allocation in `computeImageLines` / `computeImageOrder` (~3M objects/run)
2. `imageIteratorOrder` nested object rebuild (~1M entries per run)
3. `[...group.key, keyValue]` spread allocation per slot per grouping level
4. `closestDate` Date object allocation per slot per date-grouped property
5. `sortGroupSlots` using `ImageOrder` plain-object keyed by slot (hash lookup per comparison)
6. `imageToGroups[id].indexOf` → O(groups) per image on removal
7. `computeLines` in TreeScroller: full O(n) walk + O(n) reactive line objects

---

## 2. Target Architecture

```ts
// ── GroupNode: stores instance IDs (not slots) ────────────────────────────
interface GroupNode {
  id: number
  parentId: number
  childIds: number[]
  depth: number
  order: number                        // DFS display order among sibling groups

  instanceIds: Int32Array              // leaf nodes only — instance IDs in sorted order
  start: number                        // offset into orderedIds cache
  end: number                          // exclusive

  closed: boolean
  meta: { propertyValues?: PropertyValue[] }
  type: GroupType
  subGroupType?: GroupType
}

// ── GroupTree ─────────────────────────────────────────────────────────────
interface GroupTree {
  nodes: Map<number, GroupNode>         // #groups (thousands), NOT #images
  rootId: number
  valueIndex: GroupValueIndex           // PERSISTENT across rebuilds — stable IDs

  // Reverse lookup for incremental updates
  imageToGroups: Map<number, Set<number>> // instanceId → Set<leafGroupId>  O(1) lookup

  // Derived cache — rebuilt lazily before computeLines, marked stale on leaf changes
  orderedIds: Int32Array                // instance IDs in DFS display order
  rowToGroup: Int32Array                // parallel: rowToGroup[i] = groupId owning row i
  prefixCounts: Int32Array              // cumulative leaf sizes, DFS order (cursor arithmetic)
  cacheStale: boolean
}

// ── Traversal: zero-alloc mutating cursors ────────────────────────────────
// GroupIterator / ImageIterator kept as API-compatible facades.
// next() / prev() mutate this, return this | null.
// cursor.pos = index into orderedIds = global display order (replaces imageIteratorOrder).
```

**Deleted vs. today:**

| Removed | Replaced by |
|---|---|
| `imageIteratorOrder` + `computeImageOrder()` | `cursor.pos` |
| `imageToGroups: { [id]: number[] }` with `indexOf` | `Map<id, Set<groupId>>` O(1) |
| `sortGroupSlots(group, order)` | SortManager sorted input + stable bucket sort = free |
| `ImageOrder` parameter | `sortedSlots: Int32Array` |
| `closestDate()` | epoch-ms integer arithmetic |
| `Group.slots: number[]` | `GroupNode.instanceIds: Int32Array` |

---

## 3. Implementation Phases

### Phase 0 — Quick wins, no API change (do first, independent of redesign)

These can land now on the current structure:

**P0.1 — Replace `imageToGroups` array-indexOf with Map+Set**
```ts
// current: { [instanceId: number]: number[] }  — O(groups) indexOf removal
// new:     Map<instanceId, Set<groupId>>         — O(1) delete
```
`removeImageToGroups` L894–901: replace `splice(indexOf)` with `set.delete(groupId)`.
`saveImagesToGroup` L489–496: use `set.add(groupId)`.

**P0.2 — Eliminate `computeImageOrder()` for the common cases**
`getImageOrder()` is the only consumer of `imageIteratorOrder` (L1254). Find all callers of
`getImageOrder()` in the UI — if none are active in the hot path, delete
`computeImageOrder()` entirely for now (or move it behind a flag). Calling it after every
`group()` + `updateSelection()` is the single largest allocation source.

**P0.3 — Eliminate `[...group.key, keyValue]` spread in `computePropertySubGroup`**
L869: `const key = [...group.key, keyValue]` allocates a new array per slot. Since
`group.key` is constant per group and the new value is constant per bucket, build the key
once per unique value, not once per slot:
```ts
// bucket pass: slot → keyValue (no spread)
// key construction: once per unique keyValue
const key = parentKey.concat(keyValue)   // still allocates once per bucket, not per slot
```
Pre-bucket slots by keyValue first (one linear scan), then build groups from buckets.

**P0.4 — Eliminate `closestDate` Date allocations**
Replace with epoch-ms arithmetic (see [[managers_1m_optimization]] §5, date bucketing).
Prerequisite: confirm that `col.readSlot(propId, s)` for a date property returns epoch-ms
number (Float64) not an ISO string. **This is an open question** (see §4 Q4).

**P0.5 — `sortGroupSlots` via SortCols not ImageOrder**
`ImageOrder = { [slot]: pos }` plain-object keyed by slot is now superseded by
`SortManager._sortCols` (typed arrays). GroupManager receives `order: ImageOrder` in its
public API. After the SortManager rewrite, consider passing `SortCols` directly and
sorting per-group with `cols[k][slotA] - cols[k][slotB]`. **API alignment question** (§4 Q5).

---

### Phase 1 — Per-leaf typed arrays (incremental-safe flat structure)

Replace `Group.slots: number[]` with `Group.slots: Int32Array` (typed, no push — rebuild on
change). Build `orderedSlots` as the concatenation of all leaf slots in DFS display order.
Build `rowToLeaf` as a parallel `Int32Array`.

```ts
interface GroupTree {
  root: GroupNode
  nodes: Map<number, GroupNode>
  orderedSlots: Int32Array          // leaf slots concatenated in DFS order
  rowToLeaf: Int32Array             // parallel to orderedSlots
  valueIndex: GroupValueIndex
}

interface GroupNode {
  // existing fields kept, plus:
  start: number                     // index into orderedSlots (set after DFS)
  end: number                       // exclusive
}
```

Build after `group()`: one DFS pass over the tree, concatenate leaf slots arrays (typed
`set()`), record `start`/`end` per node.

`imageToGroups` can then be dropped for the common case: `rowToLeaf[pos]` + `parentId` walk
gives all ancestor group IDs. Keep it only if a feature genuinely needs the reverse map.

This is the key **invariant flip**: the tree owns `start/end` ranges; the data is in
`orderedSlots`; leaves are still mutable arrays for incremental updates (insert/remove from
one leaf = O(leaf) not O(n)).

---

### Phase 2 — Integer cursors (kill iterator allocation)

Replace `new ImageIterator(...)` per step with `ImageCursor` that is a reusable mutable
object (or a value pair `{ pos, groupId }`):

```ts
class ImageCursor {
  pos: number           // index into orderedSlots
  groupId: number       // current leaf group
  localIdx: number      // index within group's range (pos - node.start)

  next(): boolean       // advance pos; return false at end of tree
  prev(): boolean
  isValid(): boolean
  get slot()  { return this.tree.orderedSlots[this.pos] }
  isImageBefore(o: ImageCursor) { return this.pos < o.pos }
}
```

`_shiftSelect` L938–956: replace iterator-clone-walk with
`for (let p = start.pos; p <= end.pos; p++) ids.push(slotToId[orderedSlots[p]])`.
No iterator objects. O(selection size) not O(selection size × iterator-construction cost).

**API compatibility target**: keep `GroupIterator` / `ImageIterator` as thin facades over the
integer cursors for all external callers (selection code, TreeScroller). Their
constructor cost drops to O(1) (no group-object graph traversal, no `shouldSkipGroup`
scan). `nextImages()` becomes `this.pos++; return this`.

Whether to mutate-in-place or return new objects from `nextImages` is the key API question
(§4 Q6).

---

### Phase 3 — TreeScroller descriptor lines (kill computeImageLines walk)

**Depends on Phase 1** (`orderedSlots` + `GroupNode.{start,end}`).

Replace `computeImageLines` iterator-walk with arithmetic packing:
```ts
perLine = Math.floor(lineWidth / (imageHeight + 12))
rowCount = Math.ceil(node.end - node.start, perLine)
// emit rowCount descriptor lines, no per-image work
```

Each line: `{ type:'images', groupId, offset, len, size }` — no iterator array embedded.

`ImageLine.vue` and `PileLine.vue` must be updated to read `orderedSlots[offset + k]`
instead of `line.data[k].slot`. This is the **largest consumer-side change** (§4 Q7).

---

### Phase 4 — Virtual layout (kill O(n) line materialization)

**Depends on Phase 3**.

See [[tree_scroller_computelines_optimization]] §4 Option 2. Replace the ~100k-line flat
array with `GroupBlock[]` + `lineOffsets: Float64Array` prefix sums. RecycleScroller (or a
thin wrapper) reads only the ~100 visible lines at scroll time.

`computeLines` drops from O(n) to O(#groups).

---

## 4. Open Questions

These must be resolved before writing Phase 1+ code. Phase 0 is independent.

---

### Q1 — Per-leaf arrays vs. single packed array for `orderedSlots`

[[group_tree_structure_redesign]] §8 recommends **per-leaf** (leaves own `Int32Array`s;
`orderedSlots` is the DFS concatenation, rebuilt after any structural change). The single
packed array is O(n) for any insert/remove.

**Current assumption**: per-leaf is correct. Single packed array is only built as a
derived cache after `group()` and after any structural `updateSelection`. Is this correct?

*Decision needed*: Is per-leaf the default, or do we target a single packed array and
accept O(n) insert/remove (which is already the case for full rebuilds)?

A: per leaf

---

### Q2 — `imageToGroups` reverse lookup: keep or drop?

`updateSelection` L606 reads `this.result.imageToGroups[instanceId]` to find which groups
an updated/removed instance currently lives in. With `rowToLeaf` + parent walk this is
O(#occurrences × depth) per instance. For multi-tag with many parent groups this is fine;
for a deep tree with many levels it may be expensive.

Options:
- **A**: Keep `Map<instanceId, Set<groupId>>` maintained incrementally (current approach, just fix indexOf → Set)
- **B**: Drop it; scan leaf's `slots` for the target slot (per-leaf arrays are small) + walk `parentId` chain
- **C**: Keep a `Map<slot, leafGroupIds[]>` (slot-indexed, not instance-ID-indexed) for the hot path in `updateSelection`

*Decision needed*: Which approach? Option A is the safest and the existing design. Option C aligns better with the slot-first pipeline.

A: Keep A. We will have instance ids in the leaf groups and not slot. So we will need A

---

### Q3 — Custom groups (clusters): how do they interact with `orderedSlots`?

`addCustomGroups` L719 injects non-property groups as children of an existing group. Their
slots are NOT produced by SortManager's sorted output — they come from external sources
(e.g., similarity clusters with their own ordering).

With per-leaf arrays: custom group children each own their own `slots: Int32Array`, and the
parent's range in `orderedSlots` is rebuilt to include them. This requires a DFS
re-concatenation pass (O(#affected + subtree size)) after each cluster injection.

*Questions*:
- Can we afford O(subtree) re-concatenation on cluster injection? Current code does `setChildGroup` → `saveImagesToGroup` which is already O(cluster size).
- Should `orderedSlots` be lazily rebuilt only at `computeLines` time, not on every `addCustomGroups`?
- Cluster slots may duplicate slots from other groups (same image in multiple clusters). Is that intended?
 A:
orderedSlots should maybe be orderedInstances
  yes we can affort re concatenation
  It should be instances in the cluster groups.
  

---

### Q4 — Date storage format in ColumnStore

`closestDate()` (L129) calls `new Date(value)` where `value` comes from
`col.readSlot(propId, s)`. The epoch-ms arithmetic optimization requires that the column
store returns a **number (epoch ms)** for date properties.

*Verify*: What does `col.readSlot` actually return for `PropertyType.date`? Is it:
- `number` (epoch ms) → arithmetic works, `closestDate` can be replaced
- `string` (ISO 8601) → need `Date.parse(value)` first, only once per unique date
- `Date` object → need `.getTime()`, only once per unique date

If dates are stored as strings or Date objects in the column, the optimization still works
by calling `Date.parse`/`.getTime()` once per unique raw value (cache via `Map<raw, epochMs>`), since 1M images rarely have 1M unique dates.

A: Its dates

---

### Q5 — Should `sort(order: ImageOrder)` change to accept `SortCols`?

Currently `GroupManager.sort(order: ImageOrder)` receives an `ImageOrder = { [slot]: pos }`
(plain object). `sortGroupSlots` L209 sorts each group's `slots[]` using this.

After the SortManager rewrite, the natural output is a sorted `Int32Array`, not an
`ImageOrder` map. If we pass the sorted `Int32Array` to `GroupManager.group()`, the bucket
sort is **stable** (slots arrive pre-sorted), so `sortGroupSlots` is **not needed at all**
inside `group()`.

*Question*: Is `GroupManager.sort(order)` called independently after `group()` (i.e., sort
changes without regrouping)? If yes, we still need a per-group slot sort. Could that sort
use `SortCols` directly instead of `ImageOrder`?

*Decision needed*: Should the public API of `sort()` change from `(order: ImageOrder)` to
`(sortedSlots: Int32Array)` or `(cols: SortCols, orders: number[])`? This affects
`CollectionManager`'s orchestration.

A: Use Int32Array

---

### Q6 — Iterator mutation semantics: mutate or return new?

The current API: `nextImages(): ImageIterator` returns a **new object** each step.
TreeScroller `computeImageLines` collects these into arrays: `newLine.push(imgIt)`.

The proposed integer cursor: `next(): boolean` mutates in place.

These are incompatible. Two options:

**Option A — Mutating cursor** (optimal, no allocation):
`nextImages()` mutates `this` and returns `this | undefined`. BUT `newLine.push(imgIt)`
would then push the same cursor reference into every slot of `newLine` — all pointing to
the last position. TreeScroller must change `newLine.push(imgIt)` to
`newLine.push(imgIt.pos)` (or a snapshot).

**Option B — Value-type iterator** (compatible, minimal allocation):
`nextImages()` returns a new `ImageIterator` but backed by a pool or by copying just two
integers (`groupId`, `imageIdx`). Construction becomes O(1) (no group-object traversal).
Iterator allocation drops from "complex object" to "two-integer value". Not zero-alloc but
much cheaper.

*Decision needed*: Which option? Option B is a drop-in replacement; Option A requires
TreeScroller and `_shiftSelect` to change their iterator-collection pattern.

The answer directly determines whether `line.data: ImageIterator[]` can survive as-is or
must become `line.data: number[]` (positions).

A: Mutating cursor

---

### Q7 — ImageLine.vue / PileLine.vue change scope

`line.data` in the current scroller is `ImageIterator[]`. Each cell accesses:
- `it.slot` → resolves to the column-store slot index
- `it.sha1Group` → the sha1 pile (if any)
- `it.slots` → all slots in the pile

With descriptor lines (`{ type, groupId, offset, len }`), cells would instead access:
```ts
orderedSlots[offset + k]    // → slot
// sha1 piles: how?
```

*Questions*:
- Is changing ImageLine.vue and PileLine.vue in scope for Phase 3, or must descriptor
  lines stay backward-compatible with iterator arrays?
- How do sha1 piles surface in the descriptor model? In sha1 mode each "image position"
  in `orderedSlots` is actually a sha1 group, not a single slot. Does `orderedSlots`
  contain ONE representative slot per pile (with a sidecar `sha1GroupId[]`), or does each
  pile get a block of N consecutive entries?
  
  A: I want to have instanceId here 

---

### Q8 — `getImageOrder()` / `imageIteratorOrder` consumers

`ImageIterator.getImageOrder()` L1254 returns the global order number from
`imageIteratorOrder`. Find all call sites. If this is only used for:
- sorting a selected set by display order before some operation, OR
- exposing order to external code

then replacing it with `cursor.pos` is a drop-in. But if something formats or serialises
`imageIteratorOrder` to the backend or to saved state, that's a breaking change.

*Action*: grep for `getImageOrder` and `imageIteratorOrder` across the whole frontend.

---

### Q9 — `GroupValueIndex` ID stability

`GroupValueIndex` assigns monotonically increasing IDs to group keys. It is reset on every
`group()` call (L418: `this.result.valueIndex = new GroupValueIndex()`). IDs are then
re-assigned fresh each rebuild, and `view` state is transferred by old ID (L453–455):
```ts
if (lastIndex[id]) group.view = lastIndex[id].view
```

This works as long as the same group gets the same numeric ID across rebuilds, which
requires the same insertion order into `GroupValueIndex`. Is that guaranteed?

If not, view state (open/closed) could be lost on any rebuild where group order changes.
Should IDs be derived from the key path itself (e.g., a hash) rather than insertion order?

---

### Q10 — `addInstanceToGroups` vs. `computePropertySubGroup` duplication

`addInstanceToGroups` (L335) is called per-slot in the incremental update path. It
duplicates much of `computePropertySubGroup` (L832) but less efficiently: it rebuilds
`tagWithParents` inside the per-slot loop (L346–353), whereas `computePropertySubGroup`
correctly hoists it outside (L837–841).

In the redesign, does the incremental path (`addUpdatedToGroups`) survive at all, or does
any structural change (groupBy property change, tag value change) always trigger a full
`group()` rebuild? If full rebuilds are the norm, `addInstanceToGroups` can be deleted.

*Decision needed*: What is the threshold between incremental group update and full rebuild?
Currently: `updateSelection` uses `addUpdatedToGroups` → `addInstanceToGroups`. Is this
path worth the complexity, or should structural changes always trigger `group()`?

A: First load is update, then its incremental for now

---

## 5. Dependency Graph

```
Phase 0 (quick wins, independent)
  P0.1 imageToGroups Set
  P0.2 delete computeImageOrder
  P0.3 pre-bucket computePropertySubGroup
  P0.4 epoch-ms date arithmetic         ← needs Q4 answer
  P0.5 SortCols in sortGroupSlots       ← needs Q5 answer

Phase 1 (orderedSlots + ranges)          ← needs Q1, Q2, Q3 answers
  → GroupTree gets orderedSlots + rowToLeaf
  → GroupNode gets start/end
  → imageToGroups optionally dropped

Phase 2 (integer cursors)                ← needs Q6 answer
  → ImageCursor replaces new ImageIterator per step
  → _shiftSelect, computeImageOrder replaced by range loops

Phase 3 (descriptor lines)               ← needs Q7 answer; depends on Phase 1
  → computeImageLines replaced by arithmetic
  → ImageLine.vue / PileLine.vue updated

Phase 4 (virtual layout)                 ← depends on Phase 3
  → GroupBlock + lineOffsets prefix sums
  → Drop materialized line array
```

---

## 6. Recommended First Step

**Answer Q4 (date storage format)** and **Q6 (iterator mutation semantics)** first —
these determine whether Phase 0.4 and Phase 2 are cheap or require larger changes.

Then implement Phase 0.1–0.3 (independent, safe) and Q2/Q10 (incremental vs. full rebuild
policy), which together eliminate most of the current allocation hotspots without touching
the public API.

Phase 1 (orderedSlots) is the structural pivot that enables Phases 3 and 4. Do it after
Phase 0 is settled.
