# Frontend ↔ Backend Communication

## Overview

Two independent channels run in parallel:
- **REST (Axios)** — request/response for mutations and initial data loads
- **Socket.IO (WebSocket)** — server-pushed events for live state updates

---

## REST Layer

### Two axios instances

**`panopticApi`** (`apiPanopticRoutes.ts`) — panoptic-level operations, no project context needed.
- `baseURL` = `VITE_API_ROUTE`
- Interceptor: injects `?connection_id=…` from `clientState.connectionId`

**`projectApi`** (`apiProjectRoutes.ts`) — project-level operations.
- `baseURL` = `VITE_API_ROUTE`
- Interceptor: prepends `/projects/{connectedProject}` to every URL, plus injects `connection_id`
- If no project is connected, logs an error and the call goes out malformed (no guard throws)

Both interceptors share an error handler that catches any non-2xx response and creates a `Notif` of type `ERROR` which is pushed to `panopticStore.notifs` and shown in the notification modal.

### Key case conversion

The backend speaks snake_case; the frontend speaks camelCase.
`keysToCamel` / `keysToSnake` from `utils/utils` are applied at every API boundary — on responses when reading data, on request bodies when writing. `apiCommit` does a manual deep-copy + per-array conversion because the nested arrays need item-level conversion too.

### Route files

| File | axios instance | Scope |
|------|---------------|-------|
| `apiPanopticRoutes.ts` | `panopticApi` | projects CRUD, plugins, filesystem, packages |
| `apiProjectRoutes.ts` | `projectApi` | DB state, commit, images, import/export, actions, vectors, maps, UI data |

> **Note**: `apiProjectRoutes.ts` also contains `apiGetPlugins`, `apiAddPlugin`, `apiDelPlugin`, `apiUpdatePlugin` that use raw `axios` (no base URL). These look like copy-paste leftovers from before the split — the real plugin calls are in `apiPanopticRoutes.ts`.

---

## Socket.IO Layer (`socketStore.ts`)

### Connection

The socket connects to `VITE_API_ROUTE` on the `/socket.io/` path. The stored `connection_id` from `localStorage` is passed as `auth.connection_id` so the server can reassociate the socket with a known client on page reload.

On connect → `panopticStore.setConnect()`  
On connect_error → `panopticStore.setFailedConnect()`  
On disconnect → `panopticStore.updateClientState(undefined)` (wipes client state)

### Server → client events

| Event | Payload | Handler |
|-------|---------|---------|
| `server_state` | `PanopticServerState` | `panopticStore.updateServerState()` — global list of projects/plugins/users |
| `client_state` | `PanopticClientState` | `panopticStore.updateClientState()` — this tab's connection ID and connected project; also saves `connection_id` to localStorage |
| `project_state` | `ProjectState` | `projectStore.importState()` — project runtime info: tasks, plugins, settings |
| `commit` | `DbCommit[]` | `dataStore.applyMultipleCommits()` — live data patches from other tabs or background plugins |
| `tasks` | `TaskState[]` | `projectStore.importTasks()` — progress of background tasks (import, ML compute) |
| `project_settings` | `ProjectSettings` | `projectStore.importSettings()` |
| `folders` | `Folder[]` | `dataStore.importFolders()` |
| `folders_delete` | — | `location.reload()` — hard reload; folders can't be patched incrementally |
| `vector_types` | `VectorType[]` | `dataStore.importVectorTypes()` |
| `maps` | `PointMap[]` | `dataStore.loadMaps()` |
| `atlas` | — | `dataStore.loadAtlas()` |

### Client → server events

| Emit | Purpose |
|------|---------|
| `connect_user` | Associate this socket with a user account |
| `disconnect_user` | Detach user from socket |

---

## State model

### `PanopticServerState`
Global, shared across all tabs. Sent via `server_state` socket event whenever the server-side registry changes.
```ts
{ version, projects: ProjectRef[], plugins: PluginKey[], users: User[], askUser }
```
`ProjectRef` extends `ProjectId` with `isOpen` and `ignoredPlugins`.

### `PanopticClientState`
Per-connection state. Sent via `client_state` after connect and after load/close.
```ts
{ connectionId, connectedProject?: number, connectedAt, user: UserState }
```
`connectedProject` is the currently loaded project for this socket. When it becomes non-null the router pushes to `/view`; when null it pushes to `/`.

### `ProjectState`
Runtime project data. Received via `project_state` socket event.
```ts
{ id, name, path, tasks: TaskState[], plugins: PluginDescription[], settings: ProjectSettings }
```

### `DbCommit`
The single data-transfer object for all CRUD. Used both in REST responses and pushed via socket.
```ts
{
  // deletions (pass IDs)
  emptyInstances?, emptyProperties?, emptyTags?, emptyInstanceValues?, emptyImageValues?
  // upserts
  instances?, properties?, propertyGroups?, tags?, instanceValues?, imageValues?
  // metadata
  undo?, history?
}
```
Every mutation returns a `DbCommit` containing only what changed; `dataStore.applyCommit()` merges it into the local state.

---

## Initialization flow

```
Browser tab opens
  └─ socketStore.init()
       └─ socket connects
            ├─ server_state  → panopticStore.serverState
            └─ client_state  → panopticStore.clientState
                  ├─ connectedProject == null  → router → '/'  (home/project picker)
                  └─ connectedProject != null  → router → '/view'
                         └─ projectStore.init()
                               ├─ apiGetProjectState()   → projectStore.state
                               ├─ loadUiState()          → apiGetUIData('uiState')
                               ├─ dataStore.init()
                               │    └─ apiStreamLoadState(callback)
                               │         reads /db_state_stream (newline-delimited JSON)
                               │         calls callback per chunk → dataStore merges each DbCommit
                               └─ actionStore.init()
                                    └─ apiGetActions()
```

### The streaming load (`apiStreamLoadState`)

Uses native `fetch` with a `ReadableStream` reader (not axios). Reads the response body incrementally, splits on newlines, parses each line as JSON, converts keys to camelCase, and calls the callback. This keeps the UI responsive during large project loads.

---

## Data mutation pattern

All writes go through REST POST `/commit` (or `/undo`, `/redo`). The request is a `DbCommit` with only the changed entities; the response is a `DbCommit` with the server-confirmed state. The store then applies the response via `dataStore.applyCommit()`. Concurrently, the server pushes the same changes to all other connected tabs via `socket.emit('commit', ...)`.

---

## connection_id

Every REST request and every socket connection carries the same `connection_id` (UUID stored in `localStorage`). The server uses this to:
- Know which socket to push events back to after a REST mutation
- Avoid echoing socket events back to the tab that triggered them

On first connect the server assigns an ID and sends it in `client_state`; subsequent connects reuse the stored ID so the server can restore session context after a reload.

---

## Known issues / rough edges

- Plugin calls in `apiProjectRoutes.ts` (`apiGetPlugins`, `apiAddPlugin`, etc.) use raw `axios` with no base URL — they will 404. The real plugin API is in `apiPanopticRoutes.ts` and is what `panopticStore` actually calls.
- `panopticStore.loadProject` / `closeProject` call the API but ignore the returned state; the actual state update comes via the `server_state` and `client_state` socket events that the server emits after the operation.
- `apiGetPanopticState` still calls `/panoptic_state` (v1 route) — that route no longer exists in v2. The store currently relies entirely on socket push for `serverState`; this function is not called anywhere in the store itself but is exported.
