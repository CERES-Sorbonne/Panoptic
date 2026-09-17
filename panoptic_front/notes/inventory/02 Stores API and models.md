---
tags: [inventory, frontend]
zone: stores
---
# 02 · Stores, API clients & models (`src/data`)

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

Checked against branch `rework-front` @ `20baa607` on 2026-09-16, after the `src/data` reorganisation. `vue-tsc --noEmit` passes with 0 errors.

**Scope:** all application state (Pinia), the two HTTP clients, the Socket.IO client, the shared model types, and a few pure helpers. The design docs are `notes/new_data_store_design.md`, `notes/tabstore_manager_reactivity_refactor.md`, `notes/frontend_backend_communication.md` and `notes/UI_STORE_GUIDE.md`.

## Layout
`src/data` has 5 folders and 33 files:
- `models/` holds types only.
- `lib/` holds helpers (only `builders.ts` is not pure).
- `api/` holds the HTTP clients.
- `stores/` holds the Pinia stores.
- `composables/` holds two small composables.

Importer counts below only include files that are actually used. Dead files are left out.

### How the folders depend on each other (runtime imports, checked with esbuild)
- **`models/` is clean.** Bundling it pulls in only its own 12 files. `models/tab.ts` imports `FilterState` / `GroupState` / `SortState` from `@/core/*`, but these are type-only imports, so they are erased at build time.
- **`lib/columns.ts` and `lib/tree.ts` are clean.** They import only `models/`.
- **`lib/builders.ts` is not pure.** It imports `create{Filter,Sort,Group,Collection}State` from `@/core/*`, `reactive` from vue and `t` from `@/locales/i18n`. At runtime that pulls in 53 modules, including every store.
- **`api/` reaches into `stores/`.** Both clients call `usePanopticStore()`:
  - in their interceptors, for the connection id, the project id and error notifications;
  - in `projectApi`'s four NDJSON stream helpers, for the project id.
- **One runtime import cycle of 25 modules** (loop 1 is the tightest):
  - Loop 1: `lib/builders` → `core/FilterManager` → `lib/builders` (via `propertyDefault`).
  - Loop 2: `lib/builders` → `core/*Manager` → `stores/{data,column}Store`, and `stores/tabStore` → `core/TabManager` → `lib/builders`.
  - Loop 3: `utils/utils.ts` → `stores/{data,column,project}Store` → `utils/utils.ts`.

  It works today because every access inside the cycle happens inside a function, never at module top level.

## Zone-level checks
- [ ] ⚠ **`src/data/lib/columns.ts` is not in git.** The root `/.gitignore` line 56 has a Python-template rule `lib/`, and it ignores this file. HEAD's `stores/columnStore.ts` imports `../lib/columns`, so **a fresh clone of `20baa607` does not build**. `builders.ts` and `tree.ts` are only tracked because they were renamed from tracked files. Fix: anchor the rule (`/lib/`, or `panoptic_back/**/lib/`), or add `!panoptic_front/src/data/lib/`, then `git add` the file. No other file under `panoptic_front/src` is ignored.
- [ ] ⚠ **`apiGetVersion` calls `GET /version`, which the backend doesn't have.** `panopticStore.fetchVersion()` is never called or exported, so `HomeView` always shows "Version " followed by an empty string.
- [ ] ⚠ **`apiUploadPropFile` calls `POST /projects/{id}/property/file`, which the backend doesn't have.** Its caller, `projectStore.uploadPropFile`, is exported but nothing uses it. Remove both.
- [ ] **`projectApi.ts` has dead duplicates of the plugin calls:** `apiGetPlugins`, `apiAddPlugin`, `apiDelPlugin` and `apiUpdatePlugin` (lines 261–279). They use bare `axios` with no base URL, so they would hit the Vite origin. `panopticStore` uses the `panopticApi.ts` versions. Delete the `projectApi` copies.
- [ ] **Unused API functions in `projectApi.ts`:**
  - `apiGetDbState`, `apiGetTags`, `apiGetProperties`, `apiImportFolder`, `apiGetVectorInfo`, `apiSetDefaultVector`, `apiGetSettings`, `apiStreamSlimState`, `apiStreamLoadState`.
  - `apiBenchmark`: its route `/benchmark` also doesn't exist in the backend.
- [ ] **Direct `projectApi` calls from outside `api/`:**
  - `FileSourceModal.vue` posts to `/iiif/test` and `/import/iiif` itself. As a result, `dataStore.importIiif` → `apiImportIiif` is dead.
  - `instanceStore.ts` posts to `/instances/values` twice.

  Wrap these in `api/` functions, or accept them as they are.
