---
tags: [inventory, frontend]
---
# Frontend inventory (`panoptic_front`)

Snapshot of branch `rework-front` @ `72e9faeb`, 2026-09-11.
Every file that is **used** is listed in exactly one zone note below, as a checkbox to tick once you've reviewed it by hand. Files that are **not used** are in [[99 Unused files]], each with what it used to do and what replaced it.

## How "used" was decided
- **Import graph from `src/main.js`.** It follows static `import`, `export … from`, dynamic `import()` (the router's lazy views), CSS `@import` / `url()`, template `src="…"` assets and the `@/` alias. Commented-out imports are ignored.
- **Cross-checked against a real `vite build`.** The lazy chunks it produced were `HomeView`, `MainView`, `SandboxView`, `TestView` and `NotifModal`.
- **Files outside `src/`** (`public/`, config, scripts) were matched by name against code and config.
- **Limits.** This is static analysis. A used file can still contain dead code paths, and components are only counted as used if something imports them. There is no global component registration apart from the plugins registered in `main.js`.

## Numbers
| | files |
|---|---|
| tracked files in `src/` | 315 |
| used (reachable from `main.js`) | **258** |
| not used | **57**, all in [[99 Unused files]] |
| `public/` | 7 (2 used, 5 unused icons) |

## Zone notes
| # | Zone | Covers |
|---|---|---|
| 1 | [[01 App shell routing and layout]] | `index.html`, `main.js`, `App.vue`, router, views, layouts, top bar and tabs |
| 2 | [[02 Stores API and models]] | `src/data/**`: Pinia stores, API clients, models, socket |
| 3 | [[03 Collection engine (core managers)]] | `src/core/**`: filter, sort, group, cluster, tab and collection managers |
| 4 | [[04 Main views - grid tree and image scrollers]] | `ViewPanel`, grid, tree and image scrollers, image cells |
| 5 | [[05 Group cluster and recommendation views]] | `GroupView`, cluster scroller, `RecommendView` |
| 6 | [[06 Map view]] | `mapview/*` and the three.js renderer in `mixins/mapview/*` |
| 7 | [[07 Graph view]] | `graphview/*` (ECharts) |
| 8 | [[08 Filter sort group and search]] | filter island and panel, filter tree, group/sort forms, text search |
| 9 | [[09 Properties and tags management]] | property panel and groups, property modal, tag modal and tree, badges |
| 10 | [[10 Value editing inputs]] | typed inputs (cell, row, tree), previews, stamp and bulk edit |
| 11 | [[11 Modals notifications import export]] | modal shells, image modal, import/export, notifications |
| 12 | [[12 Actions plugins and settings]] | action buttons, params, settings modal, plugin forms |
| 13 | [[13 Folders and file sources]] | folder panel and tree, file sources, file explorer |
| 14 | [[14 Home users and onboarding]] | `HomeView`, users, legacy import, tutorial |
| 15 | [[15 Shared UI primitives styling and i18n]] | `Dropdown`, tooltip, small utils, `theme.css`, locales, `utils.ts` |
| 16 | [[16 Tooling config and build]] | `package.json`, Vite, TS, env, lint, `public/`, build output |
| — | [[99 Unused files]] | dead components, scaffold leftovers, stale assets, docs, tooling, npm deps |

## Most important findings (all verified on 2026-09-11)
1. ⚠ **The `FolderTree` folder has a case mismatch.** Git tracks `src/components/foldertree/…` (lowercase), while the disk and the import in `FolderPanel.vue` use `FolderTree/`. On a case-sensitive checkout (Linux, Docker, CI) that import fails and the build breaks. See [[13 Folders and file sources]].
2. ⚠ **`npm run lint` is broken.** ESLint 10.4 no longer reads `.eslintrc.cjs` ("couldn't find an eslint.config.(js|mjs|cjs) file").
3. ⚠ **Circular import.** `FolderOptionDropdown.vue` and `FileSourceOptionDropdown.vue` do `import { i18n } from '@/main'`, which forms a cycle: `main.js` → `App` → … → dropdown → `main.js`. `main.js` itself says to use `@/locales/i18n`.
4. ⚠ **Global modals are imported in several places**: `App.vue`, `views/MainView.vue`, and some in `views/HomeView.vue`. Check they aren't mounted twice ([[01 App shell routing and layout]]).
5. **Dead files still being edited:**
   - `mainview/ContentFilter.vue` (edited today)
   - `mainview/MainView.vue` (2026-07-29)
   - `mainview/TabNav.vue` (2026-08-08, translations)
   - `assets/main.css` (2026-06-08)

   All four stopped being used with the June layout rework.
6. **Feature lost in the rework:** the collection auto-reload toggle. It only existed in the now-unused `toggles/ToggleReload.vue`.
7. **Duplicate component families**, all of them used: two `PropertyDropdown`, two `TextInput`, two `TagInput`, `Modal` vs `Modal2`, `ActionButton` vs `ActionButton2`. These are consolidation candidates.
8. The dev routes `/#/test` (Sandbox) and `/#/test-points` (TestView) ship in production.
9. **Large chunks:** `MainView` ≈ 1.13 MB, `index` ≈ 745 KB, `three` ≈ 525 KB (Vite warns above 500 KB).
10. **10 npm packages are never imported**, and runtime libraries (`pinia`, `@vueform/*`, `vue3-json-viewer`) sit in `devDependencies` ([[16 Tooling config and build]]).

## Not inventoried
`notes/` (this vault), `node_modules/`, `dist/`.
The backend has its own inventory in `panoptic_back/notes/inventory/`. It includes `panoptic_back/panoptic/html/`, which is where this app's build is written.
