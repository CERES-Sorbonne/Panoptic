---
tags: [inventory, frontend]
zone: scrollers
---
# 04 · Main views: grid, tree & image scrollers

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** `ViewPanel` (one view island) and the virtualised scrollers it switches between: the tree/mosaic view, the grid/table view, and the groupless `ImageScroller`. Also the image cells, zoom and selection circles. The value editors inside the cells are in [[10 Value editing inputs]].

## Zone-level checks
- [ ] Virtual scrolling (`vue-virtual-scroller`) at very large sizes (1M instances, see `notes/managers_1m_optimization.md`).
- [ ] `ViewSelectionDropdown.vue` keeps a legacy name of the group view because it's "still present in persisted views". Check whether old persisted tabs still load.
- [ ] `GridScroller.vue` has a commented import of a removed `@/components/Scroller/…RecycleScroller.vue`. Remove it.
- [ ] `tree/Image.vue` vs `image/ImageCell.vue`: `ImageCell` is the instance-based variant "unlike tree/Image.vue (which is hard-coupled to the …)". Check whether they can share more code.

## Files: view island
- [ ] `src/components/layoutpanels/ViewPanel.vue` · 221 L. One view island: the header (view type, image size `RangeInput`) and the body, which is a tree, grid, map, graph, group or reco view.
- [ ] `src/components/layoutpanels/ViewSelectionDropdown.vue` · 127 L. Picks the view type. Handles the legacy group-view name.

## Files: tree (mosaic) scroller
- [ ] `src/components/scrollers/tree/TreeScroller.vue` · 536 L. Virtualised group tree of image lines and piles. Its selection namespace comes from the parent. Also used by `preview/ImagePreview.vue`.
- [ ] `src/components/scrollers/tree/GroupLine.vue` · 454 L. Group header row: select, stamp, fast-row dropdowns, cluster action button.
- [ ] `src/components/scrollers/tree/ImageLine.vue` · 105 L. One row of image cells. Resolves iterator slots to instance ids.
- [ ] `src/components/scrollers/tree/PileLine.vue` · 98 L. One row of sha1 piles, with column widths precomputed by the scroller.
- [ ] `src/components/scrollers/tree/Image.vue` · 248 L. Tree image cell: thumbnail, selection, property rows (`TreePropertyInput`).

## Files: grid (table) scroller
- [ ] `src/components/scrollers/grid/GridScroller.vue` · 370 L. Virtualised table view. Also used by `modals/image/Instances.vue`.
- [ ] `src/components/scrollers/grid/GridScrollerLine.vue` · 83 L. Dispatches a row to either a group row or an instance row.
- [ ] `src/components/scrollers/grid/GroupLine.vue` · 84 L. Group row in the table.
- [ ] `src/components/scrollers/grid/RowLine.vue` · 306 L. Instance row: image and property cells.
- [ ] `src/components/scrollers/grid/GridPropInput.vue` · 97 L. Picks the right cell or row input for a property type. Also used by `inputs/PropertyInputTable.vue`.
- [ ] `src/components/scrollers/grid/TableHeader.vue` · 123 L. Column headers with resize (`Resizable`). Re-evaluates on the tree version tick.

## Files: groupless image scroller
- [ ] `src/components/scrollers/image/ImageScroller.vue` · 385 L. Scroller over a plain instance list (no groups), derived from `TreeScroller`. Used by the cluster detail pane, reco panels, selection modal and similarity panel.
- [ ] `src/components/scrollers/image/ImageCell.vue` · 186 L. Instance-based image cell for `ImageScroller`.

## Files: image & interaction helpers
- [ ] `src/components/images/CenteredImage.vue` · 141 L. Thumbnail box that keeps the aspect ratio, with a module-level cache of already-loaded URLs. Used by 10 files.
- [ ] `src/components/Zoomable.vue` · 37 L. Wrapper that opens the zoom modal on a modifier key. Used by the map, image modal, grid rows, image cells and one more.
- [ ] `src/components/modals/zoomModal.ts` · 14 L. Shared state for the zoom modal (`Zoomable`, `ImageZoomModal`).
- [ ] `src/components/Resizable.vue` · 64 L. Border-box resize handle for table column widths.
- [ ] `src/components/inputs/SelectCircle.vue` · 73 L. Selection circle for images and groups. Used in 8 places.
