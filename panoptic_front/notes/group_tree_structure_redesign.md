# GroupManager — Tree Structure Redesign for 1M Instances

Scope: the **shape of the group tree and the iterator/line-materialization path**, i.e.
`GroupManager` (`src/core/GroupManager.ts`) and how `TreeScroller.computeLines()`
(`src/components/scrollers/tree/TreeScroller.vue`) consumes it.

This is the structural counterpart to:
- [[managers_1m_optimization]] — data-store columnar layout + filter/sort/group pipeline.
- [[tree_scroller_update_flow]] — *when* `computeLines` re-runs and why it can't tell cheap from expensive changes.

This note does not repeat those. It answers one question: **what data structure should
the group tree be so that grouping, sorting, traversal, and rendering stay O(useful work)
at 1M instances?**

---

## 1. What the GroupManager is supposed to provide

Three responsibilities, all of which must survive any redesign:

1. **A tree** of groups produced by N-level property grouping (`state.groupBy`), optional
   per-leaf sha1 sub-grouping, and injectable custom groups (clusters).
2. **Sorting** at two independent levels: groups among siblings (`sortGroup`), and images
   within a group (`sortGroupImages` via an `ImageOrder` map).
3. **Traversal** in display order: `next/prevGroup`, `next/prevImages`, `isImageBefore`,
   shift-range selection, `findImageIterator`, and a global `order` per group / per image
   (`imageIteratorOrder`).

`TreeScroller` flattens this tree into a `ScrollerLine[]` (`group` / `images` / `piles`
rows) for `RecycleScroller`.

---

## 2. Why the current structure does not scale to 1M

The current `Group` node stores **`images: Instance[]` at every node**, and traversal is
done by **constructing iterator objects per step**. Both are O(n) in allocations on the hot
path, and the hot path runs on every `onResultChange`.

### 2a. `Instance[]` stored at every level — O(n) duplicated refs + object graph

```ts
interface Group {
  images: Instance[]   // root holds ALL 1M refs; each intermediate + leaf holds its subset
  children: Group[]
  ...
}
```

- The root holds 1M `Instance` refs. Each grouping level re-stores the same images split
  across nodes → **~2× the refs per grouping level** (`computePropertySubGroup` L1083:
  `grp.images.push(img)`).
- Worse, these are `Instance` *objects*, not ids/slots. Every grouping decision reads
  `store.slotMap.get(img.id)` then `store.readSlot(...)` (L1043–1044) — an id→slot hash
  lookup per image even though the column store is already slot-indexed.
- `imageToGroups: { imgId → number[] }` (L78) is a plain object with 1M keys, and
  `removeImageToGroups` does `indexOf` on those arrays (L1103) → O(groups) per image on
  updates.
- `imageIteratorOrder: { groupId → { imgIdx → order } }` (L80) is a nested plain object,
  also O(n) entries, rebuilt by `computeImageOrder()` (L594).

### 2b. Iterators are heap objects constructed per image — the headline cost

`computeImageLines` (TreeScroller L178) walks a group's images with:

```ts
let imgIt = ImageIterator.fromGroupIterator(it)
while (...) { newLine.push(imgIt); imgIt = imgIt.nextImages() }
```

`ImageIterator.nextImages()` (GroupManager L1480) does `this.clone()` **and** returns a
`new ImageIterator(...)`. Each constructor runs `getGroup()` (index lookup), `getImages()`,
`getSha1Group()`, `shouldSkipGroup()`. So:

> **`computeLines()` allocates ~2 `ImageIterator` objects per image — ~2M short-lived
> objects per recompute at 1M images** — and `computeLines` runs from scratch on every
> sort, toggle, filter, and incremental update (see [[tree_scroller_update_flow]]).

`computeImageOrder()` (L594) does the *same* full ImageIterator walk again to assign global
order — another ~1M iterator allocations, every rebuild.

### 2c. `computeLines` materializes the full flat list for the whole dataset

`computeLines` (TreeScroller L163) walks the entire tree and pushes a line per image-row for
**every open group across the whole dataset**, then `imageLines.value = lines.map(shallowReactive)`.
At 1M images / ~10 per line that is **~100k line objects, each wrapped in a reactive proxy,
each holding an array of ~10 ImageIterators**. RecycleScroller only ever renders ~100 of
them. The other ~99.9% is pure waste that must be rebuilt on every change.

### Summary of per-recompute cost at 1M

| Structure | Cost now |
|---|---|
| `ImageIterator` allocs in `computeImageLines` | ~2M objects |
| `ImageIterator` allocs in `computeImageOrder` | ~1M objects |
| `ScrollerLine` objects (full dataset) | ~100k, all `shallowReactive` |
| `Instance[]` refs across tree | ~n per grouping level |
| `imageToGroups` / `imageIteratorOrder` entries | ~1M each |

