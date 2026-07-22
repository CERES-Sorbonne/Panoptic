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

Status as of this pass — validation harness added first (`vue-tsc`/`typescript`
devDeps + `npm run typecheck`; baseline **112** pre-existing errors). Each phase
verified by `typecheck` (no new errors) + `vite build`. **No runtime tests exist**,
so all phases are behaviour-preserving *by construction*, not runtime-verified.

1. ✅ **Extract GroupResult** — `src/core/group/GroupResult.ts` owns the result
   fields (`index`/`imageToGroups`/`valueIndex`/`orderedIds`/`pileIndex`), the
   `version`/`onResultChange`/`emitResult` signal, `buildOrdinalRanges`, and the
   iterators; it is the `IteratorHost` (iterators read `host.index`/`host.pileIndex`
   directly). `GroupManager` holds one and delegates; `version`/`onResultChange` are
   getters. Consumers unaffected.
2. ✅ **Extract ClusterManager** — `src/core/group/ClusterManager.ts` owns
   `customGroups` + all cluster ops (`add`/`move`/`split`/`merge`/`delete`/`rename`)
   + the replay (`reapplyAfter`). `types.ts` split into `ClusterOpsHost` (tree
   primitives, implemented by `GroupManager`) + `GroupOpsHost` (adds `customGroups`,
   implemented by `ClusterManager`). Typed against the interface → no import cycle.
   **Behaviour-preserving relocation only** — deferred to the cluster-view rebuild
   (step 4): stripping the cluster branches from `updateSelection`/`applySha1Piles`
   and moving `rootedAt` (both need the non-destructive Set overlay first, and there
   are no runtime tests to catch a behaviour change).
3. ✅ **CollectionManager inspection API + component migration** — added the
   delegating API (`result`/`version`/`groupState`/`clusters`/iterators/grouping/
   selection/cluster-ops; `groupState` avoids clashing with `CollectionState`).
   Migrated the ~9 components with collection-routed `collection.groupManager.<x>`
   accesses onto `collection.<x>`. **Deferred:** the 25 `props.groupManager`
   scroller/form props (`TreeScroller`/`GridScroller`/`GroupForm`) still receive a
   `GroupManager` directly — rewiring them to `CollectionManager`/`GroupResult` is a
   distinct change, best done with the cluster-view rebuild.
4. ⏭️ **Cluster view rebuild** (`cluster_view_goals.md`) — Set overlay + `derive`,
   delete `rootedAt`, strip the `updateSelection` cluster branches, rewire scrollers.

Order rationale: the result object first means the cluster extraction and the API
land on the clean structure instead of wrapping the old one.

## Open questions / risks

- **Selection home.** *Not yet moved.* Selection still lives on `GroupManager`
  (`selectionNamespace`, `select*`/`toggle*`), exposed via delegating methods on
  `CollectionManager`. Still to decide: CollectionManager-level vs. a per-view
  selection object (the cluster view already uses namespaces `cluster-view`,
  `cluster-detail-0/1`). Leaning per-view object keyed by namespace, backed by
  `columnStore` — do it with the cluster-view rebuild.
- **Scroller coupling.** Iterator contract kept identical: the only change was the
  *host* (`GroupResult` instead of `GroupManager`) and iterators reading
  `host.index`/`host.pileIndex`. Scroller logic untouched. The scrollers still take
  a `GroupManager` prop (deferred rewiring, step 4).
- **Recompose trigger.** `onResultChange` is still emitted alongside `version`
  (both on `GroupResult` now). Confirm no consumer depends on the emitted payload
  before removing the legacy event.
- **`rootedAt` still on GroupManager** (delegated from `CollectionManager.rootedAt`)
  — removed with the cluster-view rebuild. The one pre-existing typecheck error
  (`string | number` id) lives here and goes away with it.

Resolved by prior analysis / `cluster_view_goals.md`: overlay lives composed into
`GroupResult` (see *Compose* above); cluster sets are **reset** on a groupBy change
(no partial-survival policy).
