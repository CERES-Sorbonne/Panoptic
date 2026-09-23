# Mission: extract clusters + iterators from GroupManager; make CollectionManager the inspection object

> **Status: DONE** (rework-front). All four phases landed; the group view (née
> cluster view) runs on the result. The current TODO is the **Open work** list in
> `README.md`, not here and not in `collection_pipeline_audit_fixes.md`.
>
> **Superseded since:** the cluster half was rebuilt a second time, after this note
> was written. Everything below that names `customGroups`, `reapplyAfter`,
> `reconcile`, `attachCustomGroups`, `collectSlots` or a `ClusterRegistry` is
> describing code that **no longer exists** — none of those identifiers is in `src/`.
> What replaced them is `src/core/group/ClusterOverlay.ts`; see *What the cluster
> half actually is now* below before reading any "as built" paragraph here.
>
> **Revoked while implementing (and then partly un-revoked):** this note originally
> proposed a non-destructive **Set overlay + per-render `derive`** for clusters (the
> `ClusterSet` registry sketched under *Target architecture*).
> `cluster_view_goals.md` §"Performance & data flow" settled the opposite — clusters
> are **grafted as real `Group` nodes** into the one property tree, because at 1M
> images a per-render derive re-pays O(|empty|) on the hot path while grafted nodes
> cost nothing. That decision still stands. What came back is the *membership*
> half of the idea: authored membership lives in a side structure (`ClusterOverlay`)
> and each pile's `slots` is derived from it — but derived once per rebuild / per
> edit, not once per render, and the grafted nodes are still real tree nodes.

Prerequisite refactor for `cluster_view_goals.md`. Folds in the prior "separate
cluster logic from GroupManager" analysis (verified against the code at the time)
and adds one goal: **CollectionManager becomes the object views use to inspect a
collection.**

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
| `GroupView.vue` | 15 |
| `CollectionManager.ts` | 14 |
| `ClusterScroller.vue` | 10 |
| `RecommendView.vue`, `ImageModal.vue`, `MapView.vue`, `ContentFilter.vue`, … | 8→1 |

`CollectionManager` already owns the filter→sort→group orchestration but just
exposes `groupManager` as a public field, so every consumer bypasses it. "Which
collection am I inspecting" is answered by grabbing a manager, not by an object.

**Verified against the code as it stood when this note was written** (i.e. *before*
any of the four phases; kept as the record of what the refactor started from — none of
it describes the code today):

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
3. **ClusterManager** — owns the cluster overlay and every cluster edit
   (`clusterEmptyBucket`, `drain`, `merge`, `split`, `delete`, `rename`, `move`).
   Replaces the cluster half of `GroupManager` and `rootedAt`.

   > ~~Originally specced as a pure-data `ClusterRegistry: Map<parentGroupId,
   > ClusterSet>` of membership Sets, derived per render.~~ ~~**Revoked** — as built,
   > the registry is `customGroups: {parentGroupId: Group[]}`, holding the grafted
   > nodes themselves; `reapplyAfter` re-grafts them after each rebuild, intersecting
   > each cluster's slots against its target's current slots. The cluster branches in
   > `updateSelection`/`applySha1Piles` were replaced by an explicit
   > `ClusterManager.reconcile()`.~~
   >
   > **Both of the above are obsolete.** `customGroups`, `reapplyAfter` and
   > `reconcile` no longer exist. See *What the cluster half actually is now*.
4. **CollectionManager** — **the inspection object.** Owns filter/sort/group +
   result + clusterManager, and exposes a stable API so views stop touching
   `.groupManager`. "Inspect this collection" = hold a `CollectionManager`.

### Compose: one final tree, two sources of truth

Two sources of truth (property tree + cluster registry), **one** composed
`GroupResult` that views read. After each property-tree rebuild the registry (and
the sha1 pile overlay) is applied to produce the final tree. Traversal, iterators,
`orderedIds`, `imageToGroups` stay exactly as simple as today because they consult
one tree, not two. This is the answer to "where does the overlay live": composed
**into** `GroupResult`, not a sibling the view stitches together.

*As built:* there is **no replay loop**. `GroupManager.group()` calls
`clusters.resyncAll()` once, near the end of the rebuild, and it makes exactly **one pass per container** over its
bucket's current slots. The deterministic apply-overlays pass this note originally
predicted is what landed in the end, just not under that name: `resync(c)` clears the
container's piles, walks `parent.slots` once, and pushes each slot into the leaf its
owner resolves to. Membership, display order and the leftover all fall out of that one
loop, so there is nothing to iterate to a fixed point.

## What the cluster half actually is now

Read this before any "as built" paragraph above it. The authority is
`src/core/group/ClusterOverlay.ts` and `src/core/group/ClusterManager.ts`.

