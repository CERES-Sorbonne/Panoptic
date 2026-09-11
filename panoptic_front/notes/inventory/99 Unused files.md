---
tags: [inventory, frontend, unused]
---
# 99 · Unused frontend files

Back to [[00 Frontend inventory]]

Every file here is tracked in git but **not reachable from `src/main.js`** (or, outside `src/`, not referenced by anything). Each entry gives:
- **size** and **dates**: `created → last touched`
- **last reference**: the most recent commit that changed a mention of the file name elsewhere in `src/`, which is usually the commit that removed its last import
- **what it was**, **what replaced it**, and a suggested **action**

`npm run typecheck` (`vue-tsc`) only checks files reachable from the entry, so dead `.vue` files are never type-checked. That's why files importing the deleted `@/data/store` don't show up as errors.

Paths are relative to `panoptic_front/`.

---

## A. Old project shell, superseded by the June 2026 layout rework
The cut-over is commit `2a0fbe04` "save wip" (2026-06-06): the router stopped using `ProjectView`, and `views/MainView.vue` now builds the IDE-style shell (`AppShellLayout` + `TopBarPanel` / `LeftBarPanel` / `FolderPanel` / `PropertyPanel` / `FilterIsland` / `ViewPanel`). Everything in this section went dead with it, and can be deleted as a group.

- [ ] `src/views/ProjectView.vue` · 184 L · 2025-08-02 → 2026-06-06 · last reference `2a0fbe04` (2026-06-06).
  - **What it was:** the project page: `Menu` (left sidebar) + `TabNav` (top) + `mainview/MainView` + `Tutorial` + the `DataLoad` overlay.
  - **Replaced by:** `src/views/MainView.vue`.
- [ ] `src/views/PanopticView.vue` · 68 L · 2023-05-16 → 2026-08-05 · last reference `2a0fbe04`.
  - **What it was:** the old root view: `RouterView` plus every global modal (`PropertyModal`, `FolderSelectionModal`, `ExportModal2`, `ImageModal`, `ImageZoomModal`, `SettingsModal`…) plus `UserSelection` for server mode.
  - **Replaced by:** `App.vue` (global modals) and `home/UserSelector.vue`.
- [ ] `src/components/mainview/MainView.vue` · 127 L · 2024-11-09 → **2026-07-29** · only importer is `ProjectView`.
  - **What it was:** the per-tab content area: the `ContentFilter` toolbar plus a Grid/Tree/Graph/Map switch. It also had a side-effect `import '@/data/socketStore'`.
  - **Replaced by:** `layoutpanels/ViewPanel.vue` + `ViewSelectionDropdown.vue`.
  - ⚠ Edited on 2026-07-29 ("Map view integration"), after it went dead. Check that the map wiring done there also exists in `ViewPanel`.
- [ ] `src/components/mainview/ContentFilter.vue` · 230 L · 2024-11-09 → **2026-09-11** · only importer is the dead `mainview/MainView.vue`.
  - **What it was:** the toolbar above the view: search, view mode, image size (`RangeInput`), filter/group/sort forms, `SelectionStamp`, `ToggleReload`, `ColumnStatusDropdown`.
  - **Replaced by:**
    - `FilterIsland` + `FilterPanel`: search, forms, instance/image mode
    - `TopBarPanel`: `ColumnStatusDropdown`, `SelectionStamp`, `HistoryDropdown`
    - `ViewPanel`: size slider
  - Touched today (`72e9faeb`), but only to remove a commented-out `HistoryDropdown`.
- [ ] `src/components/mainview/TabNav.vue` · 89 L · 2024-11-09 → **2026-08-08** "translations" · last reference `2a0fbe04`.
  - **What it was:** the old top bar: the tab list (`TabButton`), user, notifications, language.
  - **Replaced by:** `TopBarPanel.vue` for the right side (its header comment says "like TabNav.vue") and `TabPanel.vue`, which still uses `TabButton`.
  - ⚠ Translated on 2026-08-08, after it went dead.
- [ ] `src/components/menu/Menu.vue` · 213 L · 2023-05-16 → 2026-08-05 · only importer is `ProjectView`.
  - **What it was:** the old left sidebar: project title and actions, the folder tree (`FolderList2`), `TaskStatus`, `TabContainer`, `DraggablePropertyList`.
  - **Replaced by:** `TopBarPanel` (title and actions; its comment says "like Menu.vue"), `LeftBarPanel`, `FolderPanel`, `PropertyPanel`.
