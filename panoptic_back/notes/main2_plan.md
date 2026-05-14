# `main2.py` — start script plan

Goal: a new entry point at `panoptic2/main.py` that starts a FastAPI + Socket.IO server
backed by `Panoptic2` / `PanopticServer2`, so the UI can be connected to the new architecture
incrementally while the old `panoptic/main.py` remains intact.

---

## How the old start script works

```
main.py
  panoptic = Panoptic()           # owns project/plugin registry (async, old DB)
  panoptic.start()                # loads panoptic.db
  server = PanopticServer(panoptic)
    └─ sio = socketio.AsyncServer(...)   # owned here
  app = FastAPI(lifespan=lifespan)
  app.mount("/socket.io", socketio.ASGIApp(sio))
  app.include_router(selection_router)   # panoptic-level routes
  app.include_router(project_router)     # /projects/{project_id}/...
  set_server(server)                     # global used by routes
  uvicorn.run(app)
```

### Route dependency pattern

Both routers use a **module-level global**:
```python
# panoptic_routes.py
server: PanopticServer | None = None
def set_server(serv): global server; server = serv
def get_panoptic(): return server.panoptic
```

Project routes resolve the project via:
```python
async def get_project_from_id(project_id: str) -> Project:
    return get_panoptic().get_project(int(project_id))  # integer ID
```

### What each router covers

**`panoptic_routes.py` (selection_router, no prefix):**
- `GET  /panoptic_state`
- `POST /load` / `/close` / `/create_project` / `/import_project`
- `POST /delete_project` / `/update_project` / `/ignored_plugin`
- `GET  /filesystem/ls/{path}` / `/filesystem/info` / `/filesystem/count/{path}`
- `GET  /images/{file_path}` — raw file serve
- `GET  /plugins` / `POST /plugins` / `POST /plugin/update` / `DELETE /plugins`
- `GET  /packages`

**`project_routes.py` (project_router, prefix `/projects/{project_id}`):**
- `GET  /db_state` / `/db_state_stream` — full initial load
- `GET  /property` / `/tags` / `/folders`
- `POST /folders` / `DELETE /folder`
- `POST /action_execute` / `GET /actions` / `GET /plugins_info`
- `POST /commit` / `POST /undo` / `POST /redo` / `GET /history`
- `GET  /image/raw|large|medium|small/{sha1}`
- `GET|POST /ui_data/{key}` / `GET|POST /settings`
- `GET  /list_maps` / `GET /map/{id}` / `DELETE /map`
- `POST /import/upload|parse|confirm` / `POST /import/tags`
- `POST /export`
- `GET  /vectors_info` / `/vector_types` / `/vector_stats`
- `POST /default_vectors` / `/delete_vector_type`
- `GET  /atlas/{id}` / `/atlas_sheet/{id}/{sheet}`

---

## New start script structure

```
panoptic2/
  main.py                    ← new entry point
  routes/
    __init__.py
    panoptic_routes.py       ← panoptic-level routes (Panoptic2)
    project_routes.py        ← project-level routes (Project2)
```

```python
# panoptic2/main.py

import os
import socketio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from panoptic2.core.panoptic.panoptic import Panoptic2
from panoptic2.core.server.panoptic_server import PanopticServer2
from panoptic2.routes.panoptic_routes import panoptic_router, set_dependencies
from panoptic2.routes.project_routes import project_router

def start():
    db_path = os.getenv('PANOPTIC_DB', os.path.expanduser('~/.panoptic/panoptic.db'))
    PORT    = int(os.getenv('PANOPTIC_PORT', 8000))
    HOST    = os.getenv('PANOPTIC_HOST', None)

    panoptic = Panoptic2(db_path)
    panoptic.start()

    sio    = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
    server = PanopticServer2(panoptic, sio)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        server.on_startup()
        yield
        panoptic.close()

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
    app.mount('/socket.io', socketio.ASGIApp(sio))

    set_dependencies(panoptic, server)
    app.include_router(panoptic_router)
    app.include_router(project_router)

    uvicorn.run(app, host=HOST, port=PORT)

if __name__ == '__main__':
    start()
```

---

## Dependency injection pattern (new)

Drop the mutable global + `set_server()`. Use FastAPI `Depends` with a
module-level holder that is set once at startup:

```python
# panoptic2/routes/deps.py

from panoptic2.core.panoptic.panoptic import Panoptic2
from panoptic2.core.server.panoptic_server import PanopticServer2

_panoptic: Panoptic2 | None = None
_server:   PanopticServer2 | None = None

def set_dependencies(panoptic: Panoptic2, server: PanopticServer2):
    global _panoptic, _server
    _panoptic = panoptic
    _server   = server

def get_panoptic() -> Panoptic2:
    return _panoptic

def get_server() -> PanopticServer2:
    return _server
```

