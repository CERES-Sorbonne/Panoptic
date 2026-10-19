# Panoptic → Rust port — master plan

Status: **in progress** (started 2026-10-12, branch `rust`).
Every agent working on the port reads this file first. Companion docs in this folder:

| doc | owner phase | content |
|---|---|---|
| `PLAN.md` | — | this file: goals, architecture, phases, rules |
| `API_CONTRACT.md` | P1-B | every REST route + socket event, request/response shapes (the parity target) |
| `DB_FORMAT.md` | P1-A | on-disk SQLite format of the 4 databases, commit log / sequence protocol |
| `ENGINE.md` | P1-C | semantics of filter / sort / group / sha1 piles / cluster overlay as ported to Rust |
| `PLUGIN_PROTOCOL.md` | P1-D | the new out-of-process plugin protocol |
| `VIEW_PROTOCOL.md` | P4 | the client ⇄ backend collection/view protocol (windowed results) |
| `PROGRESS.md` | all | short log: what each phase delivered, open issues, deviations from this plan |

---

## 1. Goals

1. **The Panoptic backend is pure Rust.** No Python at runtime for the core app. Python remains only for
   (a) AI/other plugins, each a standalone process in its own uv venv, and (b) the legacy-project
   migration tool (`panoptic_back/panoptic/migration`), launched on demand through uv.
2. **Never-blocking UI.** All heavy computation — filtering, sorting, grouping, counting, sha1 piles,
   cluster overlays, aggregations for charts — runs on the backend. The frontend renders windows of
   results and never iterates the whole collection.
3. **One interface, two deployments.** A single HTTP + WebSocket API (axum + socket.io via
   `socketioxide`) serves:
   - **Desktop**: the Rust core + API server run *inside* the Tauri process (bound to `127.0.0.1`,
     random port, per-launch token). No sidecar.
   - **Browser**: the same crates built as a headless `panoptic-server` binary; a pure browser UI
     points at a (possibly remote) backend URL.
4. **On-disk compatibility.** Existing projects (`panoptic.db`, `project.db`, `data.db`, `media.db`,
   `atlas/*.png`, `plugin_data/`) open unchanged. The SQLite schema and value encodings are kept
   byte-compatible with the current Python backend so that plugins and the Python migration tool can
   read/write the same files.

Non-goals for this port: changing the data model, changing the visual design of the UI.

---

## 2. Target architecture

```
                 ┌──────────────── Tauri app (desktop) ────────────────┐
                 │  webview (Vue)  ──HTTP/WS 127.0.0.1:<port>──┐       │
                 │                                             ▼       │
                 │      panoptic-api (axum + socketioxide)  ◄── same ──┼── panoptic-server (headless bin)
                 │                │                                    │        ▲
                 │      panoptic-core (Panoptic, Project, tasks,       │        │ HTTP/WS
                 │        import, media, plugin host, exporter)        │   browser UI (remote)
                 │        │                 │                          │
                 │  panoptic-engine    panoptic-db (rusqlite, WAL)     │
                 │  (columnar compute)      │                          │
                 └──────────────────────────┼──────────────────────────┘
                                            │ same SQLite files
        plugin process (python, own venv) ──┘ direct read (and optional write)
              │
              └── WebSocket JSON-RPC  ──►  panoptic-api  /plugin  endpoint (token auth)
```

### 2.1 Repository layout

```
Cargo.toml                       cargo workspace (members below)
crates/
  panoptic-db/                   SQLite layer: 4 DBs, entity schema, commit log, sequence, delta, undo/redo
  panoptic-engine/               in-memory columnar store + filter/sort/group/count/piles/clusters + windows
  panoptic-core/                 Panoptic + Project facades, users/sessions, TaskManager, import pipeline
                                 (scan, sha1, thumbnails, atlas, IIIF), media serving, CSV import/export,
                                 plugin host (spawn/supervise/RPC/install), legacy-migration launcher
  panoptic-api/                  axum router: REST (parity with Python), socket.io events, view protocol,
                                 plugin endpoint, auth; `serve(config) -> ServerHandle`
  panoptic-server/               headless binary + CLI (replaces `panoptic` python CLI)
panoptic_front/src-tauri/        Tauri app; depends on panoptic-api and starts it in-process
panoptic_plugin_sdk/             python package `panoptic_plugin` (uv project): plugin base class,
                                 socket RPC client, direct SQLite read/write helpers, task API
panoptic_back/                   python reference implementation — kept until parity is proven;
                                 `panoptic.migration` stays as the on-demand legacy migration tool
technical_docs/rust_port/        this documentation
```

### 2.2 Key technical choices

