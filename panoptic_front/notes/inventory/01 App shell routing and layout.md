---
tags: [inventory, frontend]
zone: app-shell
---
# 01 · App shell, routing & layout

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** boot (`index.html` → `main.ts` → `App.vue`), the router and its views, the IDE-style shell (`AppShellLayout` with its toolbar, activity bar, sidebar split and islands), the top bar and the tab bar.
Paths are relative to `panoptic_front/`.

## Zone-level checks

*Reviewed 2026-09-21: every check below was resolved by the layout/data cleanups of
September 2026 (`9d09512f`, `f63b5267`, `3a7388d2`, `20baa607`).*

- [x] ~~**Double-mounted modals?**~~ Resolved. `App.vue` no longer imports any modal; the
  global modals are mounted once, by `views/ProjectView.vue`. `views/HomeView.vue` mounts
  its own `FirstModal` / `FolderSelectionModal` / `NotifModal`, which is a different route.
- [x] ~~`main.ts` imported for `i18n`, a circular import.~~ Resolved: no file imports
  `from '@/main'` any more; the instance lives in `locales/i18n.ts`.
- [x] ~~Dev routes shipped to production.~~ Resolved: `router/index.ts` has two routes,
  `/` and `/view`. `SandboxView.vue` and `TestView.vue` were deleted in `3a7388d2`.
- [x] ~~`main.ts` has commented-out `customize.scss` / VueFinder lines.~~ Removed.
- [x] ~~The old shell (`PanopticView`, `Menu`, `mainview/MainView`) is dead.~~ Deleted.
  `mainview/` still holds `TabButton.vue`, `ContentFilter.vue`, `ContentFilterSim.vue`,
  `ImageView.vue`, `TabNav.vue`.

## Files: boot & routing
- [x] `index.html`. Vite HTML entry: `#app`, `/favicon.ico`.
- [x] `src/main.ts` · 31 L. Creates the app. It loads Pinia, `vue-virtual-scroller`, the router, i18n and `vue3-tour`, plus the global CSS (Inter, Bootstrap, bootstrap-icons, `@vueform/toggle`, `vue3-tour`).
- [x] `src/App.vue` · 19 L. The root component, now minimal: `RouterView`, the global CSS
  imports, `panoptic.init()` and `useKeyState()` (the Ctrl/Cmd+Z handling moved into that
  composable, `data/composables/keyState.ts`). No modals.
- [x] `src/router/index.ts` · 19 L. Hash history, two routes: `/` HomeView and `/view`
  ProjectView. `panopticStore.ts` and `views/ProjectView.vue` also import it.
- [x] `src/views/ProjectView.vue` · 160 L. The project page (route `/view`), renamed from
  `MainView.vue` in `3a7388d2`. It builds `AppShellLayout` with `TopBarPanel` (toolbar),
  `LeftBarPanel` (activity bar), `SidebarLayout` / `SplitLayout` holding `FolderPanel`,
  `PropertyPanel`, `FilterIsland` and `ViewPanel`, plus `TabProvider` — and it mounts the
  twelve global modals.
- [x] `src/views/HomeView.vue` · 332 L. The project picker (route `/`).

## Files: layout primitives
- [x] `src/layouts/AppShellLayout.vue` · 80 L. The pure shell frame (PyCharm "island" style): a `#toolbar` and an `#activity` slot plus the content.
- [x] `src/layouts/SidebarLayout.vue` · 150 L. Sidebar plus main content, with a resize gutter.
- [x] `src/layouts/SplitLayout.vue` · 289 L. Two-pane split where the primary pane grows and the secondary keeps its size. Also used by `GroupView.vue`.
- [x] `src/layouts/IslandPanel.vue` · 74 L. A rounded, bordered, shadowed "island" card. Used by the filter, folder, property and reco panels and 2 others.

## Files: top bar, activity bar & tabs
- [x] `src/components/layoutpanels/TopBarPanel.vue` · 268 L. The top toolbar:
  - left: project title and actions
  - right: user, notifications, language
  - also hosts `TabPanel`, `HistoryDropdown`, `TaskProgressBar`, `ColumnStatusDropdown` and `SelectionStamp`

  Last changed 2026-09-11.
- [x] `src/components/layoutpanels/LeftBarPanel.vue` · 121 L. Left activity bar that toggles the Folder and Properties tool windows (`uiStore`).
- [x] `src/components/layoutpanels/TabPanel.vue` · 238 L. Tab bar island: the open tabs (`TabButton`), a tab-picker dropdown, and the add-tab button.
- [x] `src/components/layoutpanels/TabProvider.vue` · 30 L. Provides the current tab to its descendants ("Pillar D", see `data/composables/useCurrentTab.ts`).
- [x] `src/components/mainview/TabButton.vue` · 172 L. One tab: rename, close, and scrolling itself into view when it becomes active.
- [x] `src/components/TabContainer.vue` · 31 L. Small tab wrapper (it uses `TabManager` and `tabStore`). Used by `PropertyPanel.vue`.
- [x] `src/components/dropdowns/HistoryDropdown.vue` · 285 L. Undo history in two modes: `own` (the store's own commit stacks, which Ctrl+Z acts on) and `all` (every commit, fetched from the backend). Heavily changed on 2026-09-11.
- [x] `src/components/dropdowns/TaskProgressBar.vue` · 291 L. Backend task progress. It maps raw task class names and English step names to translated labels.
- [x] `src/components/dropdowns/ColumnStatusDropdown.vue` · 437 L. Load status per property column (loading / empty / loaded counts). The panel is `position:fixed` so it escapes the toolbar's `overflow:hidden`.
