# TreeScroller — `computeLines()` Optimization

Scope: the line-layout computation in `src/components/scrollers/tree/TreeScroller.vue`
(`computeLines`, `GroupToLines`, `computeImageLines`, `computeImagePileLines`, and the
layout watchers). **Assumes the group structure has already been optimized** per
[[group_tree_structure_redesign]] — i.e. the GroupManager exposes:

- `orderedSlots: Int32Array` — all image-rows in display order (slot indices),
- thin `GroupNode { start, end, childIds, depth, order, closed }` keyed in a `Map` sized by
  #groups (thousands), not #images,
- integer-cursor traversal (no `ImageIterator` heap objects per step).

Related: [[tree_scroller_update_flow]] (when/why `computeLines` re-fires),
[[managers_1m_optimization]] (data-store / pipeline).

---

## 1. What `computeLines` does today

It translates the group tree into a flat `ScrollerLine[]` that `RecycleScroller` renders:

```
getGroupIterator()  →  walk every group in display order
  per group: push 1 'group' header line
             if open & leaf: computeImageLines()  → pack images into rows
             if open & sha1: computeImagePileLines()
imageLines.value = lines.map(l => shallowReactive(l))
```

`computeImageLines` (L178) packs images into rows by **walking image iterators and
accumulating pixel width** until a row is full.

It runs from scratch on **every** `onResultChange`, and on `imageSize` / `width` /
`visiblePropertiesNb` changes, and on every group open/close (`closeGroup`/`openGroup` →
`computeLines`). See [[tree_scroller_update_flow]].

---

## 2. Cost today, at 1M images (all groups open)

| Cost | Location | Order |
|---|---|---|
| `ImageIterator` allocations (packing walk) | `computeImageLines` L195–214, `nextImages` | ~2M objects |
| Flat line objects built | `computeLines` L167–175 | ~n/perLine ≈ **100k** |
| `shallowReactive(l)` proxy per line | L175 | ~100k proxies |
| String id per line `id+'|img-'+len` | L185 | ~100k string allocs |
| `visiblePropertiesNb` watcher: scan + size-mutate all lines | L316–354 | 2 × O(lines) |
| `width` watcher → full `computeLines` | L357–360 | O(n) |

Even after the group redesign removes the ~2M `ImageIterator` allocs, **`computeLines` is
still O(n): it materializes ~100k reactive line objects for a dataset where RecycleScroller
only ever renders ~100 rows.** That O(n) array is rebuilt on every trigger. This note is
about removing that remaining O(n).

---

## 3. The two structural facts that unlock the win

### Fact A — packing is uniform, so it's division, not a loop

Inside one group every image cell has the **same width**: `imgWidth = imageHeight + 12`
(constant), against a constant `lineWidth = width - depth*MARGIN_STEP`. So the number of
images per row is a pure function:

```ts
perLine = Math.max(1, Math.floor(lineWidth / imgWidth))
rowsInGroup = Math.ceil(count / perLine)         // count = node.end - node.start
```

The entire width-accumulation `while` loop in `computeImageLines` / `computeImagePileLines`
(L196–214 / L238–255) — and the iterator walk it drives — is **unnecessary**. The component
already computes a `maxPerLine` this exact way (L46). Packing per group drops from
O(group size) to **O(1)**.

### Fact B — the line list is a deterministic function of group sizes + sizing constants

Given each group's `count`, `depth`, `closed`, and the three height constants
(`groupHeaderSize`, `imageLineSize`, `pileLineSize`), the **entire line layout is
derivable arithmetically**. Nothing needs to be walked per image. The line at index `i`, and
the line at pixel `y`, are both answerable from compact per-group summaries via prefix sums.

---

## 4. Proposed layout model

