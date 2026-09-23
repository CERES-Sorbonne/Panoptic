# Frontend Settings & Local Data Storage

Analysis of all user data stored in the frontend **outside** of data_db models (images, tags, properties, etc.).

*Re-verified 2026-09-21 against `5a6893b9`. Paths follow the `20baa607` split of `src/data/`
into `api/`, `models/`, `stores/`, `lib/` and `composables/`; line numbers were dropped where
they had drifted.*

---

## 1. Server-Persisted Settings (via `/ui_data/{key}` API)

All non-model persistence routes through `apiSetUIData(key, value)` / `apiGetUIData(key)` in `src/data/api/projectApi.ts` (plus `apiSetUIDataBulk`, `apiGetAllUIData`). No auto-persistence plugin is used — every save is explicit.

### Project Settings (`/settings` endpoint)
**Store:** `projectStore.state.settings`  
**Model:** `ProjectSettings` in `src/data/models/project.ts`  
**Save fn:** `projectStore.updateSettings()`

- `imageSmallSize / imageMediumSize / imageLargeSize` — thumbnail cache sizes in pixels  
- `saveImageSmall / saveImageMedium / saveImageLarge / saveFileRaw` — cache policy flags

---

### UI State (`ui_data/uiState`)
**Store:** `projectStore.uiState`  
**Model:** `UiState` in `src/data/models/project.ts`  
**Save fns:** `projectStore.setLang()`, `projectStore.saveUiState()`, `projectStore.updateScoreInterval()`  
**Load fn:** `projectStore.loadUiState()` (`src/data/stores/projectStore.ts`)

- `activeTab` — ID of the currently active tab  
- `lang` — user's language preference (`'en'`, `'fr'`, etc.)  
- `similarityIntervals: { [funcId: string]: ScoreInterval }` — per-function min/max score thresholds for similarity view  
- `similarityImageSize` — default image size in similarity view (default 70px)

---

### Tab State (`ui_data/tabs`)
**Store:** `tabStore` + `TabManager`  
**Model version:** `TAB_MODEL_VERSION = 11` (`src/data/models/tab.ts`) — a tab whose stored
version differs is dropped and reset by `tabStore`.  
**Save:** a debounced deep `watch` on the active tab (`armAutosave`) → `apiUpdateTabState`.
There is no `saveState()` / `saveManagerStates()` call chain any more: mutating `TabState` *is*
the save trigger.  
**Load fn:** `tabStore.loadTabsFromStorage()` (`src/data/stores/tabStore.ts`); tab *order* is a
separate `ui_data` key written by `saveTabOrder()`.

Each tab (`TabState`) holds:

**Metadata**
- `id, name, version, selected` — tab identity
- `isSelection` — whether this is a selection tab

**Collections** — since M4 the filter/sort/group config is **not** tab-level any more:
`collections: CollectionConfig[]`, each `{ id, collectionState, filterState, sortState,
groupState }`, and each of the two `views` names the one it renders through `collectionId`
(two views may share one). `splitView` / `splitRatio` position them.

**Filter state** (`FilterState`, one per collection)
- `folders: number[]` — folder IDs to filter by
- `filter: FilterGroup` — hierarchical filter tree (`propertyId`, `operator`, `value`)
- `query: TextQuery` — text search query

**Sort state** (`SortState`, one per collection)
- `sortBy: number[]` — ordered property IDs
- `options: { [propId]: SortOption }` — Ascending / Descending per property

**Group state** (`GroupState`, one per collection)
- `groupBy: number[]` — ordered property IDs
- `options: { [groupId]: GroupOption }` — grouping options per property
- `sha1Mode` — deduplicate by image hash

**Display config** — tab-level:
- `visibleProperties: { [propId]: boolean }` — column visibility
- `visibleFolders / selectedFolders: { [folderId]: boolean }` — tree expand/select state
- `propertyOptions: { [propId]: PropertyOption }` — per-property display options (column width, default 200px)

**Display config** — per view (`ViewState`): `type`, `imageSize`, and the optional per-view
option bags `mapOptions`, `graphOptions`, `clusterOptions`, `recoOptions`. They are optional on
purpose, so tabs persisted before a bag existed still load without a `TAB_MODEL_VERSION` bump.

