---
tags: [inventory, frontend]
zone: stores
---
# 02 · Stores, API clients & models (`src/data`)

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** all application state (Pinia), the two HTTP clients, the Socket.IO client, the shared model types, and the renderless `InstanceData` loader. The docs are in `notes/new_data_store_design.md`, `notes/tabstore_manager_reactivity_refactor.md` and `notes/frontend_backend_communication.md`.

## Zone-level checks
- [ ] `models.ts` (1128 L, **~170 importers**) and `dataStore.ts` (938 L, ~77 importers) are the hubs. Any cycle through them drags in the whole app. `actionStore.ts` already needs a type-only import to avoid one.
- [ ] Every function in `apiProjectRoutes.ts` / `apiPanopticRoutes.ts` still matches a backend route (see backend note `01 Entry point server and API`).
- [ ] `socketStore.ts` has a single importer (`panopticStore.ts`). Check that it's initialised once, and that updates buffered during the first stream are flushed.
- [ ] `stores/textSearchStore.ts` is the only file in a `stores/` subfolder. Inconsistent with the rest.
- [ ] Both API files start with the French header "Fichier servant à regrouper…". Harmonise comment language if it matters.
- [ ] `data/UI_STORE_GUIDE.md` is documentation sitting in `src/` ([[99 Unused files]]).

## Files
- [ ] `src/data/models.ts` · 1128 L. Shared types and enums: `Instance`, `RawInstance`, `Property`, `PropertyType`, `ModalId`, `Colors`, `LoadState`, and the action and plugin descriptions.
- [ ] `src/data/dataStore.ts` · 938 L. Project data: properties, tags, folders, file sources, instances index, commit application, own undo/redo stacks. Changed on 2026-09-11.
- [ ] `src/data/columnStore.ts` · 716 L. Columnar property values: typed columns, the tag CSR index, and the selection sets per namespace (`global` is always present).
- [ ] `src/data/instanceStore.ts` · 362 L. Per-instance entries, value load status, and a placeholder entry for components that render before an instance has streamed in.
- [ ] `src/data/panopticStore.ts` · 360 L. Instance-level state: projects, plugins, users, connection, migration of old (0.x) projects, and the router hand-off.
- [ ] `src/data/projectStore.ts` · 231 L. The open project: settings, tasks, plugin params, UI version.
- [ ] `src/data/tabStore.ts` · 230 L. Tabs and their `TabManager`s, persistence, `TAB_MODEL_VERSION`.
- [ ] `src/data/actionStore.ts` · 253 L. Plugin actions: available functions, default action per slot, running actions.
- [ ] `src/data/uiStore.ts` · 183 L. UI layout state: panels, resizes, scroll positions.
- [ ] `src/data/hoverStore.ts` · 162 L. The property currently hovered or edited anywhere, which lights up its row in the property panel.
- [ ] `src/data/inputStore.ts` · 90 L. Registry of editable inputs, used for keyboard navigation between tree cells.
- [ ] `src/data/mediaStore.ts` · 93 L. Vector types, maps and atlas metadata. It relies on the backend always rewriting atlas id 0 in place.
- [ ] `src/data/modalStore.ts` · 60 L. Which modal is open, plus its payload.
- [ ] `src/data/socketStore.ts` · 190 L. Socket.IO client: connection state, `db_update` deltas, buffering during the initial stream.
- [ ] `src/data/apiPanopticRoutes.ts` · 170 L. Axios client for instance-level routes: projects, users, filesystem, plugins. Exports `SERVER_PREFIX`.
- [ ] `src/data/apiProjectRoutes.ts` · 584 L. Axios client for `/projects/{id}` routes: state streams, tags, properties, folders, IIIF, history. Changed on 2026-09-11.
- [ ] `src/data/builder.ts` · 121 L. Factories for the default collection config, view state, tab state and map/reco/cluster/graph options.
- [ ] `src/data/storeutils.ts` · 158 L. Builds the folder tree and the tag tree (drops cyclic parent edges), counts tags and images per folder, `wouldCreateTagCycle`.
- [ ] `src/data/keyState.ts` · 16 L. Global modifier-key state (shift, ctrl, alt).
- [ ] `src/data/dropdowns.ts` · 6 L. `DropdownElem` / `Dropdowns` types.
- [ ] `src/data/useCurrentTab.ts` · 17 L. Reactive handle to the active tab's `TabManager` ("Pillar D").
- [ ] `src/data/stores/textSearchStore.ts` · 15 L. Text-search store, used by `TextSearchInput.vue`.
- [ ] `src/components/data/InstanceData.vue` · 63 L. Renderless component that registers interest in (instanceIds × propIds) so those columns get loaded. Used by the graph, map, image modal and 5 others.
