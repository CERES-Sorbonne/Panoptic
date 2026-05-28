# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend
```bash
cd panoptic_back
pip3 install -e .          # install in dev mode
python panoptic2/main.py   # run server (default port 8000)
```

### Frontend
```bash
cd panoptic_front
npm install
npm run dev    # Vite dev server (port 5173, proxies API to :8000)
npm run build  # builds into panoptic_back/panoptic/html
npm run lint   # ESLint with auto-fix
```

### Integrated dev
Start backend first, then set `PANOPTIC_ENV=DEV` before starting the frontend. The env var makes the backend serve the live Vite dev server instead of the built HTML.

Key backend env vars: `PANOPTIC_PORT` (default 8000), `PANOPTIC_DB` (default `~/.panoptic2/panoptic.db`), `PANOPTIC_WATCH_PLUGINS=1` to enable hot-reload of plugins.

---

## Architecture

### Overview
Panoptic is a local image management tool. A Python FastAPI backend owns all data (SQLite) and serves a Vue 3 SPA. Real-time multi-client sync runs over Socket.IO.

```
Vue 3 SPA (Pinia stores)
      │  HTTP REST + Socket.IO
      ▼
FastAPI + uvicorn  (panoptic_back/panoptic2/)
      │
      ▼
SQLite  (panoptic.db global  +  one data.db per project)
```

### Backend structure

`panoptic2/main.py` — entry point, wires together FastAPI app and Socket.IO server.

`core/server/panoptic_server.py` — `PanopticServer2`: manages Socket.IO connections, broadcasts events (`commits`, `tasks`, `update_projects`, `connection_state`), owns `DbWatcher` (watchfiles) per open project.

`core/panoptic/panoptic.py` — `Panoptic2`: global engine, manages project creation/deletion and plugin installation.

`core/project/project.py` — `Project2`: per-project façade over the SQLite databases. All reads/writes go through here. Key method: `apply_upsert_commit` / `apply_delete_commit`.

**Three databases per project:**
- `data.db` — all user data: instances, files, folders, properties, tags, values, commits. Managed by `DataWriter`/`DataReader`. Every mutation is append-only in `*_log` tables; current state is in the main tables.
- `media.db` — image thumbnails (typed-array BLOBs), atlases, vectors. Managed by `MediaDB`.
- `project.db` — config, tab state, user defaults. Managed by `ProjectDB`.

`core/databases/entity_schema.py` — `EntitySchema`/`PropertyValueSchema`: auto-derives SQL schema from `msgspec.Struct` definitions; handles upsert, log, chunked queries, and commit replay (`re_compute`). Central to all DB access.

`core/databases/data/create.py` — `datastore_desc`: `DbDescription` with schema version and migration chain. Bump `version` and add a function to `migrations` dict for any schema change.

`routes/project_routes.py` — most endpoints live here. The initial load is a streaming NDJSON response (`/db_state_stream`): chunks out properties, tags, instances, then values (instance/sha1/file). A final terminal chunk is always emitted even when all value tables are empty.

### Frontend structure

`src/data/dataStore.ts` — main Pinia store: instances, folders, properties, tags, commits. Receives stream data and delta updates.

`src/data/dataStore2.ts` — `ColumnStore`: non-reactive typed-array storage designed for 1M-scale datasets. Stores per-property value columns as `Float64Array`/`Uint8Array`/`string[]`. Only `fullColumnStatus` is reactive (Vue observes it for loading indicators). META pseudo-property IDs (`META.WIDTH=-1`, `.HEIGHT=-2`, `.SHA1=-3`, `.FOLDER_ID=-4`) are read directly from typed arrays without a network call. Lazy column fetch via `requireInstanceValues` / `requireFullColumn`.

`src/data/socketStore.ts` — Socket.IO event handlers; bridges server events into the Pinia stores.

`src/data/models.ts` — shared TypeScript interfaces. `PropertyType` enum mirrors backend `dtype` strings. `PropertyMode` (`sha1 | id | file`). `Property.systemKey` identifies system-owned properties.

`src/core/GroupManager.ts` — drives all grouping, sorting, filtering. `CollectionManager` holds the current filtered/sorted instance list. `TabManager` owns one `CollectionManager`.

`src/components/data/InstanceData.vue` — renderless component: given `instanceIds` and `propIds`, fetches values via `ColumnStore.requireInstanceValues`, pre-populates META values synchronously before first render (avoids undefined on initial paint), exposes results through a scoped slot.

### Property system

Properties have three orthogonal fields:
- `dtype` — pure value shape (`number`, `text`, `date`, `tag`, `multi_tags`, …). Also includes special display-hint types like `sha1`, `folder`, `id` for the frontend.
- `mode` — value scope: `file` (one value per File row), `sha1` (shared across duplicate files by content), `id` (one value per Instance).
- `system_key` — non-null for system-owned properties (`id`, `sha1`, `folder`, `name`, `width`, `height`, `format`, `created_at`). Lets backend locate a specific property without name collision risk. Frontend uses it for read-only treatment.

System properties are created idempotently on every `project.start()` via `_ensure_system_properties()` in `project.py`. They map to native columns on the `File` table, not to value tables.

### Data commit pattern
All writes use `UpsertCommit` / `DeleteCommit` structs. The backend writes current state + appends to `*_log` tables in one transaction. Frontend receives the result as a Socket.IO `commits` event and merges it into the stores. Log tables enable point-in-time replay via `EntitySchema.re_compute`.

### File metadata
`File` table native columns: `id`, `name` (basename only, not full path), `folder_id`, `sha1`, `width`, `height`, `format`, `created_at`. Full path is reconstructed as `folder.path + '/' + file.name`. Import lives in `core/task/import_folder_task.py`; dedup checks `(folder_id, name)` pairs.