Project resolver changes from `int` to `str` UUID:
```python
def get_project(project_uid: str) -> Project2:
    project = get_panoptic().get_project(project_uid)
    if project is None:
        raise HTTPException(404, f'Project {project_uid!r} not loaded')
    return project
```

---

## Route mapping: old → new

### Panoptic-level routes  (keep same URL shape)

| Old | New | Notes |
|---|---|---|
| `GET /panoptic_state` | same | `panoptic.get_state()` |
| `POST /load` | same | `server.load_project(uid, connection_id)` |
| `POST /close` | same | `server.close_project(uid, connection_id)` |
| `POST /create_project` | same | `panoptic.create_project(name, path)` |
| `POST /import_project` | same | `panoptic.import_project(path)` |
| `POST /delete_project` | same | `panoptic.delete_project(uid, delete_files)` |
| `POST /update_project` | same | `panoptic.update_project(uid, name, excluded_plugins)` |
| `GET /plugins` | same | `panoptic.get_plugins()` |
| `POST /plugins` | same | `panoptic.add_plugin(name, source, type)` |
| `POST /plugin/update` | same | `panoptic.reinstall_plugin(id)` |
| `DELETE /plugins` | same | `panoptic.delete_plugin(id)` |
| `GET /images/{path}` | same | raw file serve, no logic change |
| `GET /filesystem/ls/{path}` | same | pure filesystem, copy as-is |
| `GET /filesystem/info` | same | copy as-is |
| `GET /filesystem/count/{path}` | same | copy as-is |
| `GET /packages` | same | copy as-is |

### Project-level routes  (prefix changes: `int` → `str` UUID)

Old prefix: `/projects/{project_id}` (int)
New prefix: `/projects/{project_uid}` (str UUID)

| Old | New | Notes |
|---|---|---|
| `GET /db_state` | → `/commits` or same | returns `get_commits()` + all data |
| `GET /db_state_stream` | same | ndjson stream of full state |
| `GET /property` | same | `project.get_properties()` |
| `GET /tags` | same | `project.get_tags()` |
| `GET /folders` | same | `project.get_folders()` |
| `POST /folders` | same | import folder (not yet ported) |
| `POST /action_execute` | same | `project.action.call(fn, ctx)` |
| `GET /actions` | same | `project.action.get_all()` |
| `GET /plugins_info` | same | `[p.get_description() for p in project.plugins]` |
| `POST /commit` | same | `project.apply_upsert_commit(...)` |
| `POST /undo` / `/redo` | same | need undo queue on `Project2` |
| `GET /history` | same | need undo queue on `Project2` |
| `GET /image/raw\|large\|medium\|small/{sha1}` | same | `MediaDB` lookups |
| `GET /ui_data/{key}` / `POST /ui_data` | same | `ProjectDB` tab/user data |
| `GET|POST /settings` | skip for now | not yet ported |
| `GET /list_maps` etc. | same | `project.get_maps()` etc. |
| `POST /import/*` | skip for now | importer not yet ported |
| `GET /vectors_info` etc. | same | `MediaDB` vector methods |

---

## Implementation order

1. **`panoptic2/routes/deps.py`** — dependency holder, `get_panoptic()`, `get_project(uid)`
2. **`panoptic2/routes/panoptic_routes.py`** — panoptic-level routes (all straight mappings)
3. **`panoptic2/routes/project_routes.py`** — minimal set to boot UI:
   - `GET /db_state_stream` (initial load)
   - `GET /property`, `/tags`, `/folders`
   - `POST /commit`, `POST /undo`, `POST /redo`
   - `POST /action_execute`, `GET /actions`, `GET /plugins_info`
   - `GET /image/small|large|raw|medium/{sha1}`
   - `GET|POST /ui_data/{key}`
4. **`panoptic2/main.py`** — wire everything and run

Routes not yet ported (import, export, settings, reimport, benchmarks) can raise
`HTTP 501 Not Implemented` initially so the UI fails gracefully instead of crashing.

---

## What the UI needs to change

- Project IDs: the UI currently sends `project_id: int` everywhere. It will need to
  send `project_uid: str` (UUID) instead. This is the one breaking change.
- Everything else keeps the same URL and payload shape.

Mitigation: run both old `main.py` (port 8000) and new `main2.py` (port 8001) in
parallel during transition so the UI can be switched by changing a base URL config.
