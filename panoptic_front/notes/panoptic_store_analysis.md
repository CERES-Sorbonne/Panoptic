# panopticStore Analysis

File: `src/data/panopticStore.ts`

## Role

`panopticStore` is the top-level shell store. It owns the global session layer:
- connection/authentication state (who is connected, to which project)
- the registry of all known projects, plugins and users (from the server)
- the modal orchestration system
- the notification system

It does **not** own any project data (instances, properties, tags). That lives in `dataStore` and `projectStore`.

---

## State

| Ref | Type | Purpose |
|-----|------|---------|
| `serverState` | `PanopticServerState` | Global app registry: `{ version, projects, plugins, users, askUser }`. Pushed by socket `server_state` event. |
| `clientState` | `PanopticClientState` | This tab's session: `{ connectionId, connectedProject, connectedAt, user }`. Pushed by socket `client_state`. |
| `failedConnected` | `boolean` | Set true on socket `connect_error`; shown as a full-page banner in `PanopticView.vue`. |
| `notifs` | `Notif[]` | All current notifications. Both axios error interceptors push here. |
| `openModalId` | `ModalId \| null` | **Legacy** — see modal section. |
| `modalData` | `any` | **Legacy** — see modal section. |

## Computed

| Computed | Logic |
|----------|-------|
| `isConnected` | Both `serverState` and `clientState` are defined. |
| `isUserValid` | `isConnected` AND (`askUser` is false OR a user is set on `clientState`). Guards the full app render in `PanopticView`. |
| `isProjectLoaded` | `isConnected` AND `clientState.connectedProject` is not null. |

---

## How state flows in

All state comes from the socket, never from REST responses. The two key handlers called by `socketStore`:

**`updateServerState(state)`** — stores the global registry. Has a `console.log` left in.

**`updateClientState(state)`** — stores the per-tab session. This is the main routing gate:
- `connectedProject != null` → `router.push('/view')`
- `connectedProject == null` → `router.push('/')`
- `undefined` (on socket disconnect) → same `router.push('/')` and clears state

This means navigation is 100% reactive to socket events. The REST calls for `load`/`close`/`create`/`import` trigger the server to push updated `client_state` and `server_state` events, which in turn drive the router and re-render.

---

## Project management methods

All six methods (`loadProject`, `closeProject`, `deleteProject`, `createProject`, `importProject`, `updateProject`) follow the same minimal pattern: call the API, ignore the return value, wait for the socket push to update state.

**Known issues:**

- **`loadProject` and `closeProject` call `project.clear()` before the API call.** If the API request fails, the project store has already been wiped but the client state is unchanged. The UI ends up in a blank project view.
- **`deleteProject` calls `window.confirm()`** inside the store. This is a blocking browser dialog inside business logic — it belongs in the component.
- **`updatePlugin` calls the API but never refreshes the plugin list.** Plugin state is left stale until the next socket `server_state` event or a page reload.
- **`addPlugin` and `delPlugin` manually assign `serverState.value.plugins`** via a separate `apiGetPlugins()` call instead of waiting for socket push. This is inconsistent with how everything else works and creates a race: if the socket `server_state` arrives before `apiGetPlugins` returns, the manual assignment overwrites a fresher value.

---

## Modal system

There are two coexisting modal systems with a `// TODO: remove this` comment marking the old one:

**Old system** (to be removed):
- `openModalId` ref + `modalData` ref stored on the store
- `showModal(id, data)` writes to these directly
- `hideModal(id)` clears them

**New system**:
- `useModalStore()` — separate modal store
- `showModal()` calls both systems simultaneously
- `hideModal()` also calls both

Components that read `panoptic.openModalId` directly are tied to the old system. They should be migrated to `modalStore`.

---

## Notification system

`notifs` is an array of `Notif` objects. `notify(notifOrList)` appends them, assigns an auto-incrementing `id` (from a module-level `idCounter`), sets `receivedAt`, and immediately opens the `NOTIF` modal.

The axios error interceptors in both `apiPanopticRoutes.ts` and `apiProjectRoutes.ts` call `panoptic.notify()` on any non-2xx response, so all backend errors automatically surface as notifications.

Issue: `closeProject()` calls `notifs.value = []` (clears all notifications). If a background task fires a notification just before closing, it gets silently dropped.

---

## `init()` — effectively a no-op

```ts
function init() {
    _init = true
}
```

Sets a flag that is never read anywhere. Called from both `App.vue` and `PanopticView.vue` on `onMounted`. Actual initialization is entirely socket-driven via `socketStore.init()`. This function can be removed.

---

## Circular dependency

`useProjectStore()` is called at the top level of the store factory function (outside any action), not lazily inside a function. `projectStore` also imports `panopticStore`. This works because Pinia stores are singletons and Vue defers resolution, but it creates a fragile initialization order dependency. If either store is instantiated before Pinia is set up (e.g. in a test), it will fail. The safer pattern is to call `useProjectStore()` only inside the functions that need it.

---

## Summary of issues

| Issue | Severity |
|-------|----------|
| `project.clear()` before API call in `load`/`close` — state cleared on API failure | Medium |
| `window.confirm()` in `deleteProject` — blocking dialog in store logic | Low |
| `updatePlugin` does not refresh plugin list | Low |
| `addPlugin`/`delPlugin` use manual fetch instead of socket push — race condition | Low |
| Dual modal system (old `openModalId` + new `modalStore`) | Low |
| `console.log` in `updateServerState` | Trivial |
| `init()` is a no-op | Trivial |
| Top-level `useProjectStore()` call — circular dependency risk | Low |
| `closeProject` wipes all notifications | Low |