- [ ] `src/components/FolderTree/FolderList2.vue` · 205 L · git path `foldertree/FolderList2.vue` · only importer is `Menu.vue`.
  - **What it was:** the folder tree of the old sidebar (folder filter).
  - **Replaced by:** `FolderTree/FolderList.vue` in `FolderPanel`.
- [ ] `src/components/menu/DraggablePropertyList.vue` · 42 L · 2025-07-18 → 2026-08-05 · only importer is `Menu.vue`.
  - **What it was:** drag-to-reorder property list (`vuedraggable`).
  - **Replaced by:** `layoutpanels/PropertyGroupPanel.vue` + `menu/PropertyGroup.vue`.
- [ ] `src/components/menu/TaskStatus.vue` · 28 L · 2024-01-29 → 2026-02-21 · only importer is `Menu.vue`.
  - **What it was:** task name and done/total/failed text.
  - **Replaced by:** `dropdowns/TaskProgressBar.vue` in the top bar.
- [ ] `src/components/loading/DataLoad.vue` · 117 L · 2025-01-06 → 2026-08-05 · only importer is `ProjectView`.
  - **What it was:** a centred "loading project data" panel with per-column progress (`columnStore` / `dataStore`, `LoadWheel`, `Percentage`).
  - **Replaced by:** `dropdowns/ColumnStatusDropdown.vue` (loading/empty/loaded counts per column, in the top bar).
- [ ] `src/components/loading/Percentage.vue` · 23 L · 2025-01-06 · only used by `DataLoad`.
  - **What it was:** a percentage label.
  - **Replaced by:** as above.
- [ ] `src/components/toggles/ToggleReload.vue` · 84 L · 2024-05-31 → 2026-02-03 · only importer is `ContentFilter`.
  - **What it was:** the auto-reload toggle plus a manual reload button for a dirty collection (`collection.setAutoReload`, `runState.isDirty`, `update()`).
  - **Replaced by:** ⚠ **nothing.** No live component calls `setAutoReload` any more.
  - **Action:** decide whether to drop the feature (and the `autoReload` state in `CollectionManager`) or put the toggle into `FilterPanel`.
- [ ] `src/components/UserSelection.vue` · 52 L · 2025-08-02 → 2026-08-05 · only importer is `PanopticView`.
  - **What it was:** "Server Mode: Select a profile" list.
  - **Replaced by:** `home/UserSelector.vue` (`connectUser` / `disconnectUser`) on `HomeView`.
- [ ] `src/assets/main.css` · 601 L · 2023-05-16 → **2026-06-08** · its import was dropped in `2a0fbe04`.
  - **What it was:** the old global stylesheet.
  - **Replaced by:** `src/assets/theme.css` (imported by `App.vue`). It defines the same 58 class selectors, and no class that exists only in `main.css` is used by a live component.
  - Edited on 2026-06-08, after it was dropped. Delete it.
- [ ] `src/components/layoutpanels/PropertyRow.vue` · 55 L · 2026-06-06 → 2026-06-07 · last reference `21b2dd46` (2026-06-08 "wip iiif").
  - **What it was:** the first prototype of the new property panel rows (a click toggles `visibleProperties`).
  - **Replaced by:** `menu/PropertyGroup.vue` + `menu/PropertyOptions.vue` inside `PropertyGroupPanel`.
- [ ] `src/components/mainview/ContentFilterSim.vue` · 198 L · 2026-06-06 · last reference `43938baa` "working splitview".
  - **What it was:** a static mock of `ContentFilter` "with no store or TabManager dependencies", used while designing the split view.
  - **Replaced by:** `FilterPanel.vue`.
- [ ] `src/components/mainview/ImageView.vue` · 69 L · 2026-06-06 · last reference `43938baa`.
  - **What it was:** a static thumbnail-grid mock (numbered fake tiles) from the same design session.
  - **Replaced by:** the real scrollers in `ViewPanel`.

## B. Tag tree and property row built on the pre-Pinia `globalStore` (these can't even compile)
The old global store `src/data/store.ts` was removed during the Pinia rewrite (`119e3c32` 2023-12-22, deleted in `5d6814c2` 2024-01-02). These files still import it.