- [ ] **Every other route matches the backend.** All other `panopticApi` / `projectApi` / stream URLs have a matching route in `panoptic_back/panoptic/routes/{panoptic,project}_routes.py` (see backend note `01 Entry point server and API`). Backend routes the frontend builds as URLs rather than calling through the API clients: `atlas_sheet/…` (`AtlasLayerManager`) and `image/by_size/…` (`CenteredImage`, `GroupLine`, `Similarity`). Backend routes nothing in the frontend uses: `/images/{path}`, `image/{raw,small,medium,large}/…`.
- [ ] **`models/` is imported only through the barrel.** 190 live files import `@/data/models`, and nothing outside `models/` imports `@/data/models/<module>`. Keep it that way, or switch importers to the submodules later.
- [ ] **`stores/dataStore.ts` is the hub.** It has 83 importers and is part of the cycle above.
- [ ] **`composables/keyState.ts` imports `dataStore`** so that Ctrl+Z / Ctrl+Shift+Z can call `undo` / `redo`. Because of this, a leaf composable with 15 importers pulls in the whole store graph. Consider moving the shortcut into a component or into `dataStore`.
- [ ] **`FunctionDescription.action`** is read by `PluginSettings.vue` / `PluginSettings2.vue` to group functions, but the backend's `FunctionDescription` (`action_models.py`) has only `id, name, label, description, params, hooks`. The model comment already says so. Every function ends up in the `undefined` group.
- [ ] **`socketStore` is initialised once.** `App.vue` calls `panoptic.init()` → `socket.init()`, and its only live importer is `panopticStore`. `TabNav.vue` also imports it, but that file is dead.
  - Buffering works. A `db_update` that arrives before `dataStore.isLoaded` sets `pendingUpdate`, and a watcher flushes it once loading finishes. An update that arrives during a sync re-runs in `finally`.
  - Leftovers: `loaded` is an unused ref; `close()` and `on()` have no live caller; there are two separate `'disconnect'` handlers (one logs, one clears the connection state), which could be merged.
- [ ] **French comments.**
  - Both API files start with the header "Fichier servant à regrouper…".
  - French comments also sit in `panopticApi.ts` (legacy block), `socketStore.ts` and `panopticStore.ts`.

  Translate them if the codebase should be English-only.
- [ ] **Store members exposed but never used outside their store.** This list comes from a heuristic scan, so check each name before deleting.
  - `dataStore`: `applyMultipleCommits`, `computePropertyTree`, `deleteEmptyClones`, `fetchTagCounts`, `importFileSources`, `importIiif`, `propertyGroupsList`
  - `columnStore`: `columnFetched`, `ensureColumn`, `isFetched`, `requireTagInverted`, `selectionMask`, `tagInverted`
  - `panopticStore`: `clearNotif`, `failedConnected`, `getLegacyReport`, `isConnected`, `isUserValid`, `migratableLegacyProjects`
  - `projectStore`: `hasGroupFunction`, `isImportingImages`, `setActionFunctions`, `updateSettings`, `uploadPropFile`
  - `uiStore`: `scrollStates`, `setPanelState`, `setResizeState`, `setScrollState`
  - `inputStore`: `requestNextInput`, `requestPrevInput`
  - `instanceStore`: `markError`
  - `mediaStore`: `hasAtlas`
  - `modalStore`: `idIndex`
  - `tabStore`: `activeTab`
  - `textSearchStore`: `setLoading`
- [ ] **`textSearchStore` does nothing.** Its `setLoading` is never called, so `isLoading` stays `false`, and the spinner in `TextSearchInput.vue` never shows. Either wire it up or delete the store. Also, the store id is `'search'` and the hook is `useSearchStore`, neither of which matches the file name.
- [ ] **Typo:** `IngoredPluginPayload` in `models/plugin.ts`.
- [ ] **Dead files still import the removed `@/data/store`:** `properties/Property.vue`, `tagtree/TagTree.vue`, `tagtree/TagNode.vue` and `folder_tree/TagNode.vue`. They would fail to build if anything imported them again. Delete them together with the rest of [[99 Unused files]]. That note still spells the folder `FolderTree/`, but it is now `folder_tree/`.
- [ ] **Off-zone, noticed on the way:** `utils/utils.ts` has `import { Exception } from "sass"` (see [[15 Shared UI primitives styling and i18n]]).