Build a compact **block summary array**, one entry per group (sized by #groups):

```ts
interface GroupBlock {
  groupId: number
  depth: number
  open: boolean
  isPile: boolean

  rowCount: number          // ceil(count / perLine), 0 if closed/empty
  rowHeight: number         // imageLineSize | pileLineSize
  rangeStart: number        // index into orderedSlots
  perLine: number

  // prefix sums (filled in one O(#groups) pass)
  firstLineIndex: number    // # of scroller lines before this block's header
  pixelOffset: number       // cumulative pixel height before this block
  pixelHeight: number       // header + rowCount*rowHeight
}

blocks: GroupBlock[]                 // length = #groups
lineOffsets: Float64Array            // prefix sum of pixel heights, for binary search
```

`computeLines` becomes: walk `GroupNode`s in `order` (the DFS index from the group redesign),
emit one `GroupBlock` each, accumulate the two prefix sums. **O(#groups)** — independent of
image count.

### Two ways to feed RecycleScroller

**Option 1 — cheap materialization (small change, ~90% of the win).**
Keep emitting a flat descriptor array, but each entry is a tiny POJO (no iterators, no
`Instance` refs) and rows are emitted by arithmetic, not by walking images:

```ts
{ type:'images', groupId, offset, len, size }   // offset/len index into orderedSlots
```

Removes the ~2M iterator allocs and the per-image packing loop. Still O(#lines) ≈ 100k tiny
objects + memory. Drop `shallowReactive` per line (see §5) and `id` becomes a number, not a
concatenated string.

**Option 2 — virtual layout (full win, constant memory).**
Don't materialize the line array at all. Drive a thin custom virtual list (or a
RecycleScroller wrapper) from `blocks` + `lineOffsets`:

- visible range from `scrollTop`: `binarySearch(lineOffsets, scrollTop)` → start block; walk
  forward until past `scrollTop + height` → ~a handful of blocks.
- materialize only the **~100 visible lines** as descriptors on demand.
- `scrollTo(groupId)` → `blocks[idx].pixelOffset` (replaces the `groupIdx` map, L34/L170).

`computeLines` is **O(#groups)**; rendered/allocated lines are **O(viewport)**. Total memory
for layout is O(#groups), not O(#images).

---

## 5. Knock-on simplifications to the watchers

The layout watchers today each do O(n) work over the materialized list. With the block model
they become O(#groups) or O(1):

- **`imageSize` watcher (L310):** recompute `imageLineSize`/`perLine` constants, recompute
  prefix sums → O(#groups). No per-line rebuild.
- **`width` watcher (L357, debounced 500ms):** width only changes `perLine` and row heights →
  recompute `rowCount` + prefix sums O(#groups). The 500ms debounce was hiding an O(n)
  rebuild; with O(#groups) it can run live on resize.
- **`visiblePropertiesNb` watcher (L316–354):** the whole "scan to find top item, then mutate
  `.size` on all 100k line objects" dance exists only because sizes live on materialized
  reactive objects. With prefix sums, the top item is `binarySearch(lineOffsets, scrollPos)`
  and the new scroll offset is recomputed arithmetically — O(log #groups) + O(#groups), no
  per-object mutation, no `shallowReactive`.
- **group open/close (`closeGroup`/`openGroup` L285–291):** today → full `computeLines`. With
  blocks, flip `blocks[i].open`, recompute that block's `rowCount`, and patch the prefix sums
  from `i` onward — O(#groups) suffix update, or lazy. No tree re-walk.

`shallowReactive` per line (L175) can go entirely: layout geometry lives in `blocks` /
`lineOffsets`; the only reactive surface needed is the visible-window descriptor list
(Option 2) or a single `triggerRef` on a `shallowRef` array (Option 1).

---

## 6. `windowIds` / `InstanceData` get simpler too

`windowIds` (L93) currently re-walks line objects and reads `it.image.id` off
`ImageIterator`s. With `orderedSlots` it's a direct slice of the visible range mapped through
`slotToId` — and in Option 2 the visible range is already known from the binary search, so
no expansion loop over line types is needed. The batched `InstanceData` value fetch is
unchanged in spirit, just fed from slots.

---

## 7. Expected gains (1M images, all open)

| Stage | computeLines time | Allocations / call | Layout memory |
|---|---|---|---|
| Today | O(n), ~hundreds ms–s | ~2M iterators + ~100k reactive lines + ~100k strings | O(n) (~100k objs) |
| Group redesign only (cursors) | O(n) | ~100k line objects (no iterators) | O(n) |
| + Arithmetic packing (Fact A) | O(#lines), no per-image walk | ~100k tiny POJOs | O(n) |
| + Virtual layout (Option 2) | **O(#groups), sub-ms** | **~100 visible descriptors** | **O(#groups)** |

The decisive step is **Option 2 + arithmetic packing**: `computeLines` cost and layout
memory stop depending on the number of images and depend only on the number of groups, which
is what the user actually scrolls through. Open/close, resize, and property-toggle all drop
from O(n) to O(#groups).

---

## 8. Required co-changes

- **`ImageLine.vue` / `PileLine.vue`** consume `line.data` as `ImageIterator[]` today. They'd
  take `{ groupId, offset, len }` and resolve `orderedSlots[offset+k]` → slot → instance
  (lazy, viewport-only). Selection (`updateImageSelection` → `findImageIterator`, L294) uses a
  lightweight integer cursor from the group redesign.
- **`scrollTo`** keys off `blocks[idx].pixelOffset` instead of `groupIdx` + `scrollToItem`.
- Option 2 needs a thin virtual-list shell; Option 1 keeps RecycleScroller as-is and is the
  low-risk first landing.

---

## 9. Recommended sequence

1. Land **arithmetic packing** (Fact A) + descriptor lines (Option 1) on top of the group
   redesign — kills the iterator allocs and the per-image packing loop, small diff.
2. Drop `shallowReactive` per line; move sizing to `blocks` + `lineOffsets`; convert the three
   watchers and open/close to O(#groups).
3. Move to **Option 2 virtual layout** for constant-memory scrolling — the step that makes
   `computeLines` independent of dataset size.