| concern | choice |
|---|---|
| async runtime | tokio (multi-thread) |
| CPU work | rayon; never on tokio worker threads (use `spawn_blocking` / rayon + oneshot) |
| HTTP | axum 0.8, tower-http (cors, compression, static files) |
| realtime | socketioxide (socket.io protocol → frontend `socket.io-client` unchanged during parity) |
| SQLite | rusqlite (bundled), WAL, `busy_timeout`, one writer connection per DB + reader pool (r2d2 or own) |
| serialization | serde; JSON field names identical to the Python responses (camelCase where Python used `fastapi-camelcase`); msgpack (`rmp-serde`) for binary view frames |
| images | `image` + `fast_image_resize`; sha1 via `sha1`/`sha1_smol`; formats = whatever the python `IMAGE_EXTENSIONS` lists, best effort (document unsupported ones in PROGRESS.md) |
| IIIF / HTTP client | reqwest (rustls) |
| CSV | `csv` crate (polars-equivalent behaviour only where the python importer/exporter needs it) |
| logging | `tracing` + `tracing-subscriber` (file + stderr) |
| errors | `thiserror` in libraries, `anyhow` in binaries; API maps errors to the same status codes as python |
| tests | `cargo test` per crate; cross-implementation tests drive the python reference via `panoptic_back/.venv` |

### 2.3 Never-blocking rules (apply everywhere)

- No request handler does CPU work or blocking IO on a tokio worker: use `spawn_blocking` or rayon.
- Every collection computation carries `(collection_id, version)`. A newer version cancels the older
  one (cooperative `CancellationToken` / `AtomicBool` checked inside rayon loops). Latest wins.
- Engine data is held as immutable snapshots (`Arc` per column, `arc-swap` for the store root).
  Writes build the next snapshot; readers never wait on writers.
- Results are delivered as *summaries + windows*: the client asks for the rows it can see.
- Edits are optimistic on the client; the backend confirms by pushing a new result revision.
- Long jobs (import, thumbnails, atlas, plugin actions) are tasks with progress events, never awaited
  by an HTTP request.

### 2.4 Engine and view protocol (summary — full spec in `ENGINE.md` / `VIEW_PROTOCOL.md`)

- Per loaded project the backend holds a **ColumnStore**: instance slots, identity columns
  (id, sha1, file_id), lazily loaded typed property columns (numeric, bool, interned string, date,
  tag CSR), deleted mask, selection bitsets per namespace.
- It is kept up to date from the **sequence/delta** mechanism of data.db, which also catches writes
  made directly by plugin processes (sequence polling, port of `DbWatcher`).
- A **Collection** = filter + sort + group (+ sha1 mode, group options, cluster overlay / custom
  groups) for a tab collection. The server computes a **GroupTree** (stable group ids via a
  persistent value index, per-group counts, display order) and keeps it per collection.
- The client receives: the result summary (total, group count, revision), **group-tree pages**
  (headers of the expanded part of the tree) and **item windows** (instance ids + the property values
  of the visible columns for a row range, grid layout given `items_per_row`). Map view gets compact
  binary arrays (ids, x, y, group colour index). Charts get server-side aggregations.
- Selection lives server-side (bitset per namespace); the client sends ops (toggle, range, group,
  all, none) and receives counts + the selection state of its visible window.

### 2.5 Plugin system (summary — full spec in `PLUGIN_PROTOCOL.md`)

- A plugin is a Python project (pyproject.toml) installed into **its own uv venv**
  (`~/.panoptic/plugins/<name>/.venv`) together with the `panoptic_plugin` SDK.
- The backend spawns one plugin process per (plugin, loaded project) and supervises it
  (restart/stop, logs captured, crash reported to the UI).
- The process connects back over **WebSocket** to `/plugin` on the backend (token from env) and speaks
  **JSON-RPC 2.0**: `hello` (name, version, actions, params schema) → backend sends `project.open`,
  `action.execute`, `event.*`, `params.update`, `shutdown`; plugin sends `task.*` (progress),
  `notify`, `commit` (writes routed through the backend for undo/history), `db.changed`.
- Plugins **read the SQLite DBs directly** (SDK helpers, read-only connections, WAL) and **may write
  directly** (SDK writer that follows the sequence/commit-log protocol of `DB_FORMAT.md`); after a
  direct write they send `db.changed` and the backend applies the delta (the sequence poll is the
  safety net).
- The old in-process API (`APlugin`, `PluginProjectInterface`) is replaced. PanopticML and other
  plugins are ported to the new base class.

### 2.6 Legacy migration

`panoptic_back/panoptic/migration` stays Python. `panoptic-core` exposes the same routes
(`/legacy/projects`, `/legacy/migrate`, …) and runs the tool through uv in an isolated venv
(`uv run --project <bundled migration package> python -m panoptic.migration.cli …`), streaming its
report back.

---

## 3. Phases

Each phase ends with a **gate**; the next phase starts only when the gate passes (or the deviation is
written in `PROGRESS.md`).

### P0 — scaffold (orchestrator)
Toolchain (rustc ≥ 1.99), cargo workspace, empty crates, this plan.