## Files
### `models/` (types, enums, constants; all created 2026-09-16 by splitting the old `models.ts`)
- [ ] `src/data/models/index.ts` · 11 L. Barrel re-exporting the 11 modules below.
- [ ] `src/data/models/instance.ts` · 33 L. `Instance`, `RawInstance`, `InstanceIndex`, `Sha1ToInstances`, `Sha1Scores`, `deletedID` (-999999999), `deletedName`.
- [ ] `src/data/models/property.ts` · 144 L. `Property`, `PropertyAccess`, `isReadonly`, `PropertyDescription`, `PropertyType` / `PropertyMode` / `PropertyID`, value shapes (`*ValuesArray`, `PropertyValueUpdate`), `PropertyOption`, `PropertyGroup*`.
- [ ] `src/data/models/tag.ts` · 34 L. `Tag`, `TagIndex`, `DeleteTagResult`, `buildTag`.
- [ ] `src/data/models/folder.ts` · 61 L. `Folder`, `FolderIndex`, `FileSource*` (including `FileSourceSyncStatus`), `SourceNode`, `FolderNode`, `RootNode`, `DirInfo`.
- [ ] `src/data/models/tab.ts` · 121 L. `TAB_MODEL_VERSION`, `CollectionState` / `CollectionConfig`, `ViewType`, `ViewState`, `TabState` / `TabData` / `TabIndex`, `Map/Reco/Cluster/GraphOptions`, `ScoreInterval`. Has type-only imports from `@/core`.
- [ ] `src/data/models/plugin.ts` · 125 L.
  - Plugin description types: `ParamDescription`, `FunctionDescription` (with the orphan `action`), `PluginBaseParamsDescription`, `PluginDescription`, `PluginDefaultParams`, `PluginType`, `PluginKey`, `PluginAddPayload`.
  - Action types: `ActionFunctions`, `ParamDefaults`, `ActionParam`, `ActionContext`, `ExecuteActionPayload`, `GroupResult`, `ActionResult`.
  - Ignore list: `IgnoredPlugins`, `IngoredPluginPayload`.
- [ ] `src/data/models/vector.ts` · 110 L. `VectorDescription`, `ProjectVectorDescription`, `VectorType`, `VectorStats`, `Score`, `ScoreList`, `GroupScoreList`, `ScoreIndex`, `PointMap`, `MapIndex`, `BoundingBox`, `ImageAtlas`, `ZoomParams`, `PointData`, `PointIndex`.
- [ ] `src/data/models/commit.ts` · 79 L. `DbCommit`, `CommitStat`, `DbCommitInfo`, `CommitHistory`, `Update`, `UpdateCounter`, `SyncResult`, `StatusUpdate`.
- [ ] `src/data/models/project.ts` · 171 L. `ProjectId`, `ProjectRef`, `ProjectSettings`, `ProjectState`, `User`, `UserState`, `ConnectionState`, `TaskState`, `LoadResult` / `LoadState`, `UiState`, `ImageType` / `ImageStats`, `Legacy*` (0.x migration: `Registry`, `Project`, `Scan`, `MigrationRun`).
- [ ] `src/data/models/notif.ts` · 56 L. `NotifType`, `Notif`, `NotifFunction`, `ApiRequestDescription`, `UploadError`, `UploadConfirm`, `ImportVerify`.
- [ ] `src/data/models/ui.ts` · 76 L. `ModalId`, `UIDataKeys`, `Colors`, `greyColor`, `DateUnit` + `DateUnitFactor`, `SelectOption`, `TextQuery`.

### `stores/` (Pinia; the importer count follows the ·)
- [ ] `src/data/stores/dataStore.ts` · 934 L · 83. Project data:
  - properties, property groups, tags, folders and file sources;
  - applying commits and deltas (`applyDelta`, `lastSequence`);
  - loading state (`isLoaded`);
  - the commit history mirror. `undo` / `redo` flip the `active` bit of the user's own commits on the server.
- [ ] `src/data/stores/columnStore.ts` · 642 L · 42. Columnar property values (`slotMap`, typed columns, tag CSR), the loading progress of each column, and the selection masks for each namespace (`global` always exists). The column helpers live in `lib/columns.ts`.
- [ ] `src/data/stores/instanceStore.ts` · 361 L · 20. Per-instance entries, value load status, and a registry of which instances and properties are needed, fed by `InstanceData.vue`. Fetches values from `/instances/values` directly. `emptyInstanceEntry` is a placeholder for components that render before an instance has streamed in.
- [ ] `src/data/stores/panopticStore.ts` · 352 L · 45. Instance-level state:
  - projects, plugins and users;
  - connection state and notifications;
  - the 0.x legacy scan and migration;
  - the router hand-off.

  `init()` starts the socket. It has a dead `fetchVersion`.
