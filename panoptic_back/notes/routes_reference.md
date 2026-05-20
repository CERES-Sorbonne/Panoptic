# Panoptic API Routes Reference

All routes registered in the FastAPI app. The backend has two versions: **v1** (`panoptic/`) and **v2** (`panoptic2/`). Both share the same structure but v2 has several endpoints marked as not yet implemented (501).

---

## v1 Routes (`panoptic/`)

### Panoptic-level routes — `panoptic/routes/panoptic_routes.py`

No prefix.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/panoptic_state` | Current app state (open projects, plugin list, etc.) |
| POST | `/ignored_plugin` | Update the list of ignored plugins |
| POST | `/load` | Load a project by ID |
| POST | `/update_project` | Update project name / metadata |
| POST | `/close` | Close the currently open project |
| POST | `/delete_project` | Delete a project (optionally delete files on disk) |
| POST | `/create_project` | Create a new project at a given path |
| POST | `/import_project` | Import an existing project from a path |
| GET | `/filesystem/ls/{path:path}` | List directory contents; marks image dirs and existing projects |
| GET | `/filesystem/info` | Disk partitions, home directories |
| GET | `/filesystem/count/{path:path}` | Recursively count images under a path |
| GET | `/plugins` | List available plugins |
| POST | `/plugins` | Add a plugin (pip package, git URL, or local path) |
| POST | `/plugin/update` | Reinstall / update a plugin |
| DELETE | `/plugins` | Remove a plugin by name |
| GET | `/images/{file_path:path}` | Serve an image file directly from disk |
| GET | `/packages` | Versions of key Python packages (numpy, torch, sklearn…) |

### Project-level routes — `panoptic/routes/project_routes.py`

Prefix: `/projects/{project_id}`

| Method | Path (after prefix) | Purpose |
|--------|---------------------|---------|
| GET | `/project_state` | Project runtime state |
| GET | `/db_state` | Full DB snapshot (instances, properties, tags, values) |
| GET | `/db_state_stream` | Same as above, streamed as newline-delimited JSON |
| GET | `/property` | All properties (including computed ones) |
| GET | `/tags` | All tags, optionally filtered by property |
| POST | `/tags/merge` | Merge multiple tags into one |
| GET | `/folders` | Imported folder metadata |
| POST | `/folders` | Add a folder for import |
| POST | `/reimport_folder` | Reimport a folder by ID |
| DELETE | `/folder` | Remove a folder by ID |
| POST | `/import/upload` | Upload a CSV file for import |
| POST | `/import/parse` | Parse uploaded CSV and verify column mapping |
| POST | `/import/confirm` | Confirm and execute the CSV import |
| POST | `/import/tags` | Import tags from an uploaded file |
| POST | `/export` | Export properties (and optionally images) |
| GET | `/history` | Undo/redo history stats |
| POST | `/undo` | Undo the last change |
| POST | `/redo` | Redo the last undone change |
| POST | `/commit` | Apply a DB commit (upsert/delete instances, properties, tags, values) |
| GET | `/image/raw/{sha1:path}` | Original image file |
| GET | `/image/large/{sha1:path}` | Large thumbnail |
| GET | `/image/medium/{sha1:path}` | Medium thumbnail |
| GET | `/image/small/{sha1:path}` | Small thumbnail |
| POST | `/action_execute` | Execute a plugin action with context |
| GET | `/actions` | Available plugin actions and their descriptions |
| GET | `/plugins_info` | Plugin info for this project |
| GET | `/ui_data/{key:path}` | Get stored UI state (tab layout, preferences…) |
| POST | `/ui_data` | Save UI state |
| POST | `/plugin_params` | Set plugin parameters |
| GET | `/vectors_info` | Vector embedding metadata |
| GET | `/vector_types` | Available vector types |
| GET | `/vector_stats` | Statistics about stored vectors |
| POST | `/delete_vector_type` | Remove a vector type by ID |
| POST | `/default_vectors` | Set the default vector type |
| GET | `/settings` | Project settings |
| POST | `/settings` | Update project settings |
| GET | `/list_maps` | All 2D projection maps (t-SNE, UMAP…) |
| GET | `/map/{map_id}` | A specific map by ID |
| DELETE | `/map` | Delete a map by ID |
| POST | `/delete_empty_clones` | Remove instance clones that have no values |
| GET | `/benchmark` | Fetch all instances + property values (perf testing) |
| GET | `/atlas/{atlas_id}` | Image atlas metadata |
| GET | `/atlas_sheet/{atlas_id}/{sheet_nb}` | A specific atlas sheet as PNG |
| GET | `/spritesheet` | Spritesheet (static path) |

---

## v2 Routes (`panoptic2/`)

### Panoptic-level routes — `panoptic2/routes/panoptic_routes.py`

No prefix. Mirrors v1; same purposes unless noted.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/panoptic_state` | App state |
| POST | `/create_project` | Create project |
| POST | `/import_project` | Import project |
| POST | `/load` | Load project by ID |
| POST | `/close` | Close project |
| POST | `/update_project` | Update project name / plugin settings |
| POST | `/delete_project` | Delete project |
| GET | `/plugins` | List plugins |
| POST | `/plugins` | Add plugin |
| POST | `/plugin/update` | Reinstall plugin |
| DELETE | `/plugins` | Delete plugin by ID |
| GET | `/images/{file_path:path}` | Serve image from disk |
| GET | `/filesystem/ls/{path:path}` | List directory |
| GET | `/filesystem/info` | Filesystem info |
| GET | `/filesystem/count/{path:path}` | Count images in directory |
| GET | `/packages` | Python package versions |

