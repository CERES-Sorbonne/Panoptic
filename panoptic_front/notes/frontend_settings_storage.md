# Frontend Settings & Local Data Storage

Analysis of all user data stored in the frontend **outside** of data_db models (images, tags, properties, etc.).

---

## 1. Server-Persisted Settings (via `/ui_data/{key}` API)

All non-model persistence routes through `apiSetUIData(key, value)` / `apiGetUIData(key)` in `src/data/apiProjectRoutes.ts:297-305`. No auto-persistence plugin is used — every save is explicit.

### Project Settings (`/settings` endpoint)
**Store:** `projectStore.state.settings`  
**Model:** `ProjectSettings` in `src/data/models.ts:586-596`  
**Save fn:** `projectStore.updateSettings()`

- `imageSmallSize / imageMediumSize / imageLargeSize` — thumbnail cache sizes in pixels  
- `saveImageSmall / saveImageMedium / saveImageLarge / saveFileRaw` — cache policy flags

---

### UI State (`ui_data/uiState`)
**Store:** `projectStore.uiState`  
**Model:** `UiState` in `src/data/models.ts:598-603`  
**Save fns:** `projectStore.setLang()`, `projectStore.saveUiState()`, `projectStore.updateScoreInterval()`  
**Load fn:** `projectStore.loadUiState()` (`src/data/projectStore.ts:121-132`)

- `activeTab` — ID of the currently active tab  
- `lang` — user's language preference (`'en'`, `'fr'`, etc.)  
- `similarityIntervals: { [funcId: string]: ScoreInterval }` — per-function min/max score thresholds for similarity view  
- `similarityImageSize` — default image size in similarity view (default 70px)

---

### Tab State (`ui_data/tabs`)
**Store:** `tabStore` + `TabManager`  
**Model version:** `TAB_MODEL_VERSION = 7` (`src/data/tabStore.ts:16`)  
**Save fn:** `tabStore.saveTabsToStorage()` ← `TabManager.saveState()`  
**Load fn:** `tabStore.loadTabsFromStorage()` (`src/data/tabStore.ts:58-81`)

Each tab (`TabState`) holds:

**Metadata**
- `id, name, display` — tab identity and active view mode (`'tree'`, `'grid'`, `'map'`, …)
- `isSelection` — whether this is a selection tab

**Filter state** (`FilterState`)
- `folders: number[]` — folder IDs to filter by
- `filter: FilterGroup` — hierarchical filter tree (`propertyId`, `operator`, `value`)
- `query: TextQuery` — text search query

**Sort state** (`SortState`)
- `sortBy: number[]` — ordered property IDs
- `options: { [propId]: SortOption }` — Ascending / Descending per property

**Group state** (`GroupState`)
- `groupBy: number[]` — ordered property IDs
- `options: { [groupId]: GroupOption }` — grouping options per property
- `sha1Mode` — deduplicate by image hash

**Display config**
- `imageSize` — grid thumbnail size (default 100px)
- `visibleProperties: { [propId]: boolean }` — column visibility
- `visibleFolders / selectedFolders: { [folderId]: boolean }` — tree expand/select state
- `propertyOptions: { [propId]: PropertyOption }` — per-property display options (column width, default 200px)
- `mapOptions: MapOptions` — `showPoints`, `selectedMap`, `groupOption`, `imageSize` (default 50px)

**Save trigger chain:**  
User changes filter/sort/group → manager emits `onStateChange` → `TabManager.saveManagerStates()` → `TabManager.saveState()` → `tabStore.saveTabsToStorage()` → `apiSetUIData('tabs', tabs)`

---

### Property Order (`ui_data/propertyOrder`)
**Store:** `dataStore.propertyOrder`  
**Save fn:** `dataStore.savePropertyOrderToStorage()` (`src/data/dataStore.ts:781-783`)  
**Trigger:** `dataStore.triggerPropertyTreeChange()` (`src/data/dataStore.ts:844-868`)

- `groups: { [groupId]: number }` — display order index per group
- `properties: { [propId]: number }` — display order index per property

---

### Action/Function Param Defaults (`ui_data/param_defaults`)
**Store:** `actionStore`  
**Save fn:** `actionStore.updateDefaultParams()` (`src/data/actionStore.ts:90-98`)  
**Load fn:** `actionStore.getDefaultParams()` (`src/data/actionStore.ts:100-111`)

- `{ [actionId.paramName]: any }` — default values for each plugin action's parameters

---

### Default Actions (`ui_data/default_actions`)
**Store:** `actionStore.defaultActions`  
**Save fn:** `actionStore.updateDefaultActions()` (`src/data/actionStore.ts:113-116`)  
**Load fn:** `actionStore.getDefaultActions()` (`src/data/actionStore.ts:118-129`)

- `similar, group, execute, import, export, vector_type, vector, map` — selected function ID for each role

---

## 2. Browser localStorage (Client-Only)

| Key | Value | Set in |
|-----|-------|--------|
| `tutorialFinished` | `'true'` / `'false'` | `src/tutorials/Tutorial.vue:214-253` |
| `currentStep` | step number | `src/tutorials/Tutorial.vue` |
| `default_project_path` | last used directory | `src/components/home/Create.vue:19,28` |
| `panoptic_connection_id` | socket.io session ID | `src/data/socketStore.ts:19-26` |

Tutorial state is checked at project init (`src/data/projectStore.ts:53`).  
Connection ID ensures socket reconnection across page reloads.

---

## 3. In-Memory Only (Pinia, not persisted)

| Store | Contents |
|-------|----------|
| `modalStore` | Open modals and their layer/data |
| `inputStore` | Keyboard-navigable input registry |
| `textSearchStore` | `isLoading` flag |
| `keyState` | Modifier key and mouse position state |
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

- `src/data/projectStore.ts` — UiState, project settings  
- `src/data/tabStore.ts` — Tab persistence (load/save)  
- `src/data/dataStore.ts` — Property order  
- `src/data/actionStore.ts` — Action defaults and param defaults  
- `src/data/socketStore.ts` — Connection ID  
- `src/data/apiProjectRoutes.ts:297-305` — `apiSetUIData` / `apiGetUIData`  
- `src/core/TabManager.ts` — Tab state orchestration and save triggers  
- `src/data/models.ts:219-239,586-603` — `TabState`, `ProjectSettings`, `UiState` interfaces