---

## 3. The key insight: after grouping+sorting, a group is a *contiguous range*

Grouping is fundamentally a **stable multi-key bucket sort**. Once images are bucketed by
group key (and sorted within), all members of a leaf group are **contiguous** in a single
global ordered array. A group therefore does not need to own an array of images — it only
needs `[start, end)` offsets into one shared array.

The one wrinkle is **multi-tag grouping**, where an image belongs to several groups. The
current tree already duplicates the image into each tag group's `images[]`; we keep that
behavior by letting the global array contain the slot once per group it appears in. Length =
Σ group sizes (with tag duplication) — still one flat typed array.

This collapses the entire image-bearing layer of the tree into **one `Int32Array`**.

---

## 4. Proposed structure

### 4a. Slot-based global order + thin group nodes

```ts
// ONE flat array, display order, slot indices (not Instance, not id).
// Length = total image-rows including multi-tag duplication.
orderedSlots: Int32Array

interface GroupNode {
  id: number
  key: (number | string)[]      // value path; group identity
  parentId: number
  depth: number
  order: number                 // DFS display order among groups (small int)

  childIds: number[]            // [] for leaf
  subGroupType?: GroupType

  // Range into orderedSlots. For a leaf: its images. For a parent: the span
  // covering all descendants (start of first child .. end of last child).
  start: number
  end: number                   // exclusive; count = end - start

  // display + view
  propertyValue?: PropertyValue
  closed: boolean
}

interface GroupTree {
  nodes: Map<number, GroupNode> // size = #groups (thousands), NOT #images
  rootId: number
  orderedSlots: Int32Array      // size = #image-rows
  // O(1) "which group owns global position p" — parallel to orderedSlots,
  // OR derive via binary search over leaf ranges (sorted by start).
  rowToLeaf?: Int32Array
}
```

What disappears:
- `Group.images: Instance[]` → gone. Resolve on demand: `instances[ slotToId[ orderedSlots[p] ] ]`,
  only for visible rows.
- `imageToGroups` → for the common case a slot's leaf is `rowToLeaf[p]`; parents are walked
  via `parentId`. (Multi-tag membership = the set of positions where the slot appears; build
  a `Map<slot, number[] positions>` only if a feature needs it.)
- `imageIteratorOrder` → **an image's global order IS its index `p` in `orderedSlots`.**
  `computeImageOrder()` is deleted entirely.

### 4b. Build = multi-key stable bucket sort

Input: the sorted slot list from SortManager (already display-ordered within a would-be
group). Output: `orderedSlots` + node map.

```
group(sortedSlots):
  recurse(range, level):
    if level == groupBy.length: return            // leaf reached
    prop = groupBy[level]
    # bucket slots in [range] by group key, STABLE (preserves sort order within bucket)
    buckets = stableBucketBy(range, slot => keyFor(prop, slot))   # tags -> multi-bucket
    write buckets back into orderedSlots contiguously, in group-sort order
    for each bucket -> create GroupNode{start,end}; recurse(bucket, level+1)
```

- `keyFor` reads the column directly by slot (`columnData[prop].data[slot]`), no `Instance`,
  no id→slot lookup. Date bucket keys are integer arithmetic (see [[managers_1m_optimization]] §5).
- Tag grouping expands one slot into several buckets (parents included) — the only place the
  array grows beyond n.