### P1 — foundations (parallel)
- **P1-A `panoptic-db`**: port `core/databases/**` (entity_schema, sqlite_db, key-value schema,
  data reader/writer with commit log, sequence, delta, undo/redo, compaction; media_db; project_db;
  panoptic_db). Write `DB_FORMAT.md`. Cross tests: DB written by python is read by Rust and vice versa;
  same operations produce equivalent rows.
- **P1-B API contract**: write `API_CONTRACT.md` (all routes in `routes/*.py`, all socket events in
  `core/server/panoptic_server.py`, cross-checked with `panoptic_front/src/data/api/*.ts` and
  `socketStore.ts`) and a **contract test harness** (`panoptic_back/test/contract/`, pytest + httpx +
  python-socketio client) that runs scenarios against a base URL. Record golden responses from the
  python backend on a fixture project.
- **P1-C `panoptic-engine`**: port the frontend compute (`src/core/FilterManager.ts`, `SortManager.ts`,
  `GroupManager.ts`, `sha1Piles.ts`, `group/*`, `ClusterManager/ClusterOverlay`) to Rust over an
  abstract ColumnStore. Golden tests: a node harness runs the TS engine on fixtures and dumps results;
  the Rust engine must match. Write `ENGINE.md`.
- **P1-D plugin protocol + SDK**: write `PLUGIN_PROTOCOL.md`; build `panoptic_plugin_sdk` (base class,
  action decorators/introspection, RPC client, task progress, DB read/write helpers) with tests
  against a mock backend.

Gate: `cargo test -p panoptic-db -p panoptic-engine` green; contract harness green against python;
SDK tests green.

### P2 — core + API parity (parallel)
- **P2-E `panoptic-core`**: Panoptic (projects/users/sessions/user data, registry in panoptic.db),
  Project facade, TaskManager, file sources (local + IIIF), import pipeline (scan → sha1 → thumbnails
  → write batches), image types, thumbnail generation, atlas generation, maps/vectors read, CSV
  import/export, legacy migration launcher, filesystem browsing.
- **P2-F `panoptic-api` + `panoptic-server`**: every REST route and socket event of
  `API_CONTRACT.md`, NDJSON streams, image serving, auth/connection handling; CLI with the python
  CLI's options.

Gate: contract harness green against the Rust server (same goldens as python); frontend works
unchanged against the Rust server (manual smoke run).

### P3 — plugin host
Plugin installer (uv venvs), process supervisor, `/plugin` WebSocket JSON-RPC endpoint, action
routing (`/actions`, `/action_execute`, `/plugins_info`, `/plugin_params`, start/stop), plugin tasks
in the TaskManager, `db.changed` handling. Port `dev_plugins/PathInputTest`; port PanopticML
(separate repo, see PROGRESS.md for status).

Gate: PathInputTest and PanopticML (vectors, similarity, clustering) run end-to-end.

### P4 — backend compute integration
ColumnStore fed from data.db + delta stream; collection sessions per client/tab; cancellation and
coalescing; selection; aggregations for charts; map arrays. Socket/WS view protocol, documented in
`VIEW_PROTOCOL.md`. Benchmarks on a 1M-instance synthetic project.

Gate: engine golden tests still green through the protocol; p95 recompute < 100 ms at 1M instances
for filter+sort+single group; no handler blocks a tokio worker (checked with tokio-console or timing).

### P5 — frontend thin client
Replace `columnStore` / Filter/Sort/Group/Cluster managers with a `RemoteCollection` client (result
summary + page/window caches + optimistic edits). Adapt TreeScroller/GroupLine, ImageScroller/grid,
ClusterScroller, MapView, graph/RecommendView, selection, property edits. Remove dead compute code.

Gate: `npm run typecheck` + remaining frontend tests green; UI never freezes on 1M instances
(main-thread long tasks < 50 ms during filter/sort/group changes and scrolling).

### P6 — packaging
Tauri app embeds `panoptic-api` (remove python install/launch code from `src-tauri/src/lib.rs`, keep
uv management for plugins), headless `panoptic-server` + Dockerfile, browser build pointing at a
configurable backend URL, docs.

Gate: desktop app builds and opens an existing project; headless server serves the browser UI.

---

## 4. Rules for agents

- **Never `git commit`, push, or open PRs.** The user commits. Leave changes in the working tree.
- Stay inside the directories your task owns; other agents work in parallel. If you must touch a
  shared file (workspace `Cargo.toml`, this plan), make minimal additive edits.
- Read the python reference before porting; behaviour parity first, refactors later. When the python
  code has a bug or the plan is wrong, note it in `PROGRESS.md` instead of silently diverging.
- Python reference env: `panoptic_back/.venv` (python 3.13, uv). Run python tests from
  `panoptic_back/test/`.
- Everything you build must have tests that run with `cargo test` (Rust) / `pytest` (Python) /
  `npm test` (front).
- Append a short entry to `PROGRESS.md` when you finish: delivered, tests, known gaps.