### Project-level routes — `panoptic2/routes/project_routes.py`

Prefix: `/projects/{project_id}`

| Method | Path (after prefix) | Purpose |
|--------|---------------------|---------|
| GET | `/db_state_stream` | Stream full project state as newline-delimited JSON |
| GET | `/db_state` | Full DB snapshot |
| GET | `/property` | Properties |
| GET | `/tags` | Tags |
| GET | `/folders` | Folders |
| GET | `/instances` | Instances |
| POST | `/commit/upsert` | Create or update instances / properties / values |
| POST | `/commit/delete` | Delete entities |
| POST | `/undo` | Undo |
| POST | `/redo` | Redo |
| GET | `/history` | History stats |
| GET | `/image/small/{sha1:path}` | Small thumbnail (falls back to large) |
| GET | `/image/large/{sha1:path}` | Large thumbnail (falls back to small) |
| GET | `/image/raw/{sha1:path}` | Original image |
| GET | `/image/medium/{sha1:path}` | Medium image (alias for large) |
| POST | `/action_execute` | Execute plugin action |
| GET | `/actions` | Available actions |
| GET | `/plugins_info` | Plugin descriptions |
| GET | `/ui_data/{key:path}` | Get UI preferences |
| POST | `/ui_data` | Save UI preferences |
| GET | `/list_maps` | All 2D projection maps |
| GET | `/map/{map_id}` | Map by ID |
| DELETE | `/map` | Delete map |
| GET | `/atlas/{atlas_id}` | Atlas metadata |
| GET | `/vector_types` | Vector type info |
| POST | `/import/upload` | **Not implemented (501)** |
| POST | `/import/parse` | **Not implemented (501)** |
| POST | `/import/confirm` | **Not implemented (501)** |
| POST | `/import/tags` | **Not implemented (501)** |
| POST | `/export` | **Not implemented (501)** |
| GET | `/settings` | **Not implemented (501)** |
| POST | `/settings` | **Not implemented (501)** |

---

## Notes

- Both versions run under the same FastAPI app; v1 and v2 routers are mounted side-by-side.
- Real-time events (import progress, plugin compute progress) are sent over **Socket.IO**, not REST.
- Image endpoints (`/image/raw`, `/image/large`, etc.) return the file bytes directly and are used by the frontend grid/detail views.
- The `/db_state_stream` endpoint is preferred over `/db_state` for large projects — it chunks the payload so the UI can render incrementally.
- v2 commit is split into `/commit/upsert` and `/commit/delete` (v1 uses a single `/commit` with mixed payload).