- sha1 sub-grouping is the same operation at the leaf, keyed by the SHA1 column.
- Cost: O(n) per grouping level, one typed array write-back, plus O(#groups) node creation.
  No per-image objects, no nested key-array spreads (`[...group.key, v]` per image, L1073,
  gone — key built once per bucket).

### 4c. Iterators become integer cursors (traversal preserved, allocation gone)

Keep the `GroupIterator` / `ImageIterator` *API* (a lot of selection/keyboard code depends
on it) but back it by integers, not by reconstructing objects each step:

```ts
class ImageCursor {
  constructor(public tree: GroupTree, public pos: number) {}   // pos = index in orderedSlots
  get slot()  { return this.tree.orderedSlots[this.pos] }
  nextImages(){ this.pos++; return this.pos < end ? this : undefined }   // mutate, no alloc
  isImageBefore(o){ return this.pos < o.pos }                            // int compare
}
```

- `next/prevImages` → `pos ± 1` (skip across closed groups via the leaf range table).
- `isImageBefore` / global `order` → integer compare on `pos`. `imageIteratorOrder` gone.
- Shift-range select → `for (let p = a; p <= b; p++) select(orderedSlots[p])` — no iterator
  objects, no `while (it = it.nextImages())` clone storms (current `_shiftSelect` L1148).
- `next/prevGroup` → walk `childIds` / `parentId` with the `order` field; #groups is small so
  these can stay as light objects or also be index cursors over a DFS-ordered group array.
- `findImageIterator(groupId, imageId)` → `slot = slotMap.get(imageId)`; scan/binary-search
  the group's `[start,end)` range in `orderedSlots` for that slot.

### 4d. `computeLines` produces tiny descriptors, resolves content lazily

```ts
interface ImageLineDesc {
  type: 'images' | 'piles'
  groupId: number
  offset: number   // start index into orderedSlots for this row
  len: number      // images on this row
  size: number
}
```

- Walk `nodes` in `order`; per open leaf emit `ceil(count/perLine)` descriptors. **No
  ImageIterator construction.** Work = O(#groups + #lines), and each line is a flat POJO
  (no embedded iterator array).
- The cell component (`ImageLine.vue` / `PileLine.vue`) resolves
  `orderedSlots[offset + k]` → `slotToId` → `instances[id]` only for the ~100 active rows,
  and pulls property values via `InstanceData` (already windowed — see
  `windowIds`/`InstanceData.vue`). So per-image work is bounded by the viewport, not the
  dataset.

This removes the ~2M iterator allocs and the ImageIterator-array payload of every line.
The `~100k descriptor` array remains (RecycleScroller needs per-item sizes), but each entry
is now ~5 numbers instead of an object holding ~10 iterators.

> Optional further step: a custom variable-height scroller driven by a prefix-sum
> (`Float64Array` of cumulative line heights) over the descriptor array would let us drop the
> materialized `imageLines` array entirely and binary-search the visible window from
> `scrollTop`. Bigger change; note it but don't block on it.

---

## 5. How each current responsibility maps onto the new structure

| Responsibility | Now | Proposed |
|---|---|---|
| N-level property grouping | recursive `computePropertySubGroup`, `images.push` per node | stable bucket sort into `orderedSlots`, ranges per node |
| sha1 sub-grouping | `groupBySha1` builds child `images[]` | sub-bucket the leaf range by SHA1 column |
| custom/cluster groups | `setChildGroup` splices `Instance[]` | inject child ranges into a parent's span |
| group sort (siblings) | `sortGroup` sorts `children[]` | sort `childIds`, renumber `order` (#groups) |
| image sort (within group) | `sortGroupImages` per group, every group | input already sorted by SortManager; bucket sort is stable → free |
| global image order | `computeImageOrder` (1M iterators) | implicit: `pos` in `orderedSlots`; deleted |
| `imageToGroups` | object, 1M keys, `indexOf` removal | `rowToLeaf` + `parentId` walk |
| traversal / shift-select | iterator object per step | integer cursor `pos±1`, range loop |
| flatten to lines | iterator per image, reactive line per row | descriptor per row, lazy content |

---

## 6. Memory at 1M (grouping by 1 property, ~avg)

| Item | Now | Proposed |
|---|---|---|
| Image membership storage | `Instance[]` at root + leaves (~2n refs) + object graph | one `Int32Array` (~4 MB) + `rowToLeaf` (~4 MB) |
| Global order | `imageIteratorOrder` nested objects (~n entries) | implicit (0) |
| `imageToGroups` | object, n keys, arrays | `rowToLeaf` (covered above) |
| Per-recompute iterator allocs | ~3M objects | 0 (cursors are reused / int) |
| Line array payload | ~100k reactive objects holding iterator arrays | ~100k flat descriptors (5 ints) |

---

## 7. Multi-tag membership (instance in multiple groups)

Fully supported, with the same semantics as today's `addInstanceToGroups` (cross-product of
keys, L479–491). The mechanism is **slot duplication** in the ordered structure:

- One multi-tag level: slot X with tags `[A,B]` appears once in A's range and once in B's.
  `orderedSlots.length` = Σ group sizes — exactly the sum of today's `images[]` lengths.
- Nested multi-tag levels: X lands in the cartesian product of memberships (A/P, A/Q, B/P,
  B/Q). Same multiplicative blow-up the current structure already has — no worse.
- Parent ranges stay contiguous: duplication happens *within* each subtree independently, so
  "parent range = first child start .. last child end" still holds.
- Selection is free: `selectedImages` is keyed by instance id, so all visual occurrences of X
  highlight together with no extra work.

The only cost of duplication is the **reverse lookup** ("which groups is X in?", used by
`updateSelection` pruning / the old `imageToGroups`). That needs either a
`Map<slot, positions[]>` or per-leaf membership (see §8) — cheap, but not free like it looks.

## 8. Incremental updates — the single packed array does NOT do this cheaply

Correction to an earlier framing: a **single packed `Int32Array orderedSlots` is bad for
incremental insert/delete**. Changing one instance changes a range's size and **shifts the
whole tail → O(n) per edit**. "Splice the affected segment" does not save you — a size change
shifts everything after the splice point. The packed array is optimal for scan / scroll /
full-rebuild, not for in-place mutation.

Two ways to get real incrementality:

### 8a. Per-leaf slot arrays (recommended if incremental matters)

Leaves own their own small `Int32Array` / `number[]`; the global flat order is the
**concatenation of leaves in DFS order** — a derived cache, or never materialized at all.

- Value edit moving X from G1→G2: remove from G1's array, binary-insert into G2's. O(leaf).
- Multi-tag edit: diff membership sets → remove from `old − new` leaves, add to `new − old`
  leaves, create/delete leaves as needed (each an O(#groups) sibling-order + prefix-sum patch).
- Add / delete instance: touch only the affected leaf array(s) + prefix-sum patch.

This keeps the [[tree_scroller_computelines_optimization]] win intact: `GroupBlock` prefix
sums use per-leaf counts either way, and a cursor becomes `(leafIndex, localIdx)`. The only
thing given up vs. the packed array is one contiguous buffer — slightly worse cache locality,
but `#leaves ≪ #images`. **Net: per-leaf is the better default** because it preserves
incrementality at negligible cost.

### 8b. Full rebuild via bucket sort (simplest)

Keep one packed array, rebuild on any *structural* change. A typed-array bucket sort over the
filtered set is an O(n) pass with zero allocations — far cheaper than today's
allocation-heavy `group()`, and most edits already full-rebuild (see
[[tree_scroller_update_flow]]). Incremental then covers only non-structural updates (sort
reorder, selection).

### Either way

Pair with typed `onResultChange` payloads (`{ type, affectedGroupIds }`) so `computeLines`
can patch only the affected descriptor range instead of rebuilding all ~100k — the open
problem called out in [[tree_scroller_update_flow]].

---

## 9. Browser array-size limits — design around the small ones

The slot primitive is **not** the binding constraint at 1M:

| Structure | Max length | At Int32 |
|---|---|---|
| `Array` (`number[]`) | 2³²−1 ≈ 4.29 B | — |
| `Int32Array` (old V8/FF ~2 GB buffer) | ~536 M | ~536 M |
| `Int32Array` (modern 64-bit) | memory-bound, billions | billions |

1M slots in an `Int32Array` = **4 MB**. The real ceiling is total renderer memory (a tab dies
around a few GB), driven by the **multi-tag duplication factor** (§7), not the array length cap.

The limits that actually bite first — and that the implementation must avoid:

1. **Spread / `apply` argument count** (`f(...arr)`, `arr.push(...big)`, `Math.max(...big)`)
   throws around **65k–500k** elements — thousands of times below the length limit. The
   current code's `lines.push(...GroupToLines(it))` is safe only because it's per-group; never
   spread a full-dataset array. Use loops or `TypedArray.set()`.
2. **`number[]` dictionary-mode cliff** — large/holey regular arrays drop out of V8 fast
   elements into hash-map mode and get slow. **`Int32Array` is immune** (flat buffer). Use
   typed arrays for slot data.

Consequences for this design:

- **Prefer the per-leaf variant (§8a)** — many small `Int32Array`s, each trivially within every
  limit, no single huge allocation. This is an independent reason to choose it over the packed
  buffer.
- If a packed buffer is still wanted, use a **chunked/paged array** (array of fixed-size
  `Int32Array(1<<20)` chunks, index via `chunk = i>>20; off = i & 0xFFFFF`) to sidestep any
  single-buffer cap.

## 10. Migration path (incremental, API-preserving)

1. Add `orderedSlots` + `GroupNode.{start,end}` alongside existing `Group.images`; build both.
   Verify ranges agree with `images` arrays in dev.
2. Switch `computeLines` to descriptor + lazy resolution; keep ImageIterator API but back
   `nextImages`/`order` with `pos`. Delete `computeImageOrder` once `pos` is authoritative.
3. Convert selection/shift-range to integer-range loops.
4. Drop `Group.images`, `imageToGroups`, `imageIteratorOrder`; replace reads with
   `orderedSlots` / `rowToLeaf` / `parentId`.
5. (Optional) prefix-sum scroller to drop the materialized line array.

Steps 1–2 capture the bulk of the win (kill the ~3M iterator allocs and the per-node
`Instance[]`); they can land before the rest.
