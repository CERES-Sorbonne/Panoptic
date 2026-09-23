# Collection refactor — everything you need to finish it

The live working set. Everything here is current as of 2026-09-21 (rework-front, committed
through `5a6893b9`). Notes outside this folder are background or history; nothing here depends
on reading them.

Where a note describes something that was designed but never built, it says so inline
with a **Not built yet** marker. The design is kept — it is still the intent — but the
marker means: do not read it as a description of the code.

Read in this order.

## 1. `collection_pipeline_audit_fixes.md` — **start here**

What the post-refactor audit found and fixed. Its *"Left open"* list is history now;
the current TODO is **Open work** at the bottom of this file.

## 2. `collection_inspection_mission.md` — the mission, status DONE

Why `GroupManager` was split into engine / `GroupResult` / `ClusterManager` /
`GroupNavigator`, and `CollectionManager` made the inspection facade. All four phases
landed. The cluster half has since been rebuilt a second time: the `customGroups`
registry the note describes is gone, replaced by `ClusterOverlay` (a dense
slot→node map per bucket, from which every pile's `slots` is derived). Read the note
for the *why*; read `ClusterOverlay.ts` for the *what*.

## 3. `cluster_view_goals.md` — the group view's model

The paradigm behind the view formerly called the cluster view (assigning *is*
grouping; clusters are scaffolding, property values are the output), and the settled
performance decision: clusters are **grafted real `Group` nodes** in the one property
tree, not a derived overlay. The design is settled and still governs; several of the
mechanisms it names are marked **Not built yet** (a `reconcile` hook, the reset button,
the save-all-clusters button, the full D4 drag rules).

## 4. `tree_scroller_update_flow.md` + `tree_scroller_computelines_optimization.md`

The scroller side. Still needed for the one live perf item: `computeLines` builds a
line object per image over the whole dataset before virtualising. (The scroller prop
question is settled — they take a `GroupInspector` now.)

## 5. `collection_architecture_simplification.md` — partially implemented

§4 (one collection per view, multiple per tab) shipped and is in `TabManager`. The
rest — state/compute/result separation — is still a proposal, and is the wider frame
if you take on the scroller-contract change.

---

## Open work, in one place

Four items that stood here are **done or gone**, and are recorded at the end of this
section so nobody re-opens them.

### Needs a product decision (not touched)

- **`filterBySelection` semantics.** `CollectionManager.setDirty` drops non-selected
  instances from the dirty set entirely, so an image that gets *deselected* lingers in
  the collection instead of being filtered out. Preserved deliberately; changing it is
  a product call.
- **`collection.delete(groupId)`** reads like it deletes the collection. Renaming it
  touches `CollectionManager` / `GroupManager` / `ClusterManager` / `groupOps`.
- **The unreachable cluster ops.** `split`, `merge`, `delete`, `renameGroup` and the
  public `addCustomGroups` / `clusterEmptyBucket` facades are implemented on
  `GroupManager` *and* `CollectionManager` and called by nothing in `src/` (the
  clustering path goes through `cluster()` → `applyClusters` → `addCustomGroups`
  instead). `cluster_view_goals.md` lists `clusterEmptyBucket` as one of its three
  O(delta) primitives and its merge / delete-pile scenarios read as shipped features;
  today they are unreachable from the app. Decide: wire them into the cluster card
  grid, or delete the surface. Do **not** delete it silently — it is public API.

  Smaller unreachable surface found in the same sweep, same decision, same caution:
  `GroupManager.emptyRoot`, `GroupNavigator.setSelectionNamespace` (and therefore
  `columnStore.ensureNamespace` via that path — every navigator sits on `'global'`),
  `ClusterOverlay.hasClusters`, `groupOps.applyClusterGroups` (used only inside its
  own module), `GroupResult.onResultChange` (zero listeners — the legacy event the
  mission note asked about), `GroupIteratorOptions.ignoreClosed` (declared, correctly
  propagated since the `at()` fix, passed by nobody), and the exported-but-unimported
  `slotOrder.slotPosition`, `sort.sortGroupByProperty`, `sort.sortGroupBySize`,
  `sha1Piles.pileSlots`.

### Known-open performance

- **Whole-dataset line construction.** `TreeScroller` builds an `ImageIterator` per
  image and `GridScroller` a line object per image, for the entire collection, on every
  version bump; both virtualise only *after* that. See
  `tree_scroller_computelines_optimization.md`.
- **`applySha1Piles()` in `updateSelection` is still the full sweep.** The structural
  ops now scope it (`only` = `ClusterOverlay.containerGroups(c)`), but the incremental
  path calls it with no argument, so every value edit rebuilds the pile overlay for the
  whole tree. With `sha1Mode` off it returns immediately, so this only bites in sha1
  mode.
- **`orderSlots` verifies the whole root array when nothing was appended.** The root is
  dirty on every update and gets no `appendedFrom` entry, so `cut == slots.length` and
  the "is the prefix ordered?" loop walks the whole collection — one position lookup per
  slot — before returning at the `cut == n` early exit. Correct, but O(n) per update for
  an array the update did not touch.

### Known-open correctness

- **Cluster error text is not translated.** `clusterErrorText` (`ClusterManager.ts`)
  returns English literals, and both `ClusterLine.vue` and `GroupLine.vue` render
  `` `Clustering failed: ${…}` `` raw. It is user-visible and bypasses vue-i18n.
  (Group *names* are raw strings by design everywhere in the tree — `"No cluster"`,
  `"Merged"`, `"Cluster N"` — so those are a separate question.)
- **`ClusterManager.emptyBucketId` is written and never read** (set in
  `clusterEmptyBucket`, cleared in `clear()`). `Group.isLeftover` was in the same state
  and now drives the leftover card's muted title in `ClusterLine.vue`; `emptyBucketId`
  still has no reader.

### Closed since the last pass — do not re-open

- ~~Scrollers take a `GroupManager` prop.~~ **Done.** They take a `GroupInspector`
  (`src/core/group/inspector.ts`); `ViewPanel` passes `collection` straight in. See
  §Facade in `collection_pipeline_audit_fixes.md`.
- ~~Iterator invalidation is inert.~~ **Gone.** Neither `options.register` nor
  `invalidateIterators` exists in `src/` any more; the mechanism was deleted rather than
  wired up. Staleness is now answered by `GroupIterator.isCurrent` (identity against
  `IteratorHost.rev`), which `ImageModal` uses.
- ~~Selection still lives on `GroupManager`.~~ **Moved.** It lives in
  `GroupNavigator` over namespaced masks in `columnStore`; `GroupManager` and
  `CollectionManager` only delegate. The *decision* that remains is whether a per-view
  selection object should replace the namespace string — see
  `collection_inspection_mission.md` §Open questions.
- ~~`ImageIterator.fromGroupIterator` has no guard on its source.~~ **Fixed** in
  `fc9ec3a7`: it returns `undefined` when `it?.isValid` is false, and again when the
  constructed `ImageIterator` is invalid.
- ~~Dead API to prune: `propagateSelect`/`propagateUnselect`, `Group.view.selected`,
  `onlyPropertyGroups`, `CollectionState.instances`.~~ **All four are gone** from the
  group system. (`propagateSelect` still exists in `components/tagtree/TagNode.vue` and
  `components/folder_tree/TagNode.vue`, which are unrelated tag-tree helpers.)

## How this is verified

- `npm run typecheck` (`vue-tsc --noEmit`) — the gate. Baseline is **0 errors**.
- `npm test` — the group/cluster suite: `test/group/build.mjs` bundles the specs with the
  project's own vite (the Pinia stores aliased to the headless stubs in
  `test/group/harness/stubs/`, DEV on so `ClusterOverlay.checkInvariants` runs), then
  `node --test` runs them. **136 tests** cover the value parser, group slots, iterators,
  dead nodes, new arrivals, cluster runs, sha1 piles, resync, tag deletion and the
  overlay invariants. Start at `test/group/README.md`.
- `npm run test:sim` — a seeded random simulation (`test/group/sim/`) that drives the real
  engine against a model and checks the invariants after every op.
- Add a spec rather than re-deriving a harness: the phases of this refactor predate the
  suite and were behaviour-preserving *by construction*, so the tests are what protects
  them now.

What is still **not** covered: the rest of the pipeline (filter/sort config, the scrollers,
the views) has no runtime test and has not been systematically smoke-tested. The group view
has been exercised by hand.
