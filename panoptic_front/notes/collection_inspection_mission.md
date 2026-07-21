# Mission: extract clusters + iterators from GroupManager; make CollectionManager the inspection object

Prerequisite refactor for `cluster_view_goals.md` (the cluster overlay / `derive`
model, removing `rootedAt`, can't land cleanly until this is done). Folds in the
prior "separate cluster logic from GroupManager" analysis (verified against current
code below) and adds one goal: **CollectionManager becomes the object views use to
inspect a collection.**

## The problem

`GroupManager` is doing five jobs at once, and it's the de-facto public API:

- **tree engine** — sorted slots + `groupBy` → property tree (its real job)
- **result object** — owns `index`, `imageToGroups`, `valueIndex`, `orderedIds`,
  `pileIndex`, `version`, `buildOrdinalRanges`
- **iterator host** — `getGroupIterator` / `getImageIterator` / `findImageIterator`
  (via the `IteratorHost` interface it implements)
- **cluster editor** — `customGroups`, `addCustomGroups`, `moveImagesToGroup`,
  `split`, `merge`, `delete`, `renameGroup`, `rootedAt`, plus cluster special-cases
  scattered through `updateSelection` / `applySha1Piles`
- **selection owner** — `selectionNamespace`, `selectImageIterator`, shift-select…

And views reach straight into it. Direct `groupManager` references today:

| File | refs |
|---|---|
| `TreeScroller.vue` | 17 |
| `ClusterView.vue` | 15 |
| `CollectionManager.ts` | 14 |
| `ClusterScroller.vue` | 10 |
| `RecommendView.vue`, `ImageModal.vue`, `MapView.vue`, `ContentFilter.vue`, … | 8→1 |

`CollectionManager` already owns the filter→sort→group orchestration but just
exposes `groupManager` as a public field, so every consumer bypasses it. "Which
collection am I inspecting" is answered by grabbing a manager, not by an object.

**Verified against current code (rework-front):**

- Clusters live in `GroupManager.customGroups`, replayed on every rebuild by the
  fixed-point `while (insert)` loop in `group()` (`GroupManager.ts:57,138,164`) — a
  symptom that clusters don't belong to the rebuild lifecycle.
- Cluster special-cases are scattered: `updateSelection` skips `type == Cluster`,
  exempts them from `dropMembership` and from the slot re-sort; `applySha1Piles`
  special-cases them. `moveImagesToGroup` is cluster-only surgery in the generic
  manager.
- Orchestration is inverted: `actionStore.executeAction` returns converted
  `Group[]` (`actionStore.ts:186`), then UI components wire them in themselves —
  `GroupLine.vue:80` and `ClusterView.vue:92` call `addCustomGroups`, and
  `ClusterView` also drives `split`/`merge`/`delete`/`rename` directly. (The old
  note said "three components"; it's now these two plus the action buttons.)
- `GroupResult`/iterators are **not** extracted yet (all still on `GroupManager`);
  `CollectionManager` has **no** cluster API.
- sha1 grouping is *already* a display overlay (`pileIndex` / `applySha1Piles`) done
  the same inline way — it gets the same home as clusters, which validates the
  overlay abstraction.

## Target architecture

Four objects, each with one job:

1. **GroupManager** — *pure* tree engine. `group(slots)` → a `GroupResult`. No
   clusters, no iterators, no selection. Knows only `groupBy` + options.
2. **GroupResult** (the result object) — owns `index`, `imageToGroups`,
   `valueIndex`, `orderedIds`, `pileIndex`, `version`, `buildOrdinalRanges`, and is
   the **`IteratorHost`** (iterators are constructed from it, not from GroupManager).
3. **ClusterManager** — owns the cluster overlay, composed onto the result. All
   cluster edits (`cluster`, `merge`, `split`-nest, `delete`, `rename`, `move`,
   `assignValue`) live here. Replaces `customGroups`, the replay loop, and
   `rootedAt`. A **registry keyed by parent group id** — pure data, no
   parent/depth/order:

   ```ts
   // per-parent cluster set; carries the function + inputs so a re-cluster can rerun
   interface ClusterSet {
     clusters: ClusterMember[]     // membership Sets + slotToCluster (cluster_view_goals derive)
     function?: string             // cluster funcId
     inputs?: ClusterParam[]
     timestamp: number
   }
   type ClusterRegistry = Map<number, ClusterSet>   // parentGroupId → set
   ```

   `moveImagesToGroup` becomes a registry mutation + recompose; the cluster branches
   fall out of `updateSelection`/`applySha1Piles` naturally (property updates never
   touch the registry).
4. **CollectionManager** — **the inspection object.** Owns filter/sort/group +
   result + clusterManager, and exposes a stable API so views stop touching
   `.groupManager`. "Inspect this collection" = hold a `CollectionManager`.

### Compose: one final tree, two sources of truth

Two sources of truth (property tree + cluster registry), **one** composed
`GroupResult` that views read. A deterministic *apply-overlays* pass replaces the
ad-hoc `while (insert)` replay: after each property-tree rebuild, apply the registry
(and the sha1 overlay — same shape) to produce the final tree. Traversal, iterators,
`orderedIds`, `imageToGroups` stay exactly as simple as today because they consult
one tree, not two. This is the answer to "where does the overlay live": composed
**into** `GroupResult`, not a sibling the view stitches together.

## What moves out of GroupManager

- `index`, `imageToGroups`, `valueIndex`, `orderedIds`, `pileIndex`, `version`,
  `buildOrdinalRanges`, `emitResult` → **GroupResult**.
- `getGroupIterator` / `getImageIterator` / `findImageIterator`, `registerIterator`,
  `invalidateIterators`, `iterators` → **GroupResult** (it becomes the
  `IteratorHost`; `GroupIterator`/`ImageIterator` already depend only on that
  interface, so this is mostly re-pointing the host).
- `customGroups`, `addCustomGroups`/`delCustomGroups`/`clearCustomGroups`,
  `moveImagesToGroup`, `split`, `merge`, `delete`, `renameGroup`, `rootedAt`, the
  `while (insert)` custom-group replay in `group()`, and the cluster branches in
  `updateSelection` (`type == Cluster` skips, `dropMembership` exemption) and
  `applySha1Piles` → **ClusterManager**.
- `selectionNamespace` + all `select*/unselect*/toggle*` iterator methods →
  **inspection/view state** (CollectionManager or a per-view selection object;
  decide during Phase 3). It's view state, not tree state.

Left in GroupManager: `group()`, `computePropertySubGroup`, `updateSelection`
(property-only after cluster branches leave), `setGroupOption`/`delGroupOption`,
`verifyState`, sort hooks.

## CollectionManager inspection API (what views call instead of reaching in)

```ts
class CollectionManager {
  result: GroupResult                 // the composed tree (read-only to views)
  clusters: ClusterManager

  // iteration
  groupIterator(groupId?, opts?): GroupIterator
  imageIterator(groupId?, idx?, opts?): ImageIterator
  findImage(groupId, imageId): ImageIterator

  // cluster ops (delegate to ClusterManager, then recompose)
  cluster(parentId, funcId?, params?): Promise<void>
  merge(ids), splitNest(id, groups), deleteCluster(id), rename(id, name)
  moveImages(fromId, toId, ids)
  assignValue(groupId, propId, value)      // the badge write (committed, undoable)
  createDefaultValues(parentId, propId)    // "save all clusters" button

  // selection (namespace-scoped)
  select(...), toggle(...), clearSelection(ns)
}
```

`cluster()` keeps `actionStore` a pure RPC layer (call backend function, convert
result) with no view/collection knowledge: the use-case lives on the owner of the
result. "Which collection" is answered by *who you call*, not a parameter
`actionStore` must resolve — which kills the duplicated wiring in `GroupLine.vue`
and `ClusterView.vue` (each currently calls `addCustomGroups`/`split` on the raw
manager).

Then migrate the ~20 components: `collection.groupManager.result` →
`collection.result`; `collection.groupManager.getGroupIterator()` →
`collection.groupIterator()`; `collection.groupManager.split(...)` →
`collection.splitNest(...)`; and `ClusterView`'s `rootedAt` clone →
`collection.clusters` overlay + `derive`.

## Sequence (low-risk, each step shippable)

1. **Extract GroupResult.** Move the result fields + `buildOrdinalRanges` +
   iterator host onto a `GroupResult`; `GroupManager.group()` fills one. Point
   iterators at the result. Purely mechanical; behaviour identical. Unblocks
   everything.
2. **Extract ClusterManager.** Move `customGroups` + all group-ops + `rootedAt`
   out; strip cluster branches from `updateSelection`/`applySha1Piles`. Cluster
   ops become registry mutations + recompose. GroupManager is now pure.
3. **CollectionManager facade + component migration.** Add the inspection API,
   fold selection in, and rewrite the ~20 call sites off `.groupManager.*`. Do the
   scrollers (`TreeScroller`, `ClusterScroller`, `GridScroller`) last/carefully —
   they own iteration + virtualization.
4. **Cluster view rebuild** (separate note) — now that `clusters` + `derive`
   exist, replace `ClusterView`'s `rootedAt` clone per `cluster_view_goals.md`.

Order rationale: the result object first means the cluster extraction and the API
land on the clean structure instead of wrapping the old one.

## Open questions / risks

- **Selection home.** CollectionManager-level (one selection per collection) vs. a
  per-view selection object (the cluster view already uses its own namespaces:
  `cluster-view`, `cluster-detail-0/1`). Decide in Phase 3 — leaning per-view
  object keyed by namespace, owned by the view, backed by `columnStore`.
- **Scroller coupling.** `TreeScroller`/`GridScroller` consume `GroupIterator` +
  `orderedIds` heavily (15 + 5 iterator refs). Keep the iterator contract identical
  across the move so scrollers change only the *host* they get it from, not their
  logic.
- **Recompose trigger.** Cluster edits bump `result.version`; confirm no consumer
  still listens to a `GroupManager`-level event after the split (`onResultChange`
  is still emitted alongside `version` today).

Resolved by prior analysis / `cluster_view_goals.md`: overlay lives composed into
`GroupResult` (see *Compose* above); cluster sets are **reset** on a groupBy change
(no partial-survival policy).
