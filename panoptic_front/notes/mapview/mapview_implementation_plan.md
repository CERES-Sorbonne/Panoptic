# Implementation plan

Each phase is shippable on its own and leaves the view working. P0–P2 are mechanical and
carry no design risk; P3 is where the actual behaviour changes; P4–P5 are the payoff.

Validation is the same as the rest of this refactor: `npm run typecheck` (no *new* errors
against the baseline) + `vite build` + hand-exercising the view. There are no runtime tests.

---

## P0 — Plumbing and hygiene *(no behaviour change)*

- `ViewPanel` passes `width` / `height` to `MapView`, like every other view.
- Delete: the `tab` prop, `hasAtlas`, `Resizable` + `mapWidth` + its `console.log`, the unused
  `.preview-overlay` rule, the unused `sleep` / `nextTick` imports.
- Size the canvas from the props instead of `height: 100%`.
- Replace literal colours in `Toolbar.vue` / `MapMenu.vue` with theme variables.
- Rename `mapOptions.imageSize` → `pointSize` with a migration for persisted states; resolve
  the duplicate image-size slider (see `mapview_modern_design.md` §2).

## P1 — Inspection contract

- `MapView` takes `manager: GroupInspector` instead of `collection: CollectionManager`.
- Membership comes from `manager.result.root.slots`, not `filterManager.result.slots`.
- Selection reads and writes through `manager.selectionNamespace`; `provide('inputKey', …)` /
  `provide('selectNamespace', …)` as the scrollers do.
- Use `pileIndex` for the sha1 fold instead of the hand-built `sha1 → id` scan, and align the
  legend's counts with the scrollers' (`mapview_current_state.md` §E).

Ships as: the map no longer disagrees with the rest of the app about *who* is in the
collection, and its counts stop lying. Colouring is still root-children-only.

## P2 — Split geometry from colouring

- Extract `useMapPoints` / `useMapRegions` / `useMapPaint`
  (`mapview_modern_design.md` §1).
- Add the per-point **visible** flag to `MapRenderer` so a filter change stops forcing
  `createMap`.
- Rewire the watchers: `createMap` only on map/atlas change; `version` ticks recolour.

Ships as: the O(1M) rebuild on every tree tick is gone. This is the phase that makes the
view usable at scale and it is worth doing even if nothing after it happens.

## P3 — The visible frontier *(the behavioural change)*

- Extract `visibleGroups()` + `frontierIndex()` into `src/core/group/frontier.ts`, and switch
  `GroupView.counts.walkVisible` onto it so there is one implementation, not two.
- Extract `groupColor()` (`mapview_sync_model.md` §4), with a sibling-stable palette index.
- `useMapRegions` colours by the frontier; drop `groupOption` / the `'property'` vs
  `'cluster'` split.

Ships as: opening, closing, grouping, nesting and clustering in any pane are visible in the
map. **This is the phase that delivers "every view shows the same tree".**

## P4 — Interactions

- Double-click a region → `openGroup`/`closeGroup`; legend click → `lookAtRect` + select.
- Retarget the cluster button (leaf / empty bucket, not the root) and surface
  `ClusterManager` errors.
- Shared hover (`mapview_sync_model.md` §3) — map ↔ scrollers, with the sticky-preview vs
  live-highlight distinction preserved.
- Empty / error states (`mapview_modern_design.md` §5).

## P5 — The map as a working surface

- `SplitLayout` legend + `ClusterDetailPane` reuse for an opened region.
- **Lasso → new cluster** (manual clustering grafted into the real tree).
- Lasso/drag → assign a region's value, reusing the group view's `assignClusterValue` path.
- Focus mode (`visibleGroups({ root })` + camera fit).

---

## Decisions needed, and when

| Decision | Blocks | Recommendation |
|---|---|---|
| One image-size slider or two? | P0 | Two, renamed: `pointSize` is map-local; drop the header slider for map views |
| Where shared hover lives — `columnStore` vs per-tab composable | P4 | Per-tab composable; hover is view state |
| Palette index: frontier position vs sibling position vs id hash | P3 | Sibling position — a local change must stay local |
| Lasso identity: sha1 or instance? | P1 | Keep sha1 (current behaviour), but state the rule in code — it is the sha1-pile rule, not the tree's |
| Does the map get its own selection namespace, or share the pane's? | P1 | Share the manager's; a map-local namespace only if it is ever used as an inspector pane |
| Migration for persisted `MapOptions` | P0 | Silent default in a `verifyState`-style pass; nothing user-visible |

## Things not to do

- **Don't build the O(delta) region index up front.** The O(n) typed-array pass on structural
  change is a few ms and the delta path has an obvious successor when a profile asks for it
  (`mapview_sync_model.md` §5).
- **Don't rewrite `MapRenderer`.** The three.js layer is the part of this view that is
  already right; it needs one flag, not a redesign.
- **Don't sync camera or scroll position.** Explicit jump gestures only.
- **Don't make the map own group state.** It reads the tree and calls the inspector's ops —
  the same rule that made the group view work (`GroupView.vue:110`: highlighting is the only
  state that view still owns).
</content>
