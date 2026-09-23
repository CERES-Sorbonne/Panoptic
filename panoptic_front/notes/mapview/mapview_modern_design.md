# The modern map view — decomposition, contracts, interactions

What the view looks like once it is written in the same style as `GroupView` /
`TreeScroller`. Assumes `mapview_sync_model.md`.

---

## 1. Decomposition

Today `MapView.vue` is ~490 lines doing six jobs: point geometry, group derivation,
colouring, layout, toolbar wiring and cluster orchestration. The scroller stack already shows
the shape that works — a view shell that owns layout + events, a "compute lines" layer, and a
dumb renderer.

```
ViewPanel                      passes width/height/imageSize/properties, as it does for every other view
└── MapView.vue                view shell: toolbar row + SplitLayout, event wiring. NO point math.
    ├── MapCanvas.vue          thin wrapper over useMapRenderer; owns the container ref + mouse mode
    ├── MapLegend.vue          the frontier as a list: swatch / name / count / actions  (replaces MapMenu)
    ├── MapToolbar.vue         map-specific controls ONLY                               (replaces Toolbar)
    └── (optional) ClusterDetailPane   reused as-is when a region is opened — see §4
```

and the logic moves to `src/mixins/mapview/` (where the three.js layer already lives):

| Module | Owns | Rebuilds on |
|---|---|---|
| `useMapPoints(mapId, atlas)` | `PointData[]`, `sha1 → point`, `slot → point`; calls `createMap` | map / atlas change |
| `useMapRegions(manager, points)` | the frontier (`visibleGroups`), `slot → region`, boxes, counts | structural version change |
| `useMapPaint(regions, selection, hover)` | colour / border / tint / z, then `updateBorder`+`updateTints` | region, selection or hover change |
| `useMapRenderer` | *(unchanged)* the three.js instance | mount |

Each is testable on its own and each has one invalidation trigger — which is the whole point
of the split (`mapview_sync_model.md` §5).

`MapRenderer` and friends stay as they are, plus the per-point `visible` flag.

---

## 2. Prop contracts

### `MapView.vue`

```ts
const props = defineProps<{
    manager: GroupInspector      // NOT CollectionManager — same prop the scrollers take
    mapOptions: MapOptions       // per-view display state (Pillar F)
    imageSize: number            // from the ViewPanel header, like every other view
    properties: Property[]       // visible properties, for the hover preview / region tooltip
    width: number
    height: number
    inputKey: string             // selection/provide namespace, as in the scrollers
}>()
const emit = defineEmits(['reco'])   // same escape hatch the tree view has
```

Every field is what `TreeScroller` / `ClusterScroller` already take. That is the point: after
this, `ViewPanel` renders all views through one shape, and the map becomes usable anywhere a
scroller is (an inspector pane, the reco panel, a modal).

Dropped: `tab` (never read), `collection` (replaced by `manager`).

### `MapOptions` — proposed shape

```ts
export interface MapOptions {
    selectedMap: number
    showPoints: boolean
    pointSize: number            // renamed from `imageSize`: it is the on-canvas point size,
                                 // NOT the view's image size. The name collision is why the
                                 // ViewPanel slider currently does nothing here.
    colorBy: 'groups' | 'none'   // replaces groupOption: 'property' | 'cluster'
    legendRatio: number          // SplitLayout position, so it survives a resize
}
```

`groupOption: 'property' | 'cluster'` disappears because the frontier makes the distinction
meaningless — a frontier holds property groups and cluster groups as peers, which is exactly
the display model of `cluster_view_goals.md`. Persisted states carry the old values, so
`verifyState`-style migration is needed: `'property' | 'cluster'` → `'groups'`, and an absent
`pointSize` inherits the old `imageSize`.

**Open question (decide before P0):** should `pointSize` remain map-local, or should the
header's `view.imageSize` drive it through a mapping? One slider is more coherent; two are
more honest (30–500 px cells vs a zoom-relative quad size). Recommendation: keep it map-local
under the clearer name, and drop the header slider for this view type.

---

## 3. Layout

Follow `GroupView.vue` exactly, because it is the same problem (a main surface plus an
inspectable side panel):

```
┌ map-toolbar (TOOLBAR_PX, own row, themed like .group-toolbar) ──────────────┐
├───────────────────────────┬─────────────────────────────────────────────────┤
│  MapCanvas                │  MapLegend            (SplitLayout, resizable,  │
│  (flex, min 0)            │  + hover preview       :hide-secondary when     │
│                           │  + opened region pane   collapsed)              │
└───────────────────────────┴─────────────────────────────────────────────────┘
```

