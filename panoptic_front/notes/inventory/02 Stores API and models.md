---
tags: [inventory, frontend]
zone: stores
---
# 02 · Stores, API clients & models (`src/data`)

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** all application state (Pinia), the two HTTP clients, the Socket.IO client, the shared model types, and the renderless `InstanceData` loader. The docs are in `notes/new_data_store_design.md`, `notes/tabstore_manager_reactivity_refactor.md` and `notes/frontend_backend_communication.md`.

## Layout
`src/data` is split by role. `models/` and `lib/` import nothing from `stores/` or `api/`. `api/` imports only `models/`, except the `usePanopticStore` read in its axios interceptors (see checks). `stores/` may import all three.

## Zone-level checks
- [ ] `models/` is imported through the `models/index.ts` barrel (~170 importers). The barrel is kept on purpose; importers could later target `@/data/models/<module>` directly.
- [ ] `stores/dataStore.ts` (934 L, ~77 importers) is the store hub. Any cycle through it drags in the whole app.
- [ ] `api/panopticApi.ts` and `api/projectApi.ts` read `usePanopticStore()` in their request/response interceptors (connection id, project id, user id, error notifs). This is the one remaining `api/` → `stores/` import.
- [ ] `lib/builders.ts` imports the `create*State` factories from `@/core/*Manager`, which import stores. It has no direct store import.
- [ ] Every function in `api/projectApi.ts` / `api/panopticApi.ts` still matches a backend route (see backend note `01 Entry point server and API`).
- [ ] `stores/socketStore.ts` has a single importer (`stores/panopticStore.ts`). Check that it's initialised once, and that updates buffered during the first stream are flushed.
- [ ] Both API files start with the French header "Fichier servant à regrouper…". Harmonise comment language if it matters.
- [ ] `FunctionDescription.action` is read by `PluginSettings.vue` / `PluginSettings2.vue`, but the backend model has no `action` field.

## Files
### `models/` (types, enums, constants)
- [ ] `src/data/models/index.ts` · 11 L. Re-export barrel, so `@/data/models` keeps working.
- [ ] `src/data/models/instance.ts` · 33 L. `Instance`, `RawInstance`, `InstanceIndex`, `Sha1*`, `deletedID` (single definition, -999999999), `deletedName`.
- [ ] `src/data/models/property.ts` · 144 L. `Property*`, `PropertyType` / `PropertyMode` / `PropertyID`, value shapes, `isReadonly`, `PropertyGroup*`, `PropertyOption`.
- [ ] `src/data/models/tag.ts` · 34 L. `Tag`, `TagIndex`, `DeleteTagResult`, `buildTag`.
- [ ] `src/data/models/folder.ts` · 61 L. `Folder*`, `FileSource*`, `SourceNode`, `FolderNode`, `RootNode`, `DirInfo`.
- [ ] `src/data/models/tab.ts` · 121 L. `TAB_MODEL_VERSION`, `CollectionState` / `CollectionConfig`, `ViewType`, `ViewState`, `TabState` / `TabData` / `TabIndex`, map/reco/cluster/graph options, `ScoreInterval`.
- [ ] `src/data/models/plugin.ts` · 125 L. `ParamDescription`, `FunctionDescription` (one interface), `Plugin*` (incl. `PluginKey`), `Action*`, `GroupResult`, `ActionResult`, `IgnoredPlugins`.
- [ ] `src/data/models/vector.ts` · 110 L. Vector types and stats, `Score*`, `PointMap`, `MapIndex`, `BoundingBox`, `ImageAtlas`, `ZoomParams`, `PointData`, `PointIndex`.
- [ ] `src/data/models/commit.ts` · 79 L. `DbCommit`, `CommitStat`, `DbCommitInfo`, `CommitHistory`, `Update`, `UpdateCounter`, `SyncResult`, `StatusUpdate`.
- [ ] `src/data/models/project.ts` · 171 L. `Project*`, `User*`, `ConnectionState`, `TaskState`, `LoadResult` / `LoadState`, `UiState`, `ImageType` / `ImageStats`, `Legacy*` (0.x migration).
- [ ] `src/data/models/notif.ts` · 56 L. `NotifType`, `Notif`, `NotifFunction`, `ApiRequestDescription`, `Upload*`, `ImportVerify`.
- [ ] `src/data/models/ui.ts` · 76 L. `ModalId`, `UIDataKeys`, `Colors`, `greyColor`, `DateUnit` (+ factor), `SelectOption`, `TextQuery`.