- [ ] `src/components/tagtree/TagTree.vue` · 66 L · 2023-05-16 → 2026-08-05 · last reference `af3af3fd` (2024-07-27 "integrate tag graph to tag modal").
  - **What it was:** a tag tree with "add root tag" (`globalStore.addTag`).
  - **Replaced by:** `tags/TagTree.vue` in `TagModal`.
  - Note that `tagtree/TagBadge.vue`, in the same folder, *is* still used.
- [ ] `src/components/tagtree/TagNode.vue` · 194 L · 2023-05-16 → 2024-05-24. Tag node with select/expand propagation. **Replaced by:** `tags/TagTree.vue` / `tags/TagListScroller.vue`.
- [ ] `src/components/FolderTree/TagList.vue` · 28 L · git path `foldertree/TagList.vue`. Recursive `<ul>` of `TagNode`; its only importer is the dead `tagtree/TagTree.vue`. **Replaced by:** as above.
- [ ] `src/components/FolderTree/TagNode.vue` · 88 L · git path `foldertree/TagNode.vue`. A near-duplicate of `tagtree/TagNode.vue`, also on `globalStore`. **Replaced by:** as above.
- [ ] `src/components/properties/Property.vue` · 35 L · 2023-05-16 → 2023-06-11 · last reference `0b619696` (2023-11-10).
  - **What it was:** a property row with a visibility toggle (`globalStore.setPropertyVisible`).
  - **Replaced by:** `menu/PropertyOptions.vue`.

## C. Superseded components from 2023–2025
- [ ] `src/components/preview/FilterPreview.vue` · 41 L · 2023-10-27 "new filter ui" → 2024-05-29 · last reference `8a293584` (2024-11-02 "clean up inputs, ready for tests").
  - **What it was:** a read-only one-line summary of a filter (property, operator, value).
  - **Replaced by:** the editable `filter/FilterRow.vue` + `FilterValueInput.vue`.
- [ ] `src/components/preview/PropertyPreview.vue` · 23 L · 2023-10-27 → 2024-05-29 · only used by `FilterPreview`. Property name and icon.
- [ ] `src/components/preview/PropertyValuePreview.vue` · 73 L · 2023-10-27 → 2024-01-16 · only used by `FilterPreview`. Formatted value.
- [ ] `src/components/preview/TagPreview.vue` · 23 L · 2023-10-27 → 2024-07-10 · only used by `PropertyValuePreview`. Tag badges.
- [ ] `src/components/tags/TagInputDropdown.vue` · 73 L · 2023-11-09 → 2024-10-28 · last reference `bfeaa22a` (2025-11-25).
  - **What it was:** `TagInput` inside a `Dropdown`, with `TagBadge` chips.
  - **Replaced by:** `property_cell_input/CellTagInput.vue` (grid, filter, stamp) and `scrollers/tree/TreeTagInput.vue` (tree cells, `cellPopup`).
- [ ] `src/components/tags/TagPropInputDropdown.vue` · 74 L · 2023-11-09 → 2024-07-04 · last reference `ea83d42e` (2024-12-04).
  - **What it was:** binds `TagInputDropdown` to an instance's value.
  - **Replaced by:** as above.
  - It also contains the stray `import { Exception } from 'sass'`.
- [ ] `src/components/ContentEditable.vue` · 148 L · 2023-07-27 → 2024-12-04 · last reference `8a293584` (2024-11-02).
  - **What it was:** the first `contenteditable` wrapper (grid text and tag inputs).
  - **Replaced by:** `property_inputs/ContentEditable.vue` (176 L, used by `property_inputs/TextInput.vue`).
- [ ] `src/components/images/ImageSimi.vue` · 74 L · 2023-05-25 → 2024-08-07 · last reference `946f1517` (2023-11-07).
  - **What it was:** a thumbnail plus score cell for the old similarity view.
  - **Replaced by:** `modals/image/Similarity.vue` + `scrollers/image/ImageScroller.vue` / `ImageCell.vue`.
- [ ] `src/components/scrollers/tree/ClusterButton.vue` · 49 L · 2023-11-18 · last reference `6886da8d` (2024-05-22).
  - **What it was:** a magic-wand button with a cluster-count input on tree group lines.
  - **Replaced by:** the cluster action through `actions/ActionButton.vue` in `scrollers/tree/GroupLine.vue`.
- [ ] `src/components/menu/ExpandOption.vue` · 79 L · 2023-05-16 → 2024-12-04 · last reference `85b2d436` (2023-06-11).
  - **What it was:** a caret expander for property options in the 2023 menu.
  - **Replaced by:** `utils/Collapsable.vue` / `menu/PropertyGroup.vue`'s own expand.