- `SplitLayout direction="row"` with `:secondary-ratio="mapOptions.legendRatio"` replaces the
  fixed 280 px panel and its bespoke collapse; `:hide-secondary` gives the collapse for free.
- Theme variables throughout (`--island-surface`, `--bg-secondary`, `--border-color`,
  `--hover-bg`, `--radius-sm`) — no literal colours.
- The canvas gets explicit pixel dimensions from `width`/`height` minus the toolbar and the
  legend, mirroring how `GroupView` derives `primaryWidth` / `contentHeight`. `Resizable`,
  `mapWidth` and the `console.log` go away; the props are the single source of truth, as the
  scroller comment already states.

**Toolbar split.** Anything that is not map-specific leaves:

| Control | Where it goes |
|---|---|
| view type, properties toggle, split toggle | already in the `ViewPanel` header — remove nothing, just stop duplicating |
| image size | header (or map-local `pointSize`, per §2) |
| map picker, create map, delete map | `MapToolbar` — genuinely map-specific |
| pan / lasso+ / lasso− | `MapToolbar` |
| show points | `MapToolbar` |
| colour by | `MapToolbar` |
| cluster | `MapToolbar`, but retargeted — see §4 |

---

## 4. Interactions once the map reads the real tree

Parity first, then what the frontier makes newly possible.

### Kept, retargeted

- **Lasso ± → selection**, through `manager.selectionNamespace` instead of `global`.
- **Legend hover → dim others.** Unchanged, but it should also raise the shared hover
  (`mapview_sync_model.md` §3) so the tree pane highlights the same group.
- **Legend click → `lookAtRect`.** Keep. Add: it also *selects* the group
  (`toggleGroupIterator`), so the other panes scroll to it.
- **Cluster button.** Stop targeting the root. Target the same group the group view does — the
  frontier's empty bucket if there is one, else the focused region, else the root when the
  collection is ungrouped (the only case where root is a leaf and the run can actually
  succeed). Render `ClusterManager`'s `error` state instead of silently doing nothing
  (`mapview_current_state.md` §3, bug 1).
- **Remove clusters.** Same retargeting; it is `delCustomGroups` on the clustered group.

### New, and cheap because the tree is shared

- **Double-click a region (map or legend) → open/close that group.** The map becomes a
  navigation surface for the same tree: drill into a region and every pane follows. This is
  the single interaction that makes "synchronised" visible to the user.
- **Focus a region** — `visibleGroups({ root: groupId })` plus a camera fit. The map's
  equivalent of the group view's inspector: still one tree, just a subtree of it.
- **Open a region in a side pane.** `ClusterDetailPane` is already written, already does
  drag-and-drop between two panes, and already takes a plain `Instance[]`
  (`GroupView.vue:430`). Reuse it verbatim: click a region → its images in the pane, drag
  between two open regions → `moveImagesToGroup` + the target's value write (D4 of
  `cluster_view_goals.md`). No new drag machinery.
- **Lasso → new cluster.** The genuinely map-native operation, and the strongest reason to do
  this work: draw around a visual blob, and it becomes a real cluster group grafted into the
  tree (`addCustomGroups` / `clusterEmptyBucket` with a manually-built group). *Manual
  clustering*, on the surface where visual similarity is actually legible, whose output the
  group view can then assign a value to. Clustering is scaffolding, values are the durable
  output — and this gives a second, human way to build the scaffolding.
- **Lasso → assign**, once the above exists: drop a lassoed set onto a legend region and it
  takes that region's value. Same code path as the group view's drag (`assignClusterValue` /
  `groupTargetValue`), and it drains the queue the same way.
- **Reveal in tree** on a hovered point — the reverse of `lookAtRect`. Needs a scroll-to on
  the scrollers, which doesn't exist yet; note it and defer.

### Deliberately out of scope

- Reordering / sorting from the map (position is the embedding's, §2 of the sync note).
- Editing a point's position. The embedding is computed, not authored.

---

## 5. Empty and error states

The current view has none — no atlas means a blank canvas (`hasAtlas` is set and never
rendered), no maps means an empty dropdown, a failed cluster run means a button that does
nothing. Follow the group view's pattern (`.cluster-empty` with a `$t(...)` line and, when
useful, the action that fixes it):

| State | Message / action |
|---|---|
| no maps at all | "No projection yet" + the *create map* action inline |
| a map is selected but has no data for the current images | explain that the map predates these images; offer *recreate* |
| no atlas | "Preparing thumbnails" — this one is transient, show a spinner |
| cluster run failed (`not-a-leaf`, `no-groups`, backend error) | surface `runs[groupId].error` on the button |
| collection empty (filter matches nothing) | same copy as the other views |
</content>
