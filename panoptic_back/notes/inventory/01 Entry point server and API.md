---
tags: [inventory, backend]
zone: entry-server-api
---
# 01 · Entry point, server & API

Back to [[00 Backend inventory]] · Unused files: [[99 Unused files]]

**Scope:** how the process starts, the FastAPI + Socket.IO app, every HTTP route, and the wire models the frontend receives.
Paths are relative to `panoptic_back/`.

## Zone-level checks
- [ ] Every route in `routes/panoptic_routes.py` and `routes/project_routes.py` still has a caller in `panoptic_front/src/data/apiPanopticRoutes.ts` / `apiProjectRoutes.ts`, or in a plugin.
- [ ] `main.py` → the global `Exception` handler sends the full Python traceback to the client. That's fine locally, but decide whether it should also happen when `PANOPTIC_REMOTE` is set.
- [ ] CORS is `allow_origins=['*']`. Is that intended for remote mode too?
- [ ] `main.py` patches `fastapi.encoders` so that `msgspec.Struct` serialises. Re-check this after every FastAPI upgrade.
- [ ] ⚠ `panoptic/__init__.py` is empty, but it is the hatch version source. See [[10 Build packaging and distribution]].
- [ ] ⚠ `cli.py` imports `click` and `main.py` imports `msgspec`, but neither package is declared in `pyproject.toml`.
- [ ] Env vars read here (`PANOPTIC_DB`, `PANOPTIC_PORT`=8001, `PANOPTIC_HOST`, `PANOPTIC_REMOTE`, `PANOPTIC_ENV=DEV`, `PANOPTIC_WATCH_PLUGINS`) are documented somewhere.

## Files
- [ ] `panoptic/__init__.py` · 0 L. Package marker. ⚠ It used to hold `__version__ = "0.7.4"`, which was removed in `834bf69e` (2026-06-04).
- [ ] `panoptic/cli.py` · 16 L. The `panoptic` console script (`[project.scripts]`): a click group that runs `main.start()` when called without a subcommand.
- [ ] `panoptic/main.py` · 115 L. `start()` does the startup: it opens `Panoptic`, creates the Socket.IO server and `PanopticServer`, and builds the FastAPI app with its lifespan, CORS, gzip (remote mode), error handlers and routers. It also mounts `panoptic/html/` as static files, opens the browser and runs uvicorn.
- [ ] `panoptic/core/__init__.py` · package marker
- [ ] `panoptic/core/server/__init__.py` · package marker
- [ ] `panoptic/core/server/panoptic_server.py` · 486 L. Owns Socket.IO:
  - handles the `connect`, `disconnect`, `load_project` and `close_project` events
  - maps sid → connection → project
  - runs one `DbWatcher` and one `PluginWatcher` per loaded project
  - bridges sync task callbacks to async
  - broadcasts projects, plugins, users, connection state, commits and tasks
- [ ] `panoptic/core/watcher/__init__.py` · package marker
- [ ] `panoptic/core/watcher/db_watcher.py` · 56 L. `DbWatcher`: notices commits written to a project's DB (or `panoptic.db`) by another process and triggers a broadcast. Used by `panoptic_server.py`.
- [ ] `panoptic/routes/__init__.py` · package marker
- [ ] `panoptic/routes/deps.py` · 33 L. Module-level holders for `Panoptic` / `PanopticServer`, plus the `get_project` dependency. The docstring still says "panoptic2 routes", the old package name.
- [ ] `panoptic/routes/panoptic_routes.py` · 419 L. Instance-level routes: projects, plugins state, users (create/delete/connect) and filesystem helpers (ls, count, info).
- [ ] `panoptic/routes/project_routes.py` · 1874 L. Everything under `/projects/{project_id}`:
  - DB state streams (ndjson, slim and full) and deltas
  - CRUD for properties, tags, values and folders
  - CSV import (`UploadFile`) and export
  - IIIF, actions and history

  At 1874 lines it's the largest file in the backend and a good candidate for splitting by resource. Last changed 2026-09-11.
- [ ] `panoptic/models/__init__.py` · package marker. Empty, although the broken tests still import names from it ([[09 Tests and fixtures]]).
- [ ] `panoptic/models/models.py` · 132 L. Pydantic API models: `PropertyType`, `PropertyMode`, `Property`, `Tag`, `Instance`, `TaskState`, `ProjectSettings`. Plugins import this module too (see [[07 Plugin system]]).
- [ ] `panoptic/models/stream_models.py` · 107 L. msgspec structs for the `db_state_stream` ndjson response: `FullInstance`, `StreamChunk`, the `*ValuesColumn` types, `LoadState`, `TagCount`, `StreamResult`.