### `stores/` (Pinia)
- [ ] `src/data/stores/dataStore.ts` · 934 L. Project data: properties, tags, folders, file sources, instances index, commit application, own undo/redo stacks. Changed on 2026-09-11.
- [ ] `src/data/stores/columnStore.ts` · 642 L. Columnar property values and the selection sets per namespace (`global` is always present). Column helpers live in `lib/columns.ts`.
- [ ] `src/data/stores/instanceStore.ts` · 361 L. Per-instance entries, value load status, and a placeholder entry for components that render before an instance has streamed in.
- [ ] `src/data/stores/panopticStore.ts` · 352 L. Instance-level state: projects, plugins, users, connection, migration of old (0.x) projects, and the router hand-off.
- [ ] `src/data/stores/projectStore.ts` · 228 L. The open project: settings, tasks, plugin params, UI version.
- [ ] `src/data/stores/tabStore.ts` · 228 L. Tabs and their `TabManager`s, persistence.
- [ ] `src/data/stores/actionStore.ts` · 252 L. Plugin actions: available functions, default action per slot, running actions.
- [ ] `src/data/stores/uiStore.ts` · 182 L. UI layout state: panels, resizes, scroll positions. Guide: `notes/UI_STORE_GUIDE.md`.
- [ ] `src/data/stores/hoverStore.ts` · 161 L. The property currently hovered or edited anywhere, which lights up its row in the property panel.
- [ ] `src/data/stores/inputStore.ts` · 89 L. Registry of editable inputs, used for keyboard navigation between tree cells.
- [ ] `src/data/stores/mediaStore.ts` · 92 L. Vector types, maps and atlas metadata. It relies on the backend always rewriting atlas id 0 in place.
- [ ] `src/data/stores/modalStore.ts` · 59 L. Which modal is open, plus its payload.
- [ ] `src/data/stores/socketStore.ts` · 189 L. Socket.IO client: connection state, `db_update` deltas, buffering during the initial stream.
- [ ] `src/data/stores/textSearchStore.ts` · 14 L. Text-search store, used by `TextSearchInput.vue`.

### `api/` (HTTP clients)
- [ ] `src/data/api/panopticApi.ts` · 169 L. Axios client for instance-level routes: projects, users, filesystem, plugins. Exports `SERVER_PREFIX`.
- [ ] `src/data/api/projectApi.ts` · 584 L. Axios client for `/projects/{id}` routes: state streams, tags, properties, folders, IIIF, history. Changed on 2026-09-11.

### `lib/` (pure helpers)
- [ ] `src/data/lib/builders.ts` · 119 L. Factories for the default collection config, view state, tab state and map/reco/cluster/graph options.
- [ ] `src/data/lib/columns.ts` · 75 L. `ColumnData`, `TagSparse` / `TagCSR`, `propertyKind`, `makeColumn`, `growColumn`, `buildCSR`.
- [ ] `src/data/lib/tree.ts` · 105 L. Builds the folder tree and the tag tree (drops cyclic parent edges), `wouldCreateTagCycle`.

### `composables/`
- [ ] `src/data/composables/keyState.ts` · 100 L. Global modifier-key state (shift, ctrl, alt).
- [ ] `src/data/composables/useCurrentTab.ts` · 16 L. Reactive handle to the active tab's `TabManager` ("Pillar D").

### Moved out of `src/data`
- [ ] `src/components/scrollers/types.ts` · 83 L. Scroller line types (`ScrollerLine`, `GroupLine`, `ImageLine`, `ClusterLine`, …), `GroupViewMode`, `MOSAIC_GRID`, `mosaicSlotCount`.
- [ ] `src/components/dropdowns/registry.ts` · 5 L. `DropdownElem` / `Dropdowns` types.
- [ ] `src/components/data/InstanceData.vue` · 63 L. Renderless component that registers interest in (instanceIds × propIds) so those columns get loaded. Used by the graph, map, image modal and 5 others.
