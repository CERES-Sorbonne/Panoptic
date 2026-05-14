# `Panoptic2` class — architecture notes

---

## Comparison: current vs proposed

### What the current `panoptic.py` does

- Manages registered projects, plugins (persisted in old async `PanopticDb`)
- Loads/closes `Project` instances (old async `Project` class)
- Installs/updates/removes plugins via `pip`/`git` subprocesses
- Has partial user management code that is never called
- Exposes `get_state()` for the API

### What the proposed design adds

- **User management** exposed at the `Panoptic` level (create, update name, delete, lookup by name)
- **Connected users + session tokens** — runtime in-memory state (not persisted)
- **`set_excluded_plugins` per project** — currently called `ignored_plugins`, inconsistent with the new DB model which uses `excluded_plugins`

### What is in the current code but missing from the proposal

- **`get_state()`** — needed by the API to report the full Panoptic state to clients. Should stay.
- **`check_for_official_plugin()`** — auto-registers `panopticml` if it's pip-installed but not yet in the DB. Useful but should be kept separate from core responsibilities, or made explicit.
- **`update_project`** — rename / update project metadata. Covered by proposal implicitly but should be listed explicitly.

---

## Errors and problems in the current code

1. **`open_projects` vs `loaded_projects`**: `__init__` sets `self.loaded_projects = {}` but every other method references `self.open_projects` — a `NameError` at runtime on any project load/close/remove call.

2. **`set_ignored_plugin` calls `self.save_data()`** which does not exist. Dead code.

3. **`start()` wraps async in `asyncio.run()`** but several methods (`create_project`, `load_project`, etc.) are still `async def`. Mixed sync/async interface — the new design should be fully sync.

4. **`load_project` uses the old async `Project` class** — incompatible with the new sync `Project2` architecture.

5. **`PanopticConfig` in the new DB model** has `uuid`, `name`, `description` all required with no defaults — same bug as `ProjectConfig` (will return `None` values). Needs `Optional[str] = None` and the same fix applied to `ProjectDB`.

6. **`ProjectKey` uses `uid` as PK** (string UUID) but the old code uses integer `project_id` everywhere — the new `Panoptic` class needs to decide on one identifier type and use it consistently.

7. **`get_user_id from username`**: `User` has `uuid` as PK. There is no unique constraint on `name`. Two users could have the same name, making lookup ambiguous. Either enforce uniqueness on `name` in the schema, or make clear that lookup returns a list.

8. **Connection tokens are not modeled anywhere** in the current code. They need to be added as runtime-only in-memory state.

9. **Missing `login()` function**: the proposal mentions connection tokens but not the function that generates them. A `login(username, password) → token` function is needed.

---

## Proposed architecture

### Responsibilities

```
Panoptic2
 ├─ Persisted state (via PanopticDB — sync SQLiteWriter)
 │   ├─ registered projects  (ProjectKey: uid, path, excluded_plugins)
 │   ├─ registered plugins   (PluginKey: id, install_path, source_type, source_path)
 │   └─ registered users     (User: uuid, name, description, password_hash)
 │
 ├─ Runtime state (in-memory only)
 │   ├─ loaded_projects: dict[str, Project2]   # uid → Project2
 │   └─ sessions:         dict[str, str]        # token → user_uuid
 │                        (watchers live in PanopticServer2, not here)
 │
 └─ Methods
     ├─ Lifecycle  (sync)
     │   ├─ start()          — opens PanopticDB, seeds state
     │   └─ run()            — starts the asyncio event loop (Socket.IO + watchers)
     │                         blocks until shutdown signal
     │
     ├─ Project management  (sync)
     │   ├─ create_project(name, path) → ProjectKey
     │   ├─ import_project(path) → ProjectKey
     │   ├─ load_project(uid) → Project2       — also starts a DbWatcher
     │   ├─ close_project(uid)                 — also stops the DbWatcher
     │   ├─ delete_project(uid, delete_files)
     │   ├─ update_project(uid, name) → ProjectKey
     │   └─ set_excluded_plugins(uid, plugins: list[str])
     │
     ├─ User management  (sync)
     │   ├─ create_user(name, description, password) → User
     │   ├─ update_user_name(uuid, new_name)
     │   ├─ delete_user(uuid)
     │   └─ get_user_by_name(name) → User | None
     │
     ├─ Session management  (sync, runtime only)
     │   ├─ login(username, password) → token
     │   ├─ logout(token)
     │   └─ get_user_from_token(token) → User | None
     │
     ├─ Plugin management  (sync, delegates to PluginInstaller)
     │   ├─ add_plugin(name, source, type) → PluginKey
     │   ├─ reinstall_plugin(name)
     │   └─ delete_plugin(name)
     │
     └─ State  (sync)
         └─ get_state() → PanopticState
```

### Lifecycle

**`start()` — sync.** Opens `PanopticDB`, reads registered projects/plugins/users into memory. No event loop needed. Can be used from scripts with no server at all.

**No `run()` on `Panoptic2`.** The event loop is owned by uvicorn, not by `Panoptic2`. The start script creates `PanopticServer2` and hands it `Panoptic2`; `PanopticServer2` handles all async wiring.

`Panoptic2` has zero asyncio imports. This allows it to be used from batch scripts or tests without starting a Socket.IO server.

