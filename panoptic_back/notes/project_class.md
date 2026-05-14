# `Project` class — in-depth analysis

**File:** `panoptic/core/project/project.py`

---

## Purpose

`Project` is the top-level facade for a single Panoptic workspace. It owns every subsystem needed to run one project: the database connection, the task queue, the plugin registry, the importer/exporter, the event bus, and the file-system layout. External callers (API layer, tests) interact almost exclusively through this class.

---

## Composition — subsystems

| Attribute | Type | Responsibility |
|---|---|---|
| `paths` | `ProjectPaths` | Knows all on-disk paths (`image_data/`, `small/`, `atlas/`, …). `create_paths()` is the only place directories are created. |
| `db` | `ProjectDb` | Async façade over the SQLite database. All reads and writes go here. |
| `ui` | `ProjectUi` | Holds a pending-commit buffer and a broadcast callback for WebSocket clients. |
| `on` | `ProjectEvents` | Typed event bus. Exposes three channels: `import_instance`, `delete_folder`, `sync` (used to push real-time updates to connected UIs). |
| `action` | `ProjectActions` | Registry of plugin-registered callable actions (name → `Action`). Used by the API to dispatch UI-triggered commands. |
| `task_manager` | `TaskManager` | Schedules and runs async `Task` objects, emits progress updates, and cleans up finished tasks. |
| `plugin_watcher` | `PluginWatcher` | Optional file-watcher (activated via `PANOPTIC_WATCH_PLUGINS=1`) that reloads plugin source on disk changes. |
| `importer` | `Importer` | Handles CSV parsing, column mapping, and committing imported data to the DB. |
| `exporter` | `Exporter` | Exports instance/property data to CSV. |
| `executor` | `ThreadPoolExecutor` | 8-thread pool for CPU-bound or blocking work; accessible via `run_async()`. Registered with `atexit` so it shuts down cleanly. |
| `sha1_to_files` | `dict[str, list[str]]` | In-memory index mapping sha1 → list of local file paths. Populated at load time and kept in sync with imports. Used to avoid duplicate imports. |
| `settings` | `ProjectSettings` | Live copy of user-facing settings (image sizes, save flags). |

---

## Lifecycle

### `__init__`
Pure initialization — no I/O. All subsystems are constructed but not started. `db` and `ui` are set to `None` until `start()` completes.

### `start()` — async
The main boot sequence. Steps in order:

1. **Create directories** — `paths.create_paths()` ensures `image_data/`, `small/`, `medium/`, `large/`, `atlas/` exist.
2. **Open DB** — Creates a `DbConnection`, awaits its `start()`, then builds `ProjectDb` on top of it.
3. **Build UI layer** — `ProjectUi` is constructed, and `on_import_instance` is wired to the project-level event bus.
4. **Background load** — Kicks off `_parallel_load()` as a detached `asyncio.Task` (stored in `_load_task`) so the `start()` call can return quickly without blocking the API response.
5. **Load plugins** — If plugin keys were passed in, a `LoadPluginTask` is enqueued on the task manager.
6. **Atlas check** — Queries the DB for atlas `0`; if absent, enqueues a `GenerateAtlasTask`.

The detached `_load_task` does two things in parallel:
- `_load_settings()` — reads `ProjectSettings` from the DB into `self.settings`.
- `_load_sha1_to_files()` — streams all (sha1, url) pairs from the DB into the `sha1_to_files` index.

### `wait_full_start()` — async
Awaits the `_load_task` so callers can block until the background load is complete. Used in tests and possibly at server startup.

### `close()` — async
Tears down in reverse order: marks `is_loaded = False`, closes the DB connection, shuts down the task manager, and stops the plugin watcher. All steps are wrapped in a bare `except Exception: pass`, meaning close errors are silently swallowed.

---

## Core operations

### Import
`import_folder(folder)` creates an `ImportFolderTask` and hands it to the task manager. It returns immediately; progress is pushed to the UI via the task manager's `on_update` event.

### Export
`export_data(...)` delegates to `Exporter.export_data()` and then calls `show_in_file_manager()` to open the result directory in the OS file browser.

### Delete folder
`delete_folder(folder_id)` awaits `db.delete_folder()`, then emits the result on `on.delete_folder` for any listeners (e.g., WebSocket broadcast).

### Settings update
`update_settings(settings)` diffs the new settings against the current ones to decide which cached images to delete and whether a re-import pass is needed. It then persists the new settings and, if required, enqueues an `ImportImageTask` to regenerate image derivatives.

### Vector type deletion
`delete_vector_type(id_)` removes the type from the DB and notifies every loaded plugin so they can unload any data keyed to that type.

---

## Plugin system

Plugins are passed in as `List[PluginKey]` at construction time. They are loaded asynchronously via `LoadPluginTask`. Once loaded, a plugin can:

- Register **actions** via `ProjectActions.easy_add()` — each action gets a `FunctionDescription` built by inspecting the function signature and its docstring (`@param_name:` annotations become UI labels).
- Be hot-reloaded by `PluginWatcher` when `PANOPTIC_WATCH_PLUGINS=1` is set. The watcher clears Python's module cache and re-enqueues a `LoadPluginTask`.

Loaded plugin instances are stored in `self.plugins: List[APlugin]`. `delete_vector_type` iterates over all plugins to call `load_vector_types()`, showing that plugins are notified of certain DB-level events.

---

## Event system

`ProjectEvents` holds three `EventListener` channels:

- `import_instance` — fires when a new `Instance` is imported; wired to `on.sync` for WebSocket broadcast.
- `delete_folder` — fires after a folder is deleted.
- `sync` (a `SyncEvent`) — higher-level broadcast channel. Exposes typed `emit*` methods for project state, commits, folders, settings, vector types, tasks, maps, and atlas updates. Each call serializes the payload into a `SyncData(key, project_id, data)` envelope and sends it to all registered WebSocket handlers.

Task progress is also routed through `on.sync.emitTasks()` via the `_emit_tasks` callback registered on `task_manager.on_update`.

---

## Notable patterns and quirks

- **Two-phase start.** `start()` returns before the DB indexes are fully loaded. Callers that need a fully warm project must call `wait_full_start()`. This is easy to miss.
- **Silent close errors.** The bare `except Exception: pass` in `close()` means any DB or task teardown failure is invisible. This could hide resource leaks.
- **Module-level executor.** The `ThreadPoolExecutor` is created per-`Project` instance but registered globally with `atexit`. If multiple projects are opened and closed, old executors remain registered until process exit.
- **`sha1_to_files` is in-memory only.** It is populated at start and updated during imports, but there is no explicit invalidation path if files are deleted outside Panoptic. It could drift from the DB.
- **Atlas generation is fire-and-forget.** The `GenerateAtlasTask` is enqueued unconditionally on every `start()` if atlas `0` is missing, with no lock to prevent concurrent generation if `start()` is called twice.
- **`PluginWatcher` hot-reload is broken.** `_reload_plugin` references `self._project.task_queue` which no longer exists (replaced by `task_manager`). Hot-reload would crash if triggered.
