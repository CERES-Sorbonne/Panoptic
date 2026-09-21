---
tags: [inventory, frontend]
---
# Frontend inventory (`panoptic_front`)

Snapshot of branch `rework-front` @ `72e9faeb`, 2026-09-11.
**Reviewed 2026-09-21 @ `5a6893b9`**: paths, findings and the zone notes for 01, 03, 13 and 99
were brought up to date after the September reorganisations (`9d09512f` deleted the old views,
`3a7388d2` renamed `MainView.vue` → `ProjectView.vue`, `20baa607` split `src/data/` into
`api/` + `models/` + `stores/` + `lib/` + `composables/`). The file *counts* below were not
re-derived — only the total was.
Every file that is **used** is listed in exactly one zone note below, as a checkbox to tick once you've reviewed it by hand. Files that are **not used** are in [[99 Unused files]], each with what it used to do and what replaced it.

## How "used" was decided
- **Import graph from `src/main.ts`.** It follows static `import`, `export … from`, dynamic `import()` (the router's lazy views), CSS `@import` / `url()`, template `src="…"` assets and the `@/` alias. Commented-out imports are ignored.
- **Cross-checked against a real `vite build`.** The lazy chunks it produced were `HomeView`, `MainView`, `SandboxView`, `TestView` and `NotifModal`; today's build emits `HomeView`, `ProjectView` and `NotifModal` (the two dev views are gone).
- **Files outside `src/`** (`public/`, config, scripts) were matched by name against code and config.
- **Limits.** This is static analysis. A used file can still contain dead code paths, and components are only counted as used if something imports them. There is no global component registration apart from the plugins registered in `main.ts`.

## Numbers
| | files |
|---|---|
| tracked files in `src/` | 329 (was 315 on 2026-09-11) |
| used (reachable from `main.ts`) | **258** at the 09-11 snapshot; not recomputed since |
| not used | **57** then, minus the 7 deleted since — see [[99 Unused files]] |
| `public/` | 7 (2 used, 5 unused icons) |

## Zone notes
| # | Zone | Covers |
|---|---|---|
| 1 | [[01 App shell routing and layout]] | `index.html`, `main.ts`, `App.vue`, router, views, layouts, top bar and tabs |
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
1. ✅ ~~**The `FolderTree` folder has a case mismatch.**~~ Fixed: git and disk both hold `src/components/folder_tree/` now. See [[13 Folders and file sources]].
2. ⚠ **`npm run lint` is broken.** ESLint 10.4 no longer reads `.eslintrc.cjs` ("couldn't find an eslint.config.(js|mjs|cjs) file").
3. ✅ ~~**Circular import** via `import { i18n } from '@/main'`.~~ Fixed: nothing imports `@/main`.
4. ✅ ~~**Global modals imported in several places.**~~ Fixed: `App.vue` is down to 19 lines and mounts no modal; `views/ProjectView.vue` owns the global modals, `views/HomeView.vue` its own three.
5. **Dead files still being edited** (as of 09-11):
   - `mainview/ContentFilter.vue`
   - `mainview/MainView.vue` — **deleted since** (`9d09512f`)
   - `mainview/TabNav.vue` (2026-08-08, translations)
   - `assets/main.css` (2026-06-08)

   All four stopped being used with the June layout rework.
6. **Feature lost in the rework:** the collection auto-reload toggle. It only existed in the now-unused `toggles/ToggleReload.vue`.
7. **Duplicate component families**, all of them used: two `PropertyDropdown`, two `TextInput`, two `TagInput`, `Modal` vs `Modal2`, `ActionButton` vs `ActionButton2`. These are consolidation candidates.
8. ✅ ~~The dev routes `/#/test` and `/#/test-points` ship in production.~~ Fixed: both routes and both views were deleted in `3a7388d2`.
9. **Large chunks** (build in `panoptic_back/panoptic/html/assets/`, 2026-09-20): `ProjectView` ≈ 1.65 MB, `index` ≈ 745 KB, `index.css` ≈ 355 KB. Vite warns above 500 KB. The chunk grew, and `three` is now inside it.
10. **10 npm packages are never imported**, and runtime libraries (`pinia`, `@vueform/*`, `vue3-json-viewer`) sit in `devDependencies` ([[16 Tooling config and build]]).

## Not inventoried
`notes/` (this vault), `node_modules/`, `dist/`.
The backend has its own inventory in `panoptic_back/notes/inventory/`. It includes `panoptic_back/panoptic/html/`, which is where this app's build is written.
