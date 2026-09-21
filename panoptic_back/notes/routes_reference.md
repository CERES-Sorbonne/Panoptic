# Panoptic API Routes Reference

Every route registered in the FastAPI app, regenerated from
`panoptic/routes/panoptic_routes.py` and `panoptic/routes/project_routes.py` on **2026-09-21**
(`5a6893b9`).

> The v1 / v2 split this note used to describe is gone: there is no `panoptic2/` package any
> more. What was "v2" is simply `panoptic/` today, and the endpoints that were stubbed at 501
> (import, export, settings) are implemented.

---

## Panoptic-level routes — `panoptic/routes/panoptic_routes.py`

No prefix.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/projects` | Known projects (the home DB's project list) |
| GET | `/plugins` | Installed plugins and their state |
| POST | `/plugins` | Add a plugin (pip package, git URL or local path) |
| DELETE | `/plugins` | Remove a plugin |
| POST | `/plugin/update` | Reinstall / update a plugin |
| GET | `/users` | Local user profiles |
| POST | `/users` | Create a user profile |
| DELETE | `/users/{user_id}` | Delete a user profile |
| POST | `/connect_user` | Connect a user to the running instance (multi-user sessions) |
| POST | `/disconnect_user` | Disconnect that user |
| POST | `/create_project` | Create a project at a path |
| POST | `/import_project` | Import an existing project folder |
| POST | `/load` | Load a project by id |
| POST | `/close` | Close the open project |
| POST | `/update_project` | Rename a project / update its metadata |
| POST | `/delete_project` | Delete a project (optionally its files) |
| GET | `/images/{file_path:path}` | Serve an image straight from disk |
| GET | `/filesystem/ls/{path:path}` | List a directory, flagging image folders and projects |
| GET | `/filesystem/info` | Partitions and home directories |
| GET | `/filesystem/count/{path:path}` | Count images under a path |
| GET | `/packages` | Versions of key Python packages |
| GET | `/legacy/projects` | Pre-2.0 projects found on disk, offered for migration |
| POST | `/legacy/migrate` | Migrate one legacy project |
| POST | `/legacy/dismiss` | Stop offering a legacy project |
| GET | `/legacy/report/{run_id}` | Report of a migration run |

---

## Project-level routes — `panoptic/routes/project_routes.py`

Prefix: `/projects/{project_id}`. Most take `user_id` as a query parameter; undo/redo and the
history stacks are **per author**.

### Loading the project state

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/init_state` | Lightweight init payload: file sources, folders, tags, properties + current sequence |
| GET | `/db_state` | Full DB snapshot in one response |
| GET | `/db_state_stream` | The same, as newline-delimited `LoadResult` chunks |
| GET | `/db_state_slim` | Structural state only (properties + instances, no values), NDJSON |
| GET | `/delta` | Every row changed since `since`, as one `StreamResult` — the sync endpoint |
| GET | `/project_state` | Project runtime state (tasks, sources, flags) |
| GET | `/instances` | Instances |
| GET | `/instances/base` | Instance base columns, batched NDJSON, for `columnStore` init |
| GET | `/instances/column/{prop_id}` | All values of one property column, batched NDJSON |
| POST | `/instances/values` | Values for a subset of instances × properties (lazy column load) |

### Properties, tags & allocation

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/property` | All properties, computed ones included |
| GET | `/tags` | All tags, optionally filtered by property |
| GET | `/tags/counts` | Instance count per tag |
| POST | `/tags/merge` | Merge tags into one |
| GET | `/allocate/tags` | Reserve tag ids for the client |
| GET | `/allocate/property_groups` | Reserve property-group ids |

### Folders & file sources

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/file_sources` | Registered file sources |
| DELETE | `/file_source` | Remove a file source |
| POST | `/file_source/resync` | Re-scan a source for new or missing files |
| GET | `/folders` | Imported folder metadata |
| GET | `/folders/counts` | Image count per folder |
| POST | `/folders` | Add a folder for import |
| POST | `/reimport_folder` | Re-import a folder |
| DELETE | `/folder` | Remove a folder |
| POST | `/import/iiif` | Import a IIIF Collection/Manifest URL as a file source |
| POST | `/iiif/test` | Test a IIIF URL and return its metadata |

