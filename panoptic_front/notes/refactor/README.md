# Collection refactor — everything you need to finish it

The live working set. Everything here is current as of 2026-07-25 (rework-front,
committed through `87f97a28`). Notes outside this folder are background or history;
nothing here depends on reading them.

Read in this order.

## 1. `collection_pipeline_audit_fixes.md` — **start here**

What the post-refactor audit found and fixed, and — at the end, under *"Left open —
these need a decision"* — the actual remaining work. That list is the closest thing
to a TODO for this refactor.

## 2. `collection_inspection_mission.md` — the mission, status DONE

Why `GroupManager` was split into engine / `GroupResult` / `ClusterManager`, and
`CollectionManager` made the inspection facade. All four phases landed. Its status
block records one **revoked** design (the Set overlay + per-render `derive`) — the
code, not that sketch, is the authority.

## 3. `cluster_view_goals.md` — the group view's model

The paradigm behind the view formerly called the cluster view (assigning *is*
grouping; clusters are scaffolding, property values are the output), and the settled
performance decision: clusters are **grafted real `Group` nodes** in the one property
tree, not a derived overlay. Explains `clusterEmptyBucket` / `drain` / `reconcile`.

## 4. `tree_scroller_update_flow.md` + `tree_scroller_computelines_optimization.md`

The scroller side. Needed for two of the open items: the scrollers still take a
`GroupManager` prop rather than a `CollectionManager`, and `computeLines` still builds
a line object per image over the whole dataset before virtualising.

## 5. `collection_architecture_simplification.md` — partially implemented

§4 (one collection per view, multiple per tab) shipped and is in `TabManager`. The
rest — state/compute/result separation — is still a proposal, and is the wider frame
if you take on the scroller-contract change.

---

## Open work, in one place

- **Scrollers take a `GroupManager` prop.** `ViewPanel` passes `collection.groupManager`
  into `TreeScroller` / `GridScroller` / `ClusterScroller`. Moving them to
  `CollectionManager` is a real change to the scroller contract.
- **Iterator invalidation is inert.** `GroupIterator` only self-registers when
  `options.register` is true and nothing passes it, so `invalidateIterators()` always
  walks an empty list. Either wire it into the scroller-owned iterators or delete the
  mechanism.
- **Selection still lives on `GroupManager`.** Decide: `CollectionManager`-level, or a
  per-view object keyed by namespace.
- **Dead API to prune or keep** — `propagateSelect`/`propagateUnselect`,
  `Group.view.selected`, the `onlyPropertyGroups` iterator option,
  `CollectionState.instances`.
- **`collection.delete(groupId)`** reads like it deletes the collection.
- **`filterBySelection`** — a deselected image lingers instead of being filtered out.
  Existing behaviour preserved deliberately; changing it is a product call.
- **Whole-dataset line construction** in both scrollers (see §4 above).

## Not verified at runtime

Every phase of this refactor was validated by `npm run typecheck` (`vue-tsc`) and
`vite build` only. There are no runtime tests. The group view has been exercised by
hand and works as intended; the rest of the pipeline has not been systematically
smoke-tested.
