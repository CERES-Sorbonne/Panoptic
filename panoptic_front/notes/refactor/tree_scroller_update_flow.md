# TreeScroller: Architecture and Update Flow

**Files covered:**
- `src/components/scrollers/tree/TreeScroller.vue`
- `src/core/CollectionManager.ts`
- `src/core/GroupManager.ts`
- `src/components/scrollers/tree/GroupLine.vue`

---

## Overview: What the TreeScroller Does

The TreeScroller is a virtualized list that renders the group tree as a flat array of typed "lines." It owns the translation from the hierarchical `GroupTree` (maintained by `GroupManager`) into a flat `ScrollerLine[]` array that a virtual scroller can render efficiently.

Each line has a type: `'group'`, `'images'`, or `'piles'`. The scroller renders only the visible subset.

---

## Data Flow: CollectionManager → GroupManager → TreeScroller

```
DataStore (raw images/instances)
        │
        ▼
CollectionManager
  ├── FilterManager.filter()        → filtered image list
  ├── SortManager.sort()            → sorted image list
  └── GroupManager.group()          → GroupTree (hierarchical)
                    │
                    │  onResultChange event
                    ▼
           TreeScroller.computeLines()
                    │
                    ▼
           imageLines: ScrollerLine[]   (flat, renderable)
```

### CollectionManager (`src/core/CollectionManager.ts`)

Acts as an orchestrator / pipeline controller. It chains three managers:

1. `filterManager.onResultChange` → calls `onFilter()` → triggers `sortManager.sort()` → triggers `groupManager.group(emit=true)`
2. `sortManager.onResultChange` → calls `onSort()` → updates sort order in GroupManager
3. `groupManager.onResultChange` → calls `onGroup()` (currently no-op; TreeScroller listens directly)

The `update()` method (line ~103) triggers the full chain from scratch. `setDirty()` can trigger either an incremental `updateSelection()` or a full `update()` depending on whether auto-reload is enabled.

### GroupManager (`src/core/GroupManager.ts`)

Owns the `GroupTree` and provides multiple update strategies with different costs:

| Method                 | Cost                                            | When Used                        |
| ---------------------- | ----------------------------------------------- | -------------------------------- |
| `group()`              | HIGH — full rebuild                             | Filter changes, group-by changes |
| `sort()`               | MEDIUM — reorders images within existing groups | Sort order changes               |
| `updateSelection()`    | LOW — removes/adds images, prunes empty groups  | Incremental image add/remove     |
| `addUpdatedToGroups()` | LOW — appends new images into existing tree     | Sub-step of updateSelection      |
| `toggleGroup()`        | INSTANT — flips `group.view.closed`             | User expand/collapse             |

All of these can emit `onResultChange` if called with `emit=true`. The TreeScroller doesn't know which method fired — it just sees the event and does a full `computeLines()`.

---

## computeLines(): The Core Translation (`TreeScroller.vue` lines 88–212)

```
GroupManager.getGroupIterator()   (walks the tree in display order)
        │
        ▼  for each group:
GroupToLines(iterator)
  ├── always: push one GroupLine (the header row)
  └── if group is open and has images:
        ├── non-sha1: computeImageLines()  →  one line per N images (grid rows)
        └── sha1:     computeImagePileLines() → one line per N piles
        │
        ▼
imageLines.value = flat ScrollerLine[]
groupIdx[groupId] = line index      (for scrollTo())
```

The key sizing values that control how many images fit per line:
- `maxPerLine` = `Math.floor(width / imageSize)`
- `imageLineSize` = `imageSize + (visibleProperties.length × propertyRowHeight)`
- `pileLineSize` = similar but for pile display

These are computed refs — when they change, watches fire and `computeLines()` is re-called.

---

## What Triggers a Lines Recompute

TreeScroller has five distinct update triggers:

```typescript
// 1. Mount
onMounted(computeLines)

// 2. imageSize prop change (user resizes thumbnails)
watch(() => props.imageSize, computeLines)

// 3. visiblePropertiesNb change (property panel visibility)
watch(visiblePropertiesNb, () => { /* update line sizes */ computeLines() })

// 4. width change (container resize) — debounced 500ms
watch(() => props.width, debounced(computeLines, 500))

// 5. GroupManager data change
props.groupManager.onResultChange.addListener(triggerUpdate)   // triggers computeLines()
```

