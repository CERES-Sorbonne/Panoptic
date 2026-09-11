---
tags: [inventory, frontend]
zone: app-shell
---
# 01 · App shell, routing & layout

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** boot (`index.html` → `main.js` → `App.vue`), the router and its views, the IDE-style shell (`AppShellLayout` with its toolbar, activity bar, sidebar split and islands), the top bar and the tab bar.
Paths are relative to `panoptic_front/`.

## Zone-level checks
- [ ] ⚠ **Double-mounted modals?** These modals are imported both by `App.vue` and by `views/MainView.vue`: `ExportModal2`, `FirstModal`, `FolderSelectionModal`, `ImageModal`, `ImageZoomModal`, `ImportModal`, `NotifModal`, `PropertyModal`, `SettingsModal`, `TagModal`. `FirstModal`, `FolderSelectionModal` and `NotifModal` are also imported by `views/HomeView.vue`. Check whether they are mounted in more than one place, which would mean double listeners and double dialogs.
- [ ] ⚠ `main.js` is imported by `dropdowns/FolderOptionDropdown.vue` and `dropdowns/FileSourceOptionDropdown.vue` (`import { i18n } from '@/main'`), which is a circular import. Switch both to `@/locales/i18n`.
- [ ] `router/index.js` ships the dev routes `/test` (`SandboxView`) and `/test-points` (`TestView`) to production. Gate them on `import.meta.env.DEV`, or drop them.
- [ ] `main.js` still has commented-out `customize.scss` and VueFinder lines. Remove them.
- [ ] The whole shell got its layout in June 2026. The old shell (`ProjectView`, `PanopticView`, `Menu`, `TabNav`, `mainview/MainView`) is dead ([[99 Unused files]]).

## Files: boot & routing
- [ ] `index.html`. Vite HTML entry: `#app`, `/favicon.ico`.
- [ ] `src/main.js` · 39 L. Creates the app. It loads Pinia, `vue-virtual-scroller`, the router, i18n and `vue3-tour`, plus the global CSS (Inter, Bootstrap, bootstrap-icons, `@vueform/toggle`, `vue3-tour`). It also re-exports `i18n`.
- [ ] `src/App.vue` · 167 L. The root component:
  - `RouterView`
  - the global keyboard handling (Ctrl/Cmd+Z undo/redo, which it doesn't take over inside text fields)
  - the global modals
  - imports `assets/theme.css`
- [ ] `src/router/index.js` · 30 L. Hash history. Routes: `/` HomeView, `/view` MainView, plus the dev routes `/test` and `/test-points`. `panopticStore.ts` and `views/MainView.vue` also import it.
- [ ] `src/views/MainView.vue` · 169 L. The project page (route `/view`). It builds `AppShellLayout` with `TopBarPanel` (toolbar), `LeftBarPanel` (activity bar), `SidebarLayout` / `SplitLayout` holding `FolderPanel`, `PropertyPanel`, `FilterIsland` and `ViewPanel`, and `TabProvider`. The islands stay hidden until `uiStore` has loaded.
- [ ] `src/views/SandboxView.vue` · 63 L. Dev scratch page for plain HTML/CSS experiments (`/#/test`).
- [ ] `src/views/TestView.vue` · 351 L. Dev page for the point/camera experiments behind the map view (`/#/test-points`).

## Files: layout primitives
- [ ] `src/layouts/AppShellLayout.vue` · 83 L. The pure shell frame (PyCharm "island" style): a `#toolbar` and an `#activity` slot plus the content.
- [ ] `src/layouts/SidebarLayout.vue` · 151 L. Sidebar plus main content, with a resize gutter.
- [ ] `src/layouts/SplitLayout.vue` · 293 L. Two-pane split where the primary pane grows and the secondary keeps its size. Also used by `GroupView.vue`.
- [ ] `src/layouts/IslandPanel.vue` · 69 L. A rounded, bordered, shadowed "island" card. Used by the filter, folder, property and reco panels and 2 others.

## Files: top bar, activity bar & tabs
- [ ] `src/components/layoutpanels/TopBarPanel.vue` · 269 L. The top toolbar:
  - left: project title and actions
  - right: user, notifications, language
  - also hosts `TabPanel`, `HistoryDropdown`, `TaskProgressBar`, `ColumnStatusDropdown` and `SelectionStamp`

  Last changed 2026-09-11.
- [ ] `src/components/layoutpanels/LeftBarPanel.vue` · 122 L. Left activity bar that toggles the Folder and Properties tool windows (`uiStore`).
- [ ] `src/components/layoutpanels/TabPanel.vue` · 239 L. Tab bar island: the open tabs (`TabButton`), a tab-picker dropdown, and the add-tab button.
- [ ] `src/components/layoutpanels/TabProvider.vue` · 31 L. Provides the current tab to its descendants ("Pillar D", see `data/useCurrentTab.ts`).
- [ ] `src/components/mainview/TabButton.vue` · 172 L. One tab: rename, close, and scrolling itself into view when it becomes active. It's the only live file left in `mainview/`.
- [ ] `src/components/TabContainer.vue` · 32 L. Small tab wrapper (it uses `TabManager` and `tabStore`). Used by `PropertyPanel.vue`.
- [ ] `src/components/dropdowns/HistoryDropdown.vue` · 210 L. Undo history in two modes: `own` (the store's own commit stacks, which Ctrl+Z acts on) and `all` (every commit, fetched from the backend). Heavily changed on 2026-09-11.
- [ ] `src/components/dropdowns/TaskProgressBar.vue` · 290 L. Backend task progress. It maps raw task class names and English step names to translated labels.
- [ ] `src/components/dropdowns/ColumnStatusDropdown.vue` · 465 L. Load status per property column (loading / empty / loaded counts). The panel is `position:fixed` so it escapes the toolbar's `overflow:hidden`.
