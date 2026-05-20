# User Management & Connection Flow

## The default user (backend)

`PanopticDB._init_config()` always seeds a default user on first start:

```python
DEFAULT_USER_ID = "default"
default_user = User(id="default", name="default", description="default user", password_hash=None)
```

This means `GET /users` always returns at least one user. There is no empty-users state in practice.

---

## How the frontend decides to show the app

The gate is `isUserValid` in `panopticStore`:

```ts
const isUserValid = computed(() =>
    isConnected.value && (users.value.length === 0 || !!clientState.value.user)
)
```

`PanopticView.vue` renders nothing until `isUserValid` is true:

```html
<template v-if="!panoptic.isUserValid">
    <UserSelection :users="panoptic.users" @connect-user="u => socketStore.connectUser(u.id)" />
</template>
<template v-else>
    <RouterView />   <!-- HomeView or ProjectView -->
    ...modals...
</template>
```

So the two paths:

| `users.length` | `clientState.user` | `isUserValid` | Result |
|---|---|---|---|
| 0 | anything | `true` | App renders immediately (single-user / local mode) |
| > 0 | defined | `true` | App renders (user was selected) |
| > 0 | undefined | `false` | Blocked on `UserSelection` screen |

---

## v1 user management

- Users were hardcoded in-memory (10 dummy names), not stored in DB.
- `ask_users: bool = False` on the server — with this flag false, `server_state` payload set `askUser: false`, which the frontend used to bypass the selection screen (old logic, now removed).
- `connect_user` socket event: client emits `connect_user(userId)` → server sets `clientState.user` → re-emits `client_state` with the user attached.
- `disconnect_user` socket event: clears the user from `clientState`.
- The `UserSelection` component called `socketStore.connectUser(u.id)` which emitted `connect_user`.

---

## v2 user management — current state and gaps

### What exists
- DB always has the "default" user (seeded on init).
- `GET /users` returns the full user list.
- Socket emits `update_users` trigger → frontend calls `fetchUsers()` → `panoptic.users` is populated.

### What is missing
- **v2 `ClientState` has no `user` field.** `ClientState.to_dict()` only emits `connection_id` and `connected_project`. The `client_state` socket payload never includes a user.
- **No `connect_user` socket event in v2.** The frontend calls `socketStore.connectUser(u.id)` which emits `connect_user` to the server, but v2's `PanopticServer2` has no handler for it.
- **No `disconnect_user` handler either.**

### The resulting deadlock
Because `GET /users` always returns at least the "default" user, `users.length` is always ≥ 1 after `fetchUsers()`. This means `isUserValid` always falls to the second condition — `clientState.user` must be set. Since v2 never sets a user on `ClientState`, `clientState.user` is always `undefined`. The app is permanently stuck on the `UserSelection` screen and clicking a user does nothing because the server has no handler.

---

## What needs to change to support the default user

The intent of the "default" user is local / single-user mode: no explicit selection required. There are two clean options:

**Option A — Auto-assign on connect (backend)**
In `PanopticServer2._register_events`, after a connection is registered, check if only the default user exists and attach it to `ClientState` automatically. Emit `client_state` with `user` set. No user selection screen ever shows.

**Option B — Treat default user as transparent (frontend)**
Change `isUserValid` logic: if the only user is the one with `id === "default"`, treat the connection as already valid without requiring `clientState.user`. The default user is invisible to the UI.

Option A is cleaner because:
- The server is the authority on who is connected.
- If real named users are added later, the auto-assign logic is simply not triggered.
- The frontend `isUserValid` logic stays correct as-is.

---

## `UserSelection` component

Renders a list of users, each showing `Connected` or `Available`. Disabled (grey, no click) if `user.connectedTo` is set — this was the v1 mechanism to prevent two connections sharing the same user. In v2 this field is not present on the User model, so all users always appear as Available.

The component emits `connectUser` (camelCase) but `PanopticView` listens with `@connect-user` (kebab) — Vue normalises these so it works.

---

## Summary of gaps to fix

1. Add `user` field to v2 `ClientState` and `to_dict()`.
2. Add `connect_user` socket event handler to `PanopticServer2`.
3. Either: auto-assign the default user on connect (Option A), or change `isUserValid` to skip selection when only the default user exists (Option B).