- **`ClusterOverlay`**, one **`ClusterContainer` per clustered grouping leaf** (the
  "bucket"). A container holds:
  - `owner: Uint32Array` — a dense **slot → node index** map. `0` means "owned by no
    pile", which routes to the level's leftover. This is the single source of truth for
    membership.
  - `drained: Uint32Array` — slot → the node it was *released* from, `0` for none. A
    release is therefore **reversible**: an image that comes back to the bucket (undo,
    a cleared value) returns to the pile it left instead of the leftover.
  - `table: (ClusterNode | null)[]` — the node table. Index 0 is unused so `0` can mean
    unowned. **Sub-clusters live in the same container**: depth is carried by each
    node's `up` link, not by more containers, so any number of levels fits one flat
    array per bucket.
  - `epoch: number` — the `columnStore` slot generation the maps were written against.
    `columnStore` re-mints slots on reset, so a container whose epoch no longer matches
    is dropped rather than misread.
- **Dead-chain routing.** `kill(c, idx)` marks a node dead; its images are *not*
  rewritten. They resolve to the nearest live ancestor on the next pass. That is what
  makes "delete a pile" and "drop a sub-clustering" the same operation with different
  chains.
- **A pile's `slots` is derived, never authored.** `resync(c)` empties every pile of the
  container, walks `parent.slots` once in display order, and pushes each slot into the
  leaf its owner resolves to (honouring a `drained` record on the way). Membership,
  display order and the leftover all come out of that one loop. A filter, a sort or a
  reload therefore cannot lose a pile: excluded images are simply not visited, and the
  next build that includes them puts them back where the map says.
- **Three entry points, not a replay:** `resyncAll()` after a full rebuild;
  `resyncDirty(groupIds)` after an incremental update — **gated on the dirty group ids**
  (the buckets the edit touched), not on a property; and a bare `resync(c)` inside each
  structural op.
- **The queue-drain is `release()`, not a slot intersection.** `ClusterManager.drain`
  releases the slots from their pile and records where they were in `drained`, then
  resyncs that container. The reverse — an undo putting the image back — is honoured by
  `restoreDrained` inside the next `resync`.
- **Change detection.** `resync` returns whether the pass changed anything, decided by a
  `fingerprint` over the container (each node's slots, wiring, and the two counts a card
  reads). A pass that produced the same picture reports no change, so a write to an
  unrelated property does not rebuild both scrollers for the whole dataset
  (`cluster_view_goals.md` G4).
- **Invariants.** `import.meta.env.DEV` only, `checkInvariants` verifies I1 (every image
  of the bucket lands in exactly one leaf), I2 (every owner value names a real node of
  *this* container), I3 (the authored totals and the owner array agree), I4 (the epoch
  survived the pass) and I5 (a leaf's slots follow the bucket's display order).

What this means for the sections above: there is no `customGroups` registry, no
`reapplyAfter`, no `reconcile`, no `attachCustomGroups`, no `collectSlots`, no
`ClusterRegistry` and no `while (insert)` loop. `ClusterManager` keeps the *ops*
(`cluster`, `addCustomGroups`, `moveImagesToGroup`, `renameGroup`, `split`, `merge`,
`delete`, `delCustomGroups`, `clearCustomGroups`, `clusterEmptyBucket`, `drain`) and
the clustering **action** end to end; the ops themselves are free functions in
`groupOps.ts` over a `GroupOpsHost`, each one "write the map, then resync".

## What moves out of GroupManager

*The plan, kept as written. Two deviations: the iterator **invalidation** listed below
(`registerIterator` / `invalidateIterators` / `iterators`) was never wired up and has
since been deleted outright — `GroupIterator.isCurrent` answers staleness instead — and
the cluster half moved as described but was then rebuilt on `ClusterOverlay`.*

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

*A sketch, not the shipped signature list.* The shape landed — views hold a
`CollectionManager` and stop touching `.groupManager` — but the method names are the
real ones on the class (`split` / `delete` / `renameGroup` / `moveImagesToGroup`,
`getGroupIterator` / `getImageIterator` / `findImageIterator`). `assignValue` and
`createDefaultValues` were never built: the per-card write lives in
`GroupView.assignClusterValue`, and there is no save-all-clusters button.

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
and `GroupView.vue` (each currently calls `addCustomGroups`/`split` on the raw
manager).

Then migrate the ~20 components: `collection.groupManager.result` →
`collection.result`; `collection.groupManager.getGroupIterator()` →
`collection.groupIterator()`; `collection.groupManager.split(...)` →
`collection.splitNest(...)`; and `ClusterView`'s `rootedAt` clone → reading the
collection's own tree directly (the clusters are already grafted into it).

## Sequence (low-risk, each step shippable)

Status as of this pass — validation harness added first (`vue-tsc`/`typescript`
devDeps + `npm run typecheck`; baseline **112** pre-existing errors *at the time*, since
driven to 0). Each phase was verified by `typecheck` (no new errors) + `vite build`; no
runtime tests existed yet, so the phases are behaviour-preserving *by construction*.

> **Since then (2026-09-21, `fc9ec3a7`):** the group/cluster engine does have runtime tests —
> `npm test` (136 specs under `node --test`) and `npm run test:sim`. See `test/group/README.md`
> and the "How this is verified" section of `README.md`.

