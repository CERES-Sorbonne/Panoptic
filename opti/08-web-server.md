# 08: Web server

Status 2026-11-06: proposal. The web server block of the Rust backend (README): it serves the
web UI and the HTTP API, and keeps one socket.io connection per client for the view messages
of note 07 and for change events. Sources: today's server
(`panoptic_back/panoptic/core/server/panoptic_server.py`, `panoptic_back/panoptic/routes/`) and
the front's `socketStore.ts` and `data/api/`.

## 1. Role and deployments

One process serves everything: the built front (static files), the HTTP API (§2) and socket.io
(§3). It hosts the open projects (note 00), each with its engine (note 06) and storage
(note 02), in the same process, so a request reads the published results and columns directly,
with no copy between processes. The server holds no project state beyond sessions and views: a
route calls the Project to write or start a task, or reads the engine's results.

- **Desktop.** The Tauri app starts the server on localhost and opens its webview on it.
- **Browser.** The same server, reached over the network (a docker image, a lab server). Several
  users can be connected to one backend; each connection has a user (§3.1).

The async runtime (tokio) handles HTTP and socket.io. Compute runs on the engine's rayon pool
(note 06 §4.1) and SQLite on blocking threads (note 02 §5), so no handler blocks the runtime.

## 2. HTTP API

Request / response calls. Today's routes, grouped, with what changes:

| group | routes today | in the Rust server |
|---|---|---|
| install | `/projects`, `/create_project`, `/import_project`, `/delete_project`, `/update_project`, `/load`, `/close`, `/users`, `/connect_user`, `/user_data`, `/plugins`, `/plugin/update`, `/version`, `/packages` | kept |
| filesystem | `/filesystem/ls`, `/filesystem/info`, `/filesystem/count` | kept (the folder picker) |
| schema | `/property`, `/tags`, `/tags/counts`, `/folders`, `/folders/counts`, `/file_sources`, `/allocate/tags`, `/allocate/property_groups` | kept. Allocation reserves ids in `sqlite_sequence` (note 01 §3) |
| full data | `/db_state`, `/db_state_slim`, `/db_state_stream`, `/init_state`, `/instances`, `/instances/base`, `/instances/column/{prop}`, `/delta` | **dropped**: the front no longer holds columns. It reads the schema and asks for slices (note 07) |
| writes | `/commit/upsert`, `/commit/delete`, `/instances/values`, `/tags/merge` | kept. A write replies with its sequence, and the front awaits the data event at that sequence (§4) for its optimistic overlay |
| history | `/undo`, `/redo`, `/history`, `/commits`, `/set_commit_active`, `/compact` | kept |
| sources | `/folders` (import), `/reimport_folder`, `/file_source/resync`, `/folder`, `/file_source` (delete), `/import/iiif` | rescans and their report (note 04 §5) |
| imports | `/import/upload`, `/import/parse`, `/import/confirm`, `/import/tags`, `/export` | kept; an import is a commit keyed by instance key (note 03 §4) |
| images | `/image/{small,medium,large,by_size,raw}/{sha1}` | `/image/{type}/{image_id}` from `media.db`; `/image/raw/file/{file_id}` and `/image/raw/{image_id}` (any present file) from disk. A failed raw read starts the check of note 04 §3.4 |
| media | `/image_types`, `/image_types/generate`, `/image_stats`, `/vector_types`, `/vector_stats`, `/vectors_info`, `/delete_vector_type`, `/default_vectors`, `/list_maps`, `/map/{id}`, `/atlas/{id}`, `/atlas/generate`, `/atlas_sheet/{id}/{n}` | kept, keyed by image id (note 02 §2) |
| plugins | `/actions`, `/action_execute`, `/plugins_info`, `/plugin/start`, `/plugin/stop`, `/plugin_params` | calls into plugin processes (note 09 §3) |
| tasks | `/task/stop`, `/task/dismiss`, `/tasks/dismiss_finished` | kept; the task list is the Project's (note 00 §7) |
| UI state | `/tabs`, `/tabs/{id}`, `/ui_data`, `/ui_data_bulk`, `/settings` | kept, in `project.db` (note 02 §3) |

- **Thumbnails are immutable.** An image id always names the same bytes (note 01 §3), so a
  thumbnail response carries `Cache-Control: immutable` and the browser cache never needs
  revalidation. A new thumbnail size is a new type id.
- Every project route names its project, so one connection can have several projects open (one
  per window).

## 3. socket.io

### 3.1 Connection and session

- A client connects with a `connection_id` it keeps across reloads, so several sockets (tabs,
  windows, a reconnect) share one session. The session holds the user, the open projects, and
  the selection bitsets (note 07 §7.2).
- On connect the server sends the install state: `update_projects`, `update_plugins`,
  `update_users`, `connection_state` (as today), and reopens the user's last project.
- `load_project` / `close_project` open and close a project for the session. A project is
  loaded once per backend, whatever the number of sessions on it, and its store is shared
  (note 07 §7.1). The project manager opens and closes it (note 00 §3, §4).

### 3.2 View messages

The collection, view, slice, selection and navigation messages of notes 06 §4.2 and 07 §3–§6
(`collection.open`, `collection.setState`, `view.open`, `view.setOpen`, `tree.slice`,
`tree.seek`, `locate`, `step`, `selection.apply`, `group.*`) and their pushes (`result`,
`values`, `stale`, `gone`, `progress`). Note 07 is their specification. Each connection has one
outbound queue in which pushes for the same collection collapse to the latest rev (note 07
§7.7).

## 4. Change events

Clients never poll. Each Project sends its changes as events on one channel (note 00 §6); the
server forwards them to every session that has the project open:

| event | when | payload | the front |
|---|---|---|---|
| `data.changed` | a new store version | `{project, sequence, schema: {properties, tags, tag_lists, property_groups, folders, file_sources}, history}`: the ids of changed schema rows by kind, and whether undo / redo changed | re-reads the changed schema rows; refreshes the history menu. Values reach views through the `result` / `values` / `stale` pushes of note 07 §6, not through this event |
| `scans.changed` | a scan or failed read wrote observed state | `{project, scan_id}` | refreshes the rescan report (note 04 §5.2) |
| `media.changed` | thumbnails, vectors, maps or atlases written | `{project, kind, type_id?}` | refetches what it shows of that kind (today's `atlas` event is one case) |
| `tasks` | task progress | as today | task panel |
| `plugins_info` | a plugin started, stopped or changed its functions | `{project}` | refetches `/actions` |
| `ui.changed` | another session wrote tabs or settings | `{project, keys}` | merges or reloads that UI state |

- `data.changed` replaces today's `db_update {project_id, sequence}`. It carries what changed,
  so the front fetches only that.
- A plugin's writes produce these events when its function returns and the store has caught up
  (note 05 §6.1), in one batch.

## 5. Open questions

- Desktop: the Tauri app runs the server in its own process, or starts it as a child process?
  One process is simpler; a child keeps a server crash from closing the window.
- Authentication for the browser deployment: today's users have an optional password. Is a
  session cookie enough, or is a token per connection needed?
- Several projects open in one session: one socket.io room per project, or the project id in
  every message?