```python
# In a batch script — no event loop needed
panoptic = Panoptic2(db_path)
panoptic.start()
project = panoptic.load_project(uid)
instances = project.get_instances()
```

```python
# In the server start script
panoptic = Panoptic2(db_path)
panoptic.start()
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
server = PanopticServer2(panoptic, sio)   # owns all async wiring
app = FastAPI(lifespan=lifespan)
uvicorn.run(socketio.ASGIApp(sio, app))
```

### DbWatcher ownership

`PanopticServer2` owns one `DbWatcher` per loaded project. When `PanopticServer2.load_project(uid)` is called, it calls `panoptic.load_project(uid)` (sync), then creates the `DbWatcher` and schedules it with `asyncio.ensure_future`. When `close_project` is called, it calls `watcher.stop()` (flag-based, sync-safe). See `ui_broadcast_watcher.md` for the full wiring detail.

---

### PluginInstaller

All subprocess work (pip/git) is extracted into a separate class so `Panoptic2` only deals with registry state. `Panoptic2` calls `PluginInstaller` to do the filesystem work, then writes the resulting `PluginKey` to `PanopticDB`.

```
PluginInstaller
 ├─ install_from_pip(source) → (install_path)
 ├─ install_from_git(url, name) → (install_path)
 ├─ install_from_path(path) → (install_path)       # installs requirements.txt
 ├─ reinstall(plugin_key: PluginKey)
 └─ uninstall_files(plugin_key: PluginKey)          # removes cloned git dirs / plugin data
```

`Panoptic2.add_plugin` flow:
1. `PluginInstaller.install_*(...)` — runs pip/git, returns install path
2. Build `PluginKey` with the result
3. `PanopticDB.add_plugin(...)` — persists the registration

`Panoptic2.delete_plugin` flow:
1. `PanopticDB.delete_plugin(...)` — removes registration first
2. `PluginInstaller.uninstall_files(...)` — cleans up filesystem

Deleting the DB record first means a crash during filesystem cleanup leaves an orphaned directory but not a broken DB reference — the safer failure mode.

### Session tokens

Tokens are UUIDs generated at login, stored in `self.sessions: dict[str, str]` (token → user_uuid). They are never written to disk — a server restart invalidates all sessions. This is intentional for a local-first app.

```python
def login(self, username: str, password: str) -> str:
    user = self.get_user_by_name(username)
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")
    token = str(uuid.uuid4())
    self.sessions[token] = user.uuid
    return token

def logout(self, token: str):
    self.sessions.pop(token, None)

def get_user_from_token(self, token: str) -> User | None:
    user_uuid = self.sessions.get(token)
    if not user_uuid:
        return None
    return next((u for u in self.db.get_users() if u.uuid == user_uuid), None)
```

### Project names

Project names are stored in `ProjectKey.name` in `PanopticDB` — decoupled from the filesystem folder name. On first import the name defaults to `Path(path).name`, but can be changed freely via `update_project(uid, name)` without any filesystem operation.

`ProjectConfig.name` in `ProjectDB` is informational only (useful for external scripts reading the project DB directly) and is not the authority. `PanopticDB` is the authority.

### Project identity

Use `uid` (string UUID from `ProjectDB.config.uuid`) as the single identifier everywhere. Drop integer project IDs — they were an artifact of the old DB schema. The `ProjectKey.uid` is the canonical key in `PanopticDB` and in `loaded_projects`.

### UUID integrity check on load

When loading a project, `load_project` must verify that the `ProjectKey.uid` stored in `PanopticDB` matches the `ProjectDB.config.uuid` read from the project's own DB file. A mismatch means the project folder was copied, moved, or replaced without re-registering.

```python
def load_project(self, uid: str) -> Project2:
    key = next((p for p in self.db.get_projects() if p.uid == uid), None)
    if not key:
        raise ValueError(f"Project {uid!r} is not registered")

    project_db = ProjectDB(Path(key.path) / 'project.db')
    project_db.start()
    if project_db.config.uuid != key.uid:
        raise ValueError(
            f"UUID mismatch: registered as {key.uid!r} "
            f"but project DB contains {project_db.config.uuid!r}. "
            f"Re-import the project to fix the registration."
        )

    project = Project2(key.path, ...)
    project.start()
    self.loaded_projects[uid] = project
    return project
```

The error message is explicit about the fix — the user should call `import_project` on the new path rather than editing the registry manually.

### Plugin install/reinstall

`pip` and `git` subprocess calls are blocking but acceptable here — they only happen on explicit admin actions, not during request handling. They should remain sync calls in the `Panoptic` class, not async tasks.

---

## What to fix before implementing

1. Fix `PanopticConfig` fields to `Optional[str] = None` (same fix as `ProjectConfig`)
2. Add `UNIQUE` constraint on `User.name` in the schema, or document that names are not unique and `get_user_by_name` returns a list
3. Pick `uid` (string) as the single project identifier and remove all integer `project_id` references
4. Rename `ignored_plugins` → `excluded_plugins` everywhere to match the new DB model
5. `check_for_official_plugin` is replaced by two explicit functions on `Panoptic2`: `is_official_plugin_installed() → bool` (pure check, no side effects, called by the UI on startup to decide whether to show an install prompt) and `install_official_plugin()` (delegates to `PluginInstaller`, only called on explicit user request). Silent auto-registration is removed.