**Save trigger chain:**  
User changes filter/sort/group → the config object on `TabState` is mutated → the tab store's
debounced deep watch fires → `apiUpdateTabState`

---

### Property Order (`ui_data/propertyOrder`)
**Store:** `dataStore.propertyOrder`  
**Save fn:** `dataStore.savePropertyOrderToStorage()` (`src/data/stores/dataStore.ts:781-783`)  
**Trigger:** `dataStore.triggerPropertyTreeChange()` (`src/data/stores/dataStore.ts:844-868`)

- `groups: { [groupId]: number }` — display order index per group
- `properties: { [propId]: number }` — display order index per property

---

### Action/Function Param Defaults (`ui_data/param_defaults`)
**Store:** `actionStore`  
**Save fn:** `actionStore.updateDefaultParams()` (`src/data/stores/actionStore.ts`, writes through `apiSetUIDataBulk`)  
**Load:** `_applyDefaultParams()`, fed by one `apiGetAllUIData()` call at init — there is no
`getDefaultParams()` any more.

- `{ [actionId.paramName]: any }` — default values for each plugin action's parameters

---

### Default Actions (`ui_data/default_actions`)
**Store:** `actionStore.defaultActions`  
**Save fn:** `actionStore.updateDefaultActions()` (`src/data/stores/actionStore.ts`, through `apiSetUIDataBulk`)  
**Load:** `_applyDefaultActions()`, from the same bulk `apiGetAllUIData()` call.

- `similar, group, execute, import, export, vector_type, vector, map` — selected function ID for each role

---

## 2. Browser localStorage (Client-Only)

| Key | Value | Set in |
|-----|-------|--------|
| `tutorialFinished` | `'true'` / `'false'` | `src/tutorials/Tutorial.vue:214-253` |
| `currentStep` | step number | `src/tutorials/Tutorial.vue` |
| `default_project_path` | last used directory | `src/components/home/Create.vue:19,28` |
| `panoptic_connection_id` | socket.io session ID | `src/data/stores/socketStore.ts` |

Tutorial state is checked at project init (`src/data/stores/projectStore.ts`).  
Connection ID ensures socket reconnection across page reloads.

---

## 3. In-Memory Only (Pinia, not persisted)

| Store | Contents |
|-------|----------|
| `modalStore` | Open modals and their layer/data |
| `inputStore` | Keyboard-navigable input registry |
| `textSearchStore` | `isLoading` flag |
| `keyState` | Modifier key and mouse position state (`data/composables/keyState.ts`) |
| `panopticStore` | Project list, connected users, notifications, connection state |

---

## 4. Summary

| Data | Persisted to | Key / Endpoint |
|------|-------------|----------------|
| Image cache settings | Server | `/settings` |
| Language, active tab, similarity intervals, similarity image size | Server | `/ui_data/uiState` |
| All tab state (filters, sorts, groups, display, map) | Server | `/ui_data/tabs` |
| Property display order | Server | `/ui_data/propertyOrder` |
| Plugin/function parameter defaults | Server | `/ui_data/param_defaults` |
| Selected default actions per role | Server | `/ui_data/default_actions` |
| Tutorial progress, last project path, socket session | Browser | `localStorage` |
| Modal, input, keyboard, notification state | None | In-memory only |

**No persistence plugin** (`pinia-plugin-persistedstate`, etc.) is used. All server saves are explicit API calls.

---

## Key Source Files

- `src/data/stores/projectStore.ts` — UiState, project settings  
- `src/data/stores/tabStore.ts` — Tab persistence (load/save)  
- `src/data/stores/dataStore.ts` — Property order  
- `src/data/stores/actionStore.ts` — Action defaults and param defaults  
- `src/data/stores/socketStore.ts` — Connection ID  
- `src/data/api/projectApi.ts:297-305` — `apiSetUIData` / `apiGetUIData`  
- `src/core/TabManager.ts` — Tab state orchestration and save triggers  
- `src/data/models/:219-239,586-603` — `TabState`, `ProjectSettings`, `UiState` interfaces