1. ✅ **Extract GroupResult** — `src/core/group/GroupResult.ts` owns the result
   fields (`index`/`imageToGroups`/`valueIndex`/`orderedIds`/`pileIndex`), the
   `version`/`onResultChange`/`emitResult` signal, `buildOrdinalRanges`, and the
   iterators; it is the `IteratorHost` (iterators read `host.index`/`host.pileIndex`
   directly). `GroupManager` holds one and delegates; `version`/`onResultChange` are
   getters. Consumers unaffected.
2. ✅ **Extract ClusterManager** — `src/core/group/ClusterManager.ts` owns the
   cluster membership + all cluster ops
   (`add`/`move`/`split`/`merge`/`delete`/`rename`). `types.ts` split into
   `ClusterOpsHost` (tree primitives, implemented by `GroupManager`) + `GroupOpsHost`
   (adds the overlay, implemented by `ClusterManager`). Typed against the interface →
   no import cycle. **Behaviour-preserving relocation only** at this point; the
   cluster branches in `updateSelection`/`applySha1Piles` and `rootedAt` were handled
   in step 4.
   *(At the time the membership was `customGroups` + a `reapplyAfter` replay; both
   were later replaced by `ClusterOverlay` — see above. The ops split and the host
   interfaces are unchanged, and the ops themselves now live in `groupOps.ts` as free
   functions over `GroupOpsHost`.)*
3. ✅ **CollectionManager inspection API + component migration** — added the
   delegating API (`result`/`version`/`groupState`/`clusters`/iterators/grouping/
   selection/cluster-ops; `groupState` avoids clashing with `CollectionState`).
   Migrated the ~9 components with collection-routed `collection.groupManager.<x>`
   accesses onto `collection.<x>`. **Deferred:** the 25 `props.groupManager`
   scroller/form props (`TreeScroller`/`GridScroller`/`GroupForm`) still receive a
   `GroupManager` directly — rewiring them to `CollectionManager`/`GroupResult` is a
   distinct change, best done with the cluster-view rebuild.
4. ✅ **Cluster view rebuild** (`cluster_view_goals.md`) — shipped as the **group
   view**. `rootedAt` and the tree clone are gone; the view reads the collection's
   own tree with the clusters grafted in. `ClusterManager` gained
   `clusterEmptyBucket` (graft + materialise the leftover pile) and `drain` (the
   O(delta) assign primitive).
   *Since then:* `reconcile()` — the `updateSelection` hook this step added — is gone,
   replaced by `resyncDirty(dirtyGroupIds)`; `clusterEmptyBucket` survives but has no
   caller, because the card grid clusters through the generic `cluster()` path
   instead. The scroller props **were** rewired afterwards (they take a
   `GroupInspector` now), and the iterator-invalidation mechanism was deleted rather
   than wired up. See `README.md` §Open work for what is actually left.

Order rationale: the result object first means the cluster extraction and the API
land on the clean structure instead of wrapping the old one.

## Open questions / risks

- **Selection home.** *Partly moved; the design question remains.* The mechanism now
  lives in `GroupNavigator` (`src/core/group/GroupNavigator.ts`) over **namespaced
  masks in `columnStore`**; `GroupManager` and `CollectionManager` only delegate, and
  nothing writes `Group.view.selected` any more. What has **not** happened is the
  per-view selection *object*: a navigator carries a single `selectionNamespace`
  string, and `setSelectionNamespace` — the only thing that would change it — is
  called from nowhere, so every navigator sits on `'global'`. The per-pane namespaces
  that do exist (`cluster-detail-0/1`, `dual-image-left/right`) are `ImageScroller`'s
  own `selectNamespace` prop, a parallel path that does not go through the navigator
  at all. Deciding between the two is still open.
- **Scroller coupling.** *Settled.* Iterator contract kept identical: the only change
  was the *host* (`GroupResult` instead of `GroupManager`) and iterators reading
  `host.index`/`host.pileIndex`. The scrollers now take a `GroupInspector`
  (`src/core/group/inspector.ts`), which both `GroupManager` and `CollectionManager`
  implement, so `ViewPanel` passes `collection` and the preview / recommend / modal
  panels pass their standalone `GroupManager` through the same prop.
- **Recompose trigger.** *Answered: nothing depends on it.* `GroupResult.emitResult`
  still does `version.value++` **and** `onResultChange.emit(this)`, but
  `onResultChange` has **zero listeners** — there is no `addListener` call against it
  anywhere in `src/`. Every consumer watches the `version` tick instead
  (`TreeScroller.vue` says so explicitly). The legacy event can be removed.
  (`FilterManager.onResultChange` and `SortManager.onResultChange` are separate
  emitters on their own objects; as it happens they have no listeners either.)

Resolved by prior analysis / `cluster_view_goals.md`: overlay lives composed into
`GroupResult` (see *Compose* above); cluster sets are **reset** on a groupBy change
(no partial-survival policy).
