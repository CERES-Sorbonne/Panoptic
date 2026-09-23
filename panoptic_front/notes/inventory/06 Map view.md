---
tags: [inventory, frontend]
zone: map
---
# 06 · Map view

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the 2D projection view: images placed at map coordinates (computed by a plugin action), rendered with three.js from atlas sheets, with hover preview, HD preview and lasso selection. The docs are in `notes/mapview/`.

## Zone-level checks
- [ ] ⚠ **The folder name is misleading.** `src/mixins/mapview/` holds plain TypeScript/three.js classes, not Vue mixins. Consider moving it to `src/core/map/` or `src/components/mapview/render/`.
- [ ] The `three` chunk is about 525 KB. Check that it only loads with the map view (it's currently a separate chunk).
- [ ] Atlas texture cache (`AtlasLayerManager`) vs the backend `GenerateAtlasTask`, which rewrites atlas 0 in place. Check cache invalidation when the atlas is regenerated.
- [ ] Lasso (`LassoLayer` + `robust-point-in-polygon` + `simplify`) and `SpatialIndex` (`kdbush`) on large maps.
- [ ] WebGL resource disposal on unmount (`useMapRenderer`).

## Files: components
- [ ] `src/components/mapview/MapView.vue` · 722 L. Hosts the renderer and wires in the collection, selection, clusters (`ClusterManager`), hover and the side preview.
- [ ] `src/components/mapview/Toolbar.vue` · 114 L. Map header bar: map picker, the 'map' action (run on the collection's current content), sizes.
- [ ] `src/components/mapview/PointMapSelection.vue` · 85 L. Picks which map or projection to show (`SelectDropdown` plus `mediaStore`).

## Files: renderer (`src/mixins/mapview/`)
- [ ] `src/mixins/mapview/useMapRenderer.ts` · 42 L. Composable controller that creates and disposes the `MapRenderer`.
- [ ] `src/mixins/mapview/MapRenderer.ts` · 261 L. Scene, camera, render loop, layer composition. Point mode vs image mode.
- [ ] `src/mixins/mapview/MapControl.ts` · 268 L. Pan, zoom, pointer picking (returns null outside the canvas), lasso interaction.
- [ ] `src/mixins/mapview/AtlasLayerManager.ts` · 209 L. Loads atlas sheets into textures (cached by atlas id and sheet) and manages the per-sheet layers.
- [ ] `src/mixins/mapview/AtlasLayer.ts` · 211 L. Instanced image layer for one sheet, with z-spread tie-breaking inside a priority tier.
- [ ] `src/mixins/mapview/InstancedImageMaterial.ts` · 234 L. Shader material for instanced atlas quads.
- [ ] `src/mixins/mapview/HDLayer.ts` · 298 L. High-resolution preview over the hovered point (the scale comes from the header slider).
- [ ] `src/mixins/mapview/HDImageMaterial.ts` · 150 L. Material for HD images (fits the image in a 1×1 box, keeping the aspect ratio).
- [ ] `src/mixins/mapview/HoverPointLayer.ts` · 96 L. Single overlay mesh for the hovered point in point mode.
- [ ] `src/mixins/mapview/LassoLayer.ts` · 244 L. Draws the lasso and computes the selection (point-in-polygon, path simplification).
- [ ] `src/mixins/mapview/SpatialIndex.ts` · 55 L. `kdbush` index over the points for picking and lasso.