Triggers 2–4 are layout-only: the group structure didn't change, only the pixel geometry.  
Trigger 5 is the data path: the underlying `GroupTree` changed.

---

## Why It's Hard to Know If Lines Actually Need Updating

This is the core complexity. The system has **one generic event** (`onResultChange`) that fires for changes of wildly different scopes, and the TreeScroller cannot distinguish between them.

### The fundamental problem

`onResultChange` fires for all of:
- Full group rebuild after a filter change → every line may change
- A sort reorder → line structure unchanged, only image order within lines changes
- A single image being added to one group → mostly unchanged
- A group being toggled open/closed → only the lines for that group's images are added/removed
- Sha1 groups being rebuilt → partial change

In every case, `computeLines()` runs from scratch, re-walking the entire tree, re-creating all line objects.

### What changes don't need `computeLines()` at all

| Change | Why lines don't need to change |
|--------|-------------------------------|
| Image selection toggled | `selectedImages` is a separate reactive Ref; child components watch it directly |
| Hover state | Pure UI, no line data involved |
| Image metadata edited (non-groupBy property) | Line structure unaffected |
| Group header label changes | GroupLine re-renders itself reactively |

### The group toggle problem

When the user collapses/expands a group, `toggleGroup()` flips `group.view.closed` and emits `onResultChange`. TreeScroller does a full `computeLines()` walk. But the only real change is whether `computeImageLines()` is called for that one group. There's no early exit or diffing.

The `GroupToLines` function (line 101) does check `group.view.closed` to skip image lines for closed groups — but this check is inside a full tree walk, not a targeted patch.

### Sort-only changes

When `sort()` runs, it reorders `group.images[]` in place across all groups, then emits. TreeScroller rebuilds all `ScrollerLine` objects. But the number of lines and their types don't change — only which `ImageIterator` objects are in each line. A smarter system could just reorder iterators within existing line objects, but there's no mechanism for that today.

### The incremental add case

`addUpdatedToGroups()` / `updateSelection()` is genuinely incremental on the GroupManager side. But TreeScroller still rebuilds all lines in response. For large collections where only 1–2 images changed, this is wasteful.

---

## What Would Be Needed for Smarter Updates

To avoid full recomputation, TreeScroller would need to know:

1. **Change type** — was this a sort, a toggle, an incremental add, or a full rebuild?
2. **Affected group IDs** — which groups actually changed?
3. **Change scope** — did the number of lines change, or only line content?

Options:
- **Typed events**: Replace `onResultChange` with typed events (`onSort`, `onGroupToggle`, `onStructureChange`) so TreeScroller can react differently to each.
- **Change set in the event payload**: GroupManager emits `{ type, affectedGroupIds }` and TreeScroller patches only the affected line ranges.
- **Dirty flag per group**: GroupManager marks groups as dirty; `computeLines` skips clean groups and reuses cached line slices.
- **Line diffing**: After recomputing, diff new lines against old and only mutate `imageLines.value` for changed ranges (still walks the tree but avoids unnecessary DOM updates downstream).

The current design chose simplicity: one event, one full recompute. For the expected collection sizes it's fast enough. The complication is that reading the code you can't tell from a call site whether a given operation will be cheap or expensive — that depends on which path through GroupManager fired `onResultChange`, which is opaque to TreeScroller.

---

## Key Line Numbers for Navigation

| Location | File | Lines |
|----------|------|-------|
| `computeLines()` main loop | TreeScroller.vue | 112–125 |
| `GroupToLines()` + image layout | TreeScroller.vue | 88–212 |
| Update triggers / watchers | TreeScroller.vue | 255–300 |
| `onResultChange` listener mount | TreeScroller.vue | 299–300 |
| `group()` full rebuild | GroupManager.ts | 507–575 |
| `addUpdatedToGroups()` incremental | GroupManager.ts | 371–416 |
| `updateSelection()` | GroupManager.ts | 730–785 |
| `sort()` | GroupManager.ts | 787–807 |
| `toggleGroup()` emits event | GroupManager.ts | ~900–904 |
| CollectionManager chain setup | CollectionManager.ts | 45–49, 103–135 |