- [ ] `src/components/property_preview/ColorPreview.vue` · 34 L · 2024-10-24 · last reference `e1482170` (2024-10-28 "updated and cleaned tree scroller inputs").
  - **What it was:** a colour swatch.
  - **Replaced by:** the chips in `scrollers/tree/TreeColorInput.vue` and `property_cell_input/CellColorInput.vue`.
- [ ] `src/components/TabMenu.vue` · 48 L · 2024-02-03 → 2025-01-17 · removed in `d05839c0` (2025-07-20 "wip new setting modal").
  - **What it was:** a segmented control (options plus i18n keys) used by the old settings modal.
  - **Replaced by:** `utils/PageWindow.vue` (left option list) in the settings, import and file-source modals.
- [ ] `src/components/settings/GeneralSettings.vue` · 27 L · 2024-02-08 → 2025-07-22 · last reference `d05839c0`.
  - **What it was:** the three-column "general" tab of the old settings modal (`ActionSettings`, `VectorSettings`, `ImageSettings`).
  - **Replaced by:** `SettingsModal` + `PageWindow` pages (`ImageSettings`, `VectorSettings`, `DataSettings`, `PluginSettingsWindow`).
- [ ] `src/components/ActionSettings.vue` · 89 L · 2024-02-07 → 2024-12-04 · only importer is `GeneralSettings`.
  - **What it was:** a default-function picker for each action type.
  - **Replaced by:** the default-action selectors (`ActionSelect` / `ActionSelectFlat`) in `settings/VectorSettings.vue`.
- [ ] `src/components/settings/PluginSettings2.vue` · 123 L · 2025-07-22 → 2026-08-05 · **never referenced** in history.
  - **What it was:** an alternative plugin params editor (base params plus per-function defaults, `setPluginParams`).
  - **Replaced by:** `settings/PluginSettings.vue` (used by `PluginSettingsWindow`).
- [ ] `src/components/actions/ActionSelect2.vue` · 106 L · 2025-12-01 · last reference `74ecb78f` (2025-12-01 "clean and nice action buttons").
  - **What it was:** a compact default-action selector.
  - **Replaced by:** `actions/ActionButton2.vue` / `ActionSelectFlat.vue`.
- [ ] `src/components/actions/ActionSelectButton.vue` · 161 L · 2025-11-25 → 2026-08-05 · last reference `0058f2c1` (2025-12-02).
  - **What it was:** action picker plus params plus run button in one component.
  - **Replaced by:** `actions/ActionButton2.vue` (hand-off mode).
- [ ] `src/utils/inputTree.ts` · 165 L · 2023-05-16 · its last user was `ActionSelectButton`.
  - **What it was:** keyboard focus traversal between inputs (`nextInput`).
  - **Replaced by:** nothing directly. `data/inputStore.ts` now handles tree-cell navigation.
- [ ] `src/components/scrollers/image/DualImageScroller.vue` · 55 L · 2026-07-12 "cluster view drag and drop + rename and recluster" · **never referenced**.
  - **What it was:** two `ImageScroller`s side by side for dragging images between groups.
  - **Replaced by:** `layoutpanels/GroupView.vue` + `ClusterDetailPane.vue`.
- [ ] `src/components/TabTmp.vue` · 17 L · 2025-01-29 · **never referenced**. A debug placeholder that prints the tab id. **Replaced by:** nothing.
- [ ] `src/views/TestView-3D.vue` · 266 L · 2025-11-25 · **never routed**.
  - **What it was:** a three.js 3D point-cloud experiment.
  - **Replaced by:** the 2D renderer in `mixins/mapview/*` and the `/#/test-points` `TestView.vue`.
- [ ] `src/components/tsne/SpatialView.vue` · **0 L** · 2024-10-25 "making ml plugin a real plugin".
  - **What it was:** the t-SNE view, emptied when that feature moved into the PanopticML plugin.
  - **Replaced by:** `mapview/MapView.vue` (maps computed by plugin actions).
- [ ] `src/utils/api.ts` · 9 L · 2023-10-31. `saveFile(response, title)`, a blob-download helper. **Replaced by:** nothing imports it; if a download helper is needed again, reuse it.
- [ ] `src/utils/helpers.ts` · 10 L · 2023-05-16. A `DefaultDict` Proxy class from the first version. **Replaced by:** nothing.

