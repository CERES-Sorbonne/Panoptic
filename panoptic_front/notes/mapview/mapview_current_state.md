# Map view — what it does today, and where it disagrees with the architecture

Read against `src/components/mapview/` (`MapView.vue`, `Toolbar.vue`, `MapMenu.vue`,
`PointMapSelection.vue`, `ImagePreview.vue`) and `src/mixins/mapview/` (the three.js layer:
`MapRenderer`, `AtlasLayer(Manager)`, `HDLayer`, `LassoLayer`, `MapControl`, `SpatialIndex`,
`useMapRenderer`).

---

## 1. Functionality inventory

Everything the view can do today. This is the list a rewrite has to preserve.

### Map (embedding) management
- **Pick a projection** — `mapOptions.selectedMap` + `PointMapSelection`; maps come from
  `mediaStore` (`loadMaps` / `loadMapData`, data is a flat `[sha1, x, y, …]` array).
- **Create a map** — `ActionButton2 action="map"` in the toolbar, run over the collection's
  current images; on success it reloads the map list and selects the new one.
- **Delete a map** — trash button (`media.deleteMap`).

### Rendering (the three.js layer — the good part)
- Instanced quads textured from an **atlas**, with an **HD layer** that swaps in
  full-resolution textures for the points near the camera.
- **Points vs images** toggle (`showPoints`), **point/image size** (`imageSize`, 10–100).
- Per-point **colour, border + border colour, tint + tint alpha, z** — the channels the
  colouring code drives (`updateBorder` / `updateTints` / `updatePosition`).
- **Camera**: pan/zoom (`MapControl`), `lookAtRect` fly-to, `getCameraRect`.
- **Picking** via `SpatialIndex` → `onHover` → `hoverInstanceId`.
- **Lasso** (`LassoLayer`) → `onPointSelection(points)`.

### Interaction
- **Mouse modes**: `pan`, `lasso-plus`, `lasso-minus`.
- **Lasso → selection**: points → instance ids via `columnStore.getInstancesBySha1`, then
  `collection.selectImages` / `unselectImages` (`MapView.vue:334`).
- **Hover → preview**: the hovered instance is shown in the side menu (`Zoomable` +
  `CenteredImage`), with `lastValiderHoverId` keeping the last valid hover so the preview
  doesn't blank out when the cursor leaves a point.
- **Selection tint**: globally selected images are tinted blue (`MapView.vue:147`).

### Group colouring + legend
- `mapOptions.groupOption` = `'property' | 'cluster'` — colour by the root's non-cluster
  children, or by the root's cluster children (`generateGroups`, `MapView.vue:168`).
- Colours: `generateColors(n)`, overridden by the **tag colour** when the group is a tag
  value-group.
- Per group: name (`computeName` — group name, else the property value, else `Group N`),
  count, colour swatch, and a **bounding box** over its points (`computeBox`).
- **Legend** (`MapMenu.vue`): the group list; hover a row → that group's points keep their
  colour and everything else is dimmed grey (`updateColors`); click a row → `lookAtRect` on
  its box; a collapse toggle; the hover preview.

### Clustering
- **Cluster button** (toolbar, only in `'cluster'` colour mode) → `collection.cluster(rootId, req)`.
- **Remove clusters** (legend header ×) → `collection.delCustomGroups(rootId, true)`.
- Renders `collection.isClustering(rootId)` as the button's busy state.

---

## 2. Where it disagrees with the current architecture

### A. It is not written against the inspection surface

Every other view now takes a **`GroupInspector`** (`core/group/inspector.ts`) — the read +
view-state surface, deliberately without filter/sort/group configuration
(`collection_pipeline_audit_fixes.md` §*Facade*). `MapView` takes a concrete
`CollectionManager` and then reaches past it:

```ts
const filterSlots = props.collection.filterManager.result?.slots   // MapView.vue:256
```

That is pipeline internals — the *filter stage's* output rather than the group tree's
membership. It also means the map can never be fed a standalone `GroupManager` the way
`ImagePreview` / `RecoPanel` / the image modal feed the scrollers.