- [ ] `src/data/stores/projectStore.ts` · 228 L · 29. The open project: state, settings, tasks, plugin info and params, action functions, UI data.
- [ ] `src/data/stores/tabStore.ts` · 228 L · 17. Tabs and their `TabManager`s (`activeManager`), and saving them through the `/tabs` routes.
- [ ] `src/data/stores/actionStore.ts` · 252 L · 17. Plugin actions: the available functions, the default action for each slot, and running actions.
- [ ] `src/data/stores/uiStore.ts` · 182 L · 8. UI layout state (panels, resizes, scroll positions), saved to the backend through `ui_data`. Guide: `notes/UI_STORE_GUIDE.md`. Logs "Module loaded" at import.
- [ ] `src/data/stores/hoverStore.ts` · 161 L · 4. The property currently hovered or edited anywhere. Entries are keyed by an owner token for each component. Also holds `useHoverSource` and the `hoverPropertyKey` injection key.
- [ ] `src/data/stores/inputStore.ts` · 89 L · 1. Registry of editable inputs, used to move between inputs with Tab.
- [ ] `src/data/stores/mediaStore.ts` · 92 L · 9. Vector types and stats, maps, and atlas metadata. The backend always rewrites atlas id 0 in place, so the store stamps each loaded atlas with a version to tell rebuilds apart.
- [ ] `src/data/stores/modalStore.ts` · 59 L · 10. Which modal is open, plus its payload.
- [ ] `src/data/stores/socketStore.ts` · 189 L · 1. The Socket.IO client:
  - connection id kept in `localStorage`;
  - project, plugin, user, legacy, task, settings, folder, vector, map and atlas events;
  - `db_update` → `processDelta` with buffering.
- [ ] `src/data/stores/textSearchStore.ts` · 14 L · 1. `useSearchStore`, which only holds an `isLoading` flag that nothing sets. Last changed 2026-02-04.

### `api/` (HTTP clients)
- [ ] `src/data/api/panopticApi.ts` · 169 L · 5.
  - Axios client for instance-level routes: filesystem, projects, users, plugins, packages, legacy migration.
  - Exports `SERVER_PREFIX`.
  - Its interceptors add `connection_id` to requests and turn errors into notifications.
  - Also contains `apiGetVersion`, whose route doesn't exist.
- [ ] `src/data/api/projectApi.ts` · 584 L · 20.
  - Axios client for `/projects/{id}` routes: project and DB state, tags, properties, folders and file sources, tabs, import/export, plugins and actions, vectors, UI data, maps, commits and history, image types, settings, atlas, delta.
  - Uses `fetch` for the NDJSON streams (`instances/base`, `instances/column/{id}`, `db_state_*`).
  - Also contains the dead code and orphan routes listed in the checks.

### `lib/` (helpers)
- [ ] `src/data/lib/builders.ts` · 119 L · 6. Not pure: it depends on `@/core`, vue and i18n. Contains:
  - factories for the default collection config, view state, tab state and the map/reco/cluster/graph options;
  - `propertyDefault`, `defaultPropertyOption`, `buildPropertyGroupOrder`, `objValues`.

  `createRecoOptions` is only used inside this file.
- [ ] `src/data/lib/columns.ts` · 75 L · 1. ⚠ Not tracked by git (see checks). `ColumnData`, `TagSparse` / `TagCSR`, `propertyKind`, `makeColumn`, `growColumn`, `buildCSR`.
- [ ] `src/data/lib/tree.ts` · 105 L · 3. `buildFolderNodes` (fills in the folder objects it is given), `buildTagTree` (drops parent edges that would create a cycle, and records them in `ignoredParents`), `wouldCreateTagCycle` (used by `TagModal` and `TagTree`).

### `composables/`
- [ ] `src/data/composables/keyState.ts` · 100 L · 15. Global modifier-key state (shift, ctrl, alt) and `useKeyState`. Also handles the undo/redo shortcut through `dataStore`.
- [ ] `src/data/composables/useCurrentTab.ts` · 16 L · 4. Reactive handle to the active tab's `TabManager` ("Pillar D" in `notes/tabstore_manager_reactivity_refactor.md`).

### Moved out of `src/data` on 2026-09-16 (listed here for tracking)
- [ ] `src/components/scrollers/types.ts` · 83 L. Scroller line types (`ScrollerLine`, `GroupLine`, `ImageLine`, `ClusterLine`, …), `GroupViewMode`, `MOSAIC_GRID`, `mosaicSlotCount`.
- [ ] `src/components/dropdowns/registry.ts` · 5 L. The `DropdownElem` / `Dropdowns` types.
- [ ] `src/components/data/InstanceData.vue` · 62 L. Renderless component that registers interest in (instanceIds × propIds) so those columns get loaded. Used by the graph view, the map view, the image modal and others.
- [ ] `notes/UI_STORE_GUIDE.md` (was `src/data/UI_STORE_GUIDE.md`).
