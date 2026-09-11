---
tags: [inventory, frontend]
zone: group-reco
---
# 05 · Group, cluster & recommendation views

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the "group" view, a workspace over the collection's groups and clusters with drag-and-drop, renaming and re-clustering, and the group recommendation workspace. Both are selected in `ViewPanel`.

## Zone-level checks
- [ ] `RecommendView.vue` (838 L) and `GroupView.vue` (764 L) are the two largest components in this zone. Look for logic that belongs in `core/`.
- [ ] Cluster run / re-cluster flow: `ClusterManager` → `actionStore` → backend. Check cancel and error states.
- [ ] Drag and drop between cluster panes. The unused `DualImageScroller.vue` was an earlier attempt at this ([[99 Unused files]]).
- [ ] `ClusterLine.vue` hard-codes the height reserved for the input row. It "must match" another constant, so check that they stay in sync.

## Files
- [ ] `src/components/layoutpanels/GroupView.vue` · 764 L. The group workspace: a `ClusterScroller` of group cards, plus the inspector panes (`ClusterDetailPane`) in a `SplitLayout`.
- [ ] `src/components/layoutpanels/ClusterDetailPane.vue` · 185 L. One cluster inspector pane: header with close button and property input, then an `ImageScroller`.
- [ ] `src/components/scrollers/cluster/ClusterScroller.vue` · 349 L. Virtualised wall of cluster cards. Images are sized on the stable workspace width.
- [ ] `src/components/scrollers/cluster/ClusterLine.vue` · 652 L. One row of cluster cards: preview images, badge, typed property input, selection.
- [ ] `src/components/scrollers/cluster/ClusterPropertyInput.vue` · 91 L. Single-row typed property editor for a cluster card and the inspector header. Reuses the `Tree*Input` rows.
- [ ] `src/components/cluster/ClusterBadge.vue` · 39 L. Cluster size/score badge. Also used by `tree/GroupLine`.
- [ ] `src/components/layoutpanels/RecommendView.vue` · 838 L. Recommendation workspace: header (view title, group selection), the source group and the recommended images, and accept/reject.
- [ ] `src/components/layoutpanels/RecoPanel.vue` · 215 L. One labelled, collapsible panel inside the reco workspace, wrapping a virtualised `ImageScroller`.
- [ ] `src/components/layoutpanels/GroupSelect.vue` · 108 L. Picks the group to work on (chip button plus popup).