## D. `create-vue` scaffold leftovers (never used, 2023-05-16)
- [ ] `src/components/icons/IconCommunity.vue`
- [ ] `src/components/icons/IconDocumentation.vue`
- [ ] `src/components/icons/IconEcosystem.vue`
- [ ] `src/components/icons/IconSupport.vue`
- [ ] `src/components/icons/IconTooling.vue`

  These are the Vite template's welcome-page icons. `icons/PanopticIcon.vue` in the same folder is the only one in use.
- [ ] `src/assets/base.css`. Empty (0 bytes), from the template.
- [ ] `src/assets/logo.svg`. Empty (0 bytes), from the template.

## E. Unused assets
- [ ] `src/assets/customize.scss` · 15 L. Bootstrap SCSS overrides. The import is commented out in `main.js` (`// import '@/assets/customize.scss'`), and the prebuilt `bootstrap.min.css` is loaded instead. **Replaced by:** `theme.css` overrides.
- [ ] `src/assets/images/IIIF-logo-colored-text.svg` · 2026-06-08 "iiif icons and file sources shown in ui". Added with the IIIF UI, but `FolderPanel` uses `/icons/iiif.svg` instead. **Action:** delete, or switch to it.
- [ ] `public/icons/clustering.svg`
- [ ] `public/icons/network.svg`
- [ ] `public/icons/network2_white.svg`
- [ ] `public/icons/network_2.svg`
- [ ] `public/icons/network_black.svg`

  All five were added on 2026-01-15 ("test version for the map view"), and nothing references them now. The map and cluster controls use bootstrap-icons. Every build copies them into `panoptic_back/panoptic/html/icons/`.

## F. Documentation sitting in `src/`
- [ ] `src/data/UI_STORE_GUIDE.md` · 224 L · 2026-06-06. How to use `uiStore`. **Action:** move it into `notes/`.
- [ ] `src/layouts/LAYOUT_PATTERN_EXAMPLE.md` · 84 L · 2026-08-05. Example of composing `AppShellLayout` / `SidebarLayout` / `SplitLayout` / `IslandPanel`. **Action:** move it into `notes/`.

## G. Tooling and misc outside `src/`
- [ ] `.eslintrc.cjs` · 2023-05-16. A legacy ESLint config (`vue3-essential` + `@vue/eslint-config-prettier` + `@rushstack/eslint-patch`). **ESLint 10.4 ignores it**, so `npm run lint` fails with "ESLint couldn't find an eslint.config.(js|mjs|cjs) file". **Replaced by:** nothing yet. **Action:** write `eslint.config.js` (flat config) or drop the lint script and the ESLint deps.
- [ ] `notes.txt` · 2023-05-16. The very first notes, in French, about the data structure (`/images` → sha1 list, metadata fetch) and store organisation. **Replaced by:** the `notes/` vault.
- [ ] `test/bench.js` · 2025-11-25 "save wip". A standalone Node benchmark of JS data structures (100k elements). It's not part of any test runner.
- [ ] `test/test_images.py` · 2024-10-25. A PIL script that generates coloured test images. **Replaced by:** `panoptic_back/test/scripts/generate_images.py` and the committed fixtures.

## H. npm packages that nothing imports
Not files, but the same cleanup (`package.json`):
- [ ] `kd-tree-javascript` + `@types/kd-tree-javascript`. **Replaced by** `kdbush` in `mixins/mapview/SpatialIndex.ts`.
- [ ] `camera-controls`. Never imported; `mixins/mapview/MapControl.ts` is custom.
- [ ] `splitpanes`. **Replaced by** the custom `layouts/SplitLayout.vue` / `SidebarLayout.vue`.
- [ ] `vue-contenteditable`. **Replaced by** the in-house `property_inputs/ContentEditable.vue`.
- [ ] `vue-use-popperjs`. **Replaced by** `floating-vue` in `dropdowns/Dropdown.vue`.
- [ ] `bootstrap5-toggle`. **Replaced by** `@vueform/toggle`.
- [ ] `d3` + `@types/d3`. No import anywhere. The charts use `echarts`.
- [ ] `sass-loader`. A webpack loader that Vite doesn't use. Keep `sass` itself: `tutorials/Tutorial.vue` uses `<style lang="scss">`.
- [ ] `@rushstack/eslint-patch` and `@vue/eslint-config-prettier`. Only `.eslintrc.cjs` uses them (see G).