It is also the last consumer of two-source membership: `showMap` filters by
`filterManager.result.slots`, while `generateGroups` reads `group.slots`. Those agree today
only because nothing between them re-filters.

**DONE** — `MapView` now takes a `GroupInspector`. Membership is read from `result.root.slots`
only; `filterManager` is no longer touched. `selectImages` / `unselectImages` were added to the
inspector interface (both implementations already had them) so the lasso needs no concrete class.

### B. It reads one level of the tree, at the root, and calls that "the groups"

`generateGroups` takes `root.children` and partitions them by `type === Cluster`. Three
consequences:

- **Nested grouping is invisible.** With `groupBy.length >= 2` the map colours by the first
  level only; the leaf level — the one the group view calls the *target*
  (`cluster_view_goals.md`, "the target *is* the leaf grouping property") — never appears.
- **Open/close is ignored.** `Group.view.closed` drives what the tree scroller and the
  cluster scroller show; the map doesn't read it, so opening a group in the left pane changes
  nothing in the right one.
- **Clusters are looked for in the wrong place.** The group view clusters the **empty
  bucket** (`clusterEmptyBucket`), grafting cluster nodes at the leaf level. The map looks for
  clusters as *direct children of the root*. Whenever a grouping is active those are two
  disjoint sets, so the map's `'cluster'` mode shows nothing the group view produced, and vice
  versa. `isLeftover` ("No cluster") nodes are not distinguished either.
**DONE** — `groupOption` is gone (model, builder, toolbar dropdown, i18n usage). The map colours by
the tree's *display leaves*: `displayLeaves()` walks from the root and stops at a childless group or a
`view.closed` one, so nesting and open/close are both honoured. The cluster button now targets every
*true* leaf instead of the root, which is what fixes bug 1 below.

### C. Everything is rebuilt on every version tick

```ts
watch(() => props.collection.version.value, onGroupManager)  // → showMap(selectedMap)
```

`showMap` re-walks the whole `[sha1,x,y,…]` array, allocates a fresh `PointData` object per
point, rebuilds `sha1ToPoint`, rebuilds the slot→id table, and calls
`renderer.createMap(...)` — a full GPU re-upload. `version` is bumped by *any* tree change:
an open/close, a group sort, a selection-driven `updateSelection`, a cluster graft, a drag in
the group view.

The rest of the pipeline moved to O(delta) (`drain` / `reconcile` / scoped
`applySha1Piles`, see `collection_pipeline_audit_fixes.md` §*Performance*). The map didn't.
At ~1M images this is the single worst thing in the view.

Same class of problem, smaller: `rootInstances` (`MapView.vue:65`) materialises an
`Instance` object per image in the collection and is passed as a **prop** to the toolbar, so
it is re-evaluated on every version tick even though only the "create map" button ever reads
it. And `updateColors` calls `columnStore.getSelectedIds()`, allocating the full selected-id
array on every selection tick.

**DONE** — geometry is cached on `(mapId, root identity, root.slots identity, root.slots.length)`.
A version tick that cannot move a point (open/close, sort, cluster graft, selection) only recolours;
`createMap` runs on a real membership/map change. The length is part of the key because an incremental
add pushes into the same `root.slots` array. `rootInstances` became a getter passed to the toolbar
(`ActionButton2` accepts a function), and `updateColors` reads `isSelectedId(id, ns)` per point instead
of allocating `getSelectedIds()`.
### D. Selection is hard-wired to the global namespace

Scrollers take their namespace from the manager
(`provide('selectNamespace', … props.manager.selectionNamespace)`). The map reads
`columnStore.getSelectedIds()` with the default namespace and writes through
`collection.selectImages`. In practice both resolve to `global` today, but the map is the
only view that *can't* follow a namespaced manager — which blocks the map ever being used as
an inspector pane, and makes it the odd one out if selection moves off `GroupManager` (an
open decision in `collection_pipeline_audit_fixes.md`).