### Writes, undo/redo & the commit log

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/commit/upsert` | Create or update instances / properties / tags / values |
| POST | `/commit/delete` | Delete entities |
| POST | `/undo` | Undo the caller's most recent still-active commit (per author) |
| POST | `/redo` | Redo their oldest undone commit that is still `redoable` |
| GET | `/history` | The caller's undo and redo stacks (`scope=all` for everyone's) |
| GET | `/commits` | Full commit timeline, newest first |
| POST | `/set_commit_active` | Toggle one commit on or off — non-sequential undo |
| POST | `/compact` | Fold commits up to an id into the frozen baseline (irreversible) |

A commit that asserts state the DB already holds writes no row and returns nothing to undo;
writing a new commit clears the author's redo stack. See `notes/versioning_multiuser_undo.md`.

### Images & renditions

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/image/by_size/{sha1:path}` | Best-fit rendition for `size=N`; omit `size` for the largest |
| GET | `/image/small/{sha1:path}` | Small thumbnail |
| GET | `/image/medium/{sha1:path}` | Medium thumbnail |
| GET | `/image/large/{sha1:path}` | Large thumbnail |
| GET | `/image/raw/{sha1:path}` | Original file |
| GET | `/image_types` | Configured rendition types |
| POST | `/image_types` | Create or update one |
| DELETE | `/image_types/{type_id}` | Delete one |
| POST | `/image_types/generate` | (Re)generate missing renditions |
| GET | `/image_stats` | Counts and sizes of stored renditions |
| GET | `/atlas/{atlas_id}` | Atlas metadata for the map view |
| GET | `/atlas_sheet/{atlas_id}/{sheet_nb}` | One atlas sheet as PNG |

### Plugins, actions & vectors

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/actions` | Available plugin actions and their parameters |
| POST | `/action_execute` | Execute an action with a context |
| GET | `/plugins_info` | Plugin descriptions for this project |
| POST | `/plugin_params` | Set plugin parameters |
| GET | `/vector_types` | Vector types |
| GET | `/vectors_info` | Vector metadata |
| GET | `/vector_stats` | Vector statistics |
| POST | `/delete_vector_type` | Remove a vector type |
| POST | `/default_vectors` | Set the default vector type |
| GET | `/list_maps` | All 2D projection maps |
| GET | `/map/{map_id}` | One map |
| DELETE | `/map` | Delete a map |

### UI state & tabs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ui_data` | Every stored UI key at once (what `actionStore` loads at init) |
| GET | `/ui_data/{key:path}` | One key |
| POST | `/ui_data` | Save one key |
| POST | `/ui_data_bulk` | Save several keys in one call |
| GET | `/tabs` | The user's tabs |
| POST | `/tabs` | Create a tab |
| PUT | `/tabs/{tab_id}` | Update a tab's state (the frontend's debounced autosave) |
| DELETE | `/tabs/{tab_id}` | Delete a tab |

### Import, export & settings

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/import/upload` | Upload a CSV and parse its headers |
| POST | `/import/parse` | Map CSV rows to instance ids |
| POST | `/import/confirm` | Write the imported CSV |
| POST | `/import/tags` | Import a tag hierarchy CSV (`name; color; parents`) |
| POST | `/export` | Export properties, optionally with images |
| GET | `/settings` | Project settings |
| POST | `/settings` | Update them |
| POST | `/delete_empty_clones` | Drop instance clones that carry no values |

---

## Notes

- Real-time events (import progress, plugin compute progress, `db_update` after a write) go over
  **Socket.IO**, not REST.
- Image endpoints return file bytes directly and back the grid and detail views.
- Prefer `/init_state` + `/instances/base` + `/instances/column/{prop_id}` over `/db_state` for
  large projects: the frontend's `columnStore` loads columns lazily.
- `/delta` is how a client catches up after reconnecting, using the sequence from `/init_state`.