Related: the lasso maps a point to **all instances sharing its sha1**
(`getInstancesBySha1`). That matches sha1-pile mode and disagrees with the flat tree. It is
probably the behaviour you want on a map, but it is an unstated rule, and it is not the rule
the tree uses.

**DONE** — the map reads `collection.selectionNamespace` for both the selection tint
(`isSelectedId(id, ns)`, watched via `selectionTick(ns)`) and, through `collection.selectImages`, for
writes. The sha1 → all-instances lasso rule is kept, and now stated in a comment.
### E. sha1 vs slot identity is re-derived by hand

The map is keyed by **sha1** (one point per sha1); the tree is keyed by **slot**. `showMap`
rebuilds a `sha1 → {id, ratio}` table by scanning the whole column store, and
`generateGroups` de-duplicates each group's slots into sha1s with a local `Set`. `pileIndex`
(`GroupResult`) already models exactly this and is ignored.

Visible consequence: the legend's count is a **sha1 count** while every other view shows an
**instance count**. Same group, two numbers.

**DONE** — slot → sha1/id goes through `columnStore.sha1s()` / `instanceIds()` in one pass over the
root's slots; the hand-rolled full-column scan is gone. The sha1-vs-instance count disagreement went
with the legend.

### F. It doesn't participate in the layout language

- It is the only view `ViewPanel` doesn't pass `width` / `height` to (`ViewPanel.vue:140`);
  it sizes itself with `height: 100%`.
- `Resizable` is mounted with `:disabled="true"` and its `@resize` feeds `mapWidth`, whose
  only consumer is `watch(mapWidth, () => console.log(...))` (`MapView.vue:387`).
- The legend is a hard-coded 280 px panel with its own collapse toggle, instead of
  `SplitLayout` (which `GroupView` uses for exactly this, with a draggable divider and a
  ratio that survives a resize).
- `Toolbar.vue` and `MapMenu.vue` style themselves with literal colours
  (`rgb(246,247,249)`, `#384955`, `#ddd`, `white`) instead of the theme variables
  (`--bg-secondary`, `--hover-bg`, `--island-surface`, `--border-color`, `--radius-sm`) the
  reworked panels use. They will not follow a theme change.
- **`imageSize` exists twice**: `view.imageSize` (30–500) in the `ViewPanel` header, and
  `mapOptions.imageSize` (10–100) in the map toolbar. The header slider is live and does
  nothing on this view.
**DONE** — `MapMenu.vue` is deleted (legend, hover preview, group dim/lookAt); an inspection split view
can take its place later. `Resizable` / `mapWidth` / the `console.log`, the `tab` prop, `hasAtlas`, the
`.preview-overlay` rule and the unused imports went with it. `Toolbar.vue` now uses the theme variables.
Dead files removed: `ImageMap.vue`, `ImagePreview.vue`, `MapRendererView.vue`.

Still open: the map is the only view `ViewPanel` doesn't pass `width`/`height` to, and `view.imageSize`
in the panel header still does nothing on this view.

---

## 3. Three real bugs that fall out of the above

1. **The cluster button is a silent no-op whenever a grouping is active.**
   `ClusterManager.cluster` bails with `error: 'not-a-leaf'` when the target has non-cluster
   children (`ClusterManager.ts:83`). The map always targets the root, so as soon as
   `groupBy` is non-empty the root has property children and the run never starts. Nothing in
   the map renders the `error` state, so the button just does nothing.

2. **The legend's counts disagree with every other view** — sha1 count vs instance count
   (§E).

3. **Point geometry is discarded and re-uploaded on tree changes that cannot move a point.**
   An open/close, a sort, a value write on a non-grouped property — none of them change where
   a point sits, and all of them trigger a full `createMap` (§C).

Plus dead code to remove while in there: the `tab` prop (never read), `hasAtlas` (assigned,
never rendered), the `Resizable` / `mapWidth` / `console.log` triple, the unused
`.preview-overlay` rule, and the unused `sleep` / `nextTick` imports.
</content>
