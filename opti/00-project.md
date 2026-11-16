# 00: Project

Status 2026-11-06: proposal. The Project block of the Rust backend (README): the owner of one
open project. It holds the project's storage handles, its engine, its tasks and its plugin
processes, makes every write of the backend, and sends the changes out. Above it, a small
install-level manager opens and closes projects. Sources: today's `Project`
(`panoptic_back/panoptic/core/project/project.py`), `Panoptic`
(`core/panoptic/panoptic.py`), `TaskManager` (`core/task/task_manager.py`) and `DbWatcher`
(`core/watcher/db_watcher.py`).

## 1. Role

The other blocks each do one thing: Storage is files and rules (notes 01–04), the engine
computes over a store version (notes 05–07), the web server translates between the outside and
the backend (note 08), plugins compute in their own process (note 09). The Project is what ties
them for one project:

1. **Lifecycle.** Opens the project, keeps it running while someone uses it, closes it.
2. **Writes.** Holds the domain operations. Every write the backend makes to a project file
   goes through it.
3. **Changes.** Follows `data.db` after any write, whoever made it, so the store catches up,
   and turns every change into events for the clients.
4. **Work.** Runs long jobs as tasks, and runs plugin functions and hooks as tasks.

The web server never writes a file and never starts a thread of work itself: a route calls the
Project, or reads the engine's published results (note 06 §4.1).

## 2. What it owns

Owned means created by it, kept alive by it, and closed with it.

| part | what it is | specified in |
|---|---|---|
| storage handles | one write connection per file (`data.db`, `media.db`, `project.db`), each used by one writer thread; a read pool per file | note 02 §5 |
| column store | the published versions of the project's data | note 05 |
| engine | the collection registry and the scheduler, over the column store | notes 06 §4.1, 07 §7 |
| change follower | brings the store up to date after each write (§5) | note 05 §6.1 for what a catch-up does |
| event channel | the project's outgoing events, which the web server forwards to sessions (§6) | note 08 §4 for the events |
| task list | queued, running and finished tasks (§7) | |
| plugin links | one per plugin process: the pipe, the calls in flight, the plugin's description (§8) | note 09 |
| folder lock | the proof that this backend is the only one with the project open (§3.2) | |

```rust
pub struct Project {
    id: ProjectId,
    folder: PathBuf,
    lock: FolderLock,                      // §3.2
    storage: StorageHandles,               // writers + read pools, note 02 §5
    store: Arc<ColumnStore>,               // note 05
    engine: Engine,                        // note 06 §4.1
    follower: ChangeFollower,              // §5
    events: broadcast::Sender<ProjectEvent>, // §6
    tasks: TaskList,                       // §7
    plugins: PluginLinks,                  // §8
    sessions: AtomicU32,                   // sessions with the project open, §4.3
}
```

## 3. The project manager

### 3.1 Role

One per backend. It owns `panoptic.db` (note 02 §4) and the map of open projects:

```rust
pub struct ProjectManager {
    db: PanopticDb,                         // users, known projects, installed plugins
    open: Mutex<FxHashMap<ProjectId, Arc<Project>>>,
    opening: Mutex<FxHashMap<ProjectId, Shared<Result<Arc<Project>>>>>,
}
```

- It serves the install routes of note 08 §2 (`/projects`, `/create_project`, `/users`,
  `/plugins`, …). They touch `panoptic.db` and no project.
- `open(id)` returns the open project, or opens it. Two sessions asking at once wait on the
  same opening, so a project is opened once per backend (note 08 §3.1).
- Several projects can be open at once, each with its own Project. They share the process-wide
  pools (§9) and nothing else.

### 3.2 One backend per project folder

A project folder is opened by one backend at a time. The Project takes an exclusive OS lock
(`flock` / `LockFileEx`) on a `backend.lock` file in the folder when it opens, and releases it
when it closes. A second backend that finds the lock taken refuses to open the project, and
says which host and process hold it (written in the file).

Why: the open deletes `data.db`'s tombstones (§4.1), and the backend deletes them again while it
runs, below its store's sequence (note 01 §2). A second backend on the same folder would delete
tombstones the first one has not read yet, and the first store would keep deleted rows.

Plugins and scripts are not backends: they open the files without this lock, as note 02 §5
says. An OS lock is released when the process dies, so a crash leaves no stale lock.

### 3.3 Checks before opening

As today's `Panoptic.load_project`:

- the project is registered in `panoptic.db`;
- `project.db`'s `project_config.id` matches the registered id. A copied or moved folder fails
  this check and has to be imported again;
- the files are in the format of notes 01 and 02. An older format is refused (migration is out
  of scope for now).

## 4. Lifecycle

### 4.1 Opening

In order. The project is visible to sessions only after step 5.

1. **Lock** the folder (§3.2).
2. **Open the files**: create them if missing (a new project), set WAL and `busy_timeout`,
   open the writers and the read pools (note 02 §5).
3. **Seed** what a project always has: the default image types (`media.db`), the system
   properties and the local file source (`data.db`), each in one transaction. Seeding an
   existing project writes nothing.
4. **Load the store**: identity and schema at sequence `S`, then delete the tombstones
   (note 05 §5.1). No property column is loaded yet.
5. **Start** the change follower (§5), the engine and the task list. Register the project in
   the manager.
6. **Queue the start tasks**: the thumbnail backfill when `project_flags.thumbnails_dirty` is
   set (note 02 §3), and the `on_project_open` hooks (§8.2).

No plugin process starts at open: a plugin starts on its first call (note 09 §2).

### 4.2 Closing

1. Unregister the project, so no new session or route reaches it.
2. Stop the tasks: queued tasks are dropped, running ones are cancelled (§7.3) and given a
   grace time to end.
3. Stop the plugin processes (`cancel` to calls in flight, then end the process).
4. Stop the follower, drop the engine and the store.
5. Close the connections, after a WAL checkpoint (`wal_checkpoint(TRUNCATE)`), so the folder is
   three plain files when the backend is gone.
6. Release the lock.

### 4.3 Who keeps it open

- A session keeps a project open from `load_project` to `close_project` or its last socket's
  end (note 08 §3.1). The Project counts its sessions.
- When the count drops to zero, the project stays open for a grace period (60 s, as for
  collections in note 07 §7.7), so a page reload finds it warm. A running task also keeps it
  open: the close waits until the task list is idle, or the user stops the tasks.
- `/close` and the backend's shutdown close it at once.

## 5. Writes and the change follower

### 5.1 Domain operations

The operations that change a project, all on the Project:

| operation | writes | note |
|---|---|---|
| commit (upsert, delete), values, tag merge | `data.db`: one commit | 01 §7 |
| undo, redo, set commit active, compact | `data.db` | 01 §7 rule 7; 04 §6.4 |
| schema: properties, tags, folders, file sources, id allocation | `data.db` | 01 §3 |
| import of a source, rescan, failed-read check | `data.db`: observed state and commits; then `media.db` (thumbnails) as a task | 04 §3, §6.3 |
| report options: match, relink, remove, values follow | `data.db`: one commit each | 04 §5.2 |
| purge | `data.db`, then `media.db` cleanup, then `on_purge` hooks | 04 §6.6 |
| media: image types, vector types, atlas, maps | `media.db` | 02 §2 |
| UI state: tabs, user defaults, settings | `project.db` | 02 §3 |

Each operation runs its transaction on the file's writer thread, by the rules of note 01 §7,
and returns the sequence it wrote (for `data.db`) once it has committed. The web server awaits
that, never the transaction itself.

```rust
impl Project {
    pub async fn commit(&self, author: UserId, c: DataCommit) -> Result<Sequence>;
    pub async fn undo(&self, author: UserId) -> Result<Option<(CommitId, Sequence)>>;
    pub async fn wait_for(&self, seq: Sequence);   // the store has a version at seq or later
    pub fn start_task(&self, t: TaskSpec) -> TaskId;
    pub fn call_plugin(&self, call: PluginCall) -> TaskId;
    pub fn subscribe(&self) -> broadcast::Receiver<ProjectEvent>;
}
```

- A write route replies with the sequence. The front waits for the `data.changed` event at that
  sequence before it drops its optimistic overlay (note 08 §2).
- A route that writes then reads awaits `wait_for(seq)` first (note 05 §6.1).

### 5.2 The change follower

The follower is the Project's part of note 05 §6.1: it decides *when* the store catches up;
note 05 says *what* a catch-up does.

- **Triggers.** The `data.db` writer after each transaction, undo or redo; the end of a plugin
  call (`result`, error or crash) and of a task that let a plugin write; a poll of
  `sequence.id` every second for anything else (a script, a plugin outside a call).
- **At most one catch-up at a time.** A trigger during a catch-up schedules exactly one more.
  A burst of writes costs a few catch-ups, not one per write.
- **Reload.** A `sequence.id` below the store's sequence means the file was replaced: the
  follower asks the store for a full reload (note 05 §6.5).
- **Tombstone cleanup.** At a quiet moment, it deletes the tombstones below the store's
  sequence (note 01 §2), as one short write on the `data.db` writer.

The follower runs on a blocking thread, as every SQLite read does (note 02 §5).

## 6. Events

Every change leaves the Project as one `ProjectEvent` on its broadcast channel. The web server
subscribes once per project, and forwards each event to the sessions that have the project
open, as the socket.io events of note 08 §4.

| source | event |
|---|---|
| a new store version (from its change record, note 05 §7.1: `schema`, and history flags) | `data.changed` |
| observed state written by a scan or a failed read | `scans.changed` |
| a `media.db` write (by an operation, a task, or a plugin call that declared media writes) | `media.changed` |
| a task's progress or state | `tasks` |
| a plugin process started, stopped, or changed its description | `plugins_info` |
| a `project.db` UI write, with the session that made it | `ui.changed` (not sent back to that session) |

- The engine gets the store's change record directly, not through this channel (note 05 §7.2):
  views get their `result` / `values` / `stale` pushes from the engine (note 07 §6).
- A plugin call's writes produce their events once, in one batch, after the catch-up that
  follows the call (note 09 §3).
- Task progress is throttled to a few events per second per task.

## 7. Tasks

### 7.1 What runs as a task

Any work that can take more than a moment, or that runs in a plugin: imports, rescans,
thumbnail generation and backfill, atlas generation, purges with their media cleanup, CSV
imports and exports, plugin functions and hooks.

### 7.2 Queues

Today's `TaskManager` runs one task at a time, with two priorities. Here a task names the
**lane** it needs, and each lane runs one task at a time:

| lane | tasks | why one at a time |
|---|---|---|
| `disk` | imports, rescans, thumbnails, atlas, purge, exports | they read the image files and use every core; two at once only slow both |
| `plugin:<name>` | that plugin's calls and hooks | a plugin process takes one call at a time (note 09 §3), unless it says it is reentrant |

Tasks in different lanes run at the same time: a CLIP plugin computing vectors does not wait
for a thumbnail pass. Inside a lane, a high-priority queue (a user action) goes before the
normal one (start tasks, hooks), as today.

### 7.3 Running, progress, cancel

- A task runs on its own blocking thread (Rust) or in its plugin process (Python), never on the
  async runtime.
- **Progress** as today's `TaskState`: step, done / total, failed count, workers. Pushed in
  `tasks` events (§6). A plugin's `progress` messages fill it (note 09 §3).
- **Cancel** is cooperative. A Rust task checks its `CancelToken` between batches; a plugin
  task is sent `cancel` and the plugin API raises `TaskCancelled` at its next call (note 09 §3).
  If a plugin task does not end within a grace time (3 s), the Project kills the plugin process:
  the task ends as cancelled, and the process restarts on its next call. A Rust task cannot be
  killed, so every Rust task checks its token at least once per batch.
- Work already committed by a cancelled task stays, as one undoable group of commits (note 01
  §7 rule 2).
- **Finished** tasks stay in the list until dismissed (`/task/dismiss`,
  `/tasks/dismiss_finished`, note 08 §2).

## 8. Plugins

### 8.1 Processes and calls

The Project owns one link per plugin used in this project (not excluded by
`projects.excluded_plugins`, note 02 §4). A link starts the plugin's process on its first call,
keeps it while the project is open, and stops it on close, after an idle time, or on
`/plugin/stop` (note 09 §2). A plugin process serves one project: two open projects using the
same plugin run two processes.

Every call is a task in the plugin's lane (§7.2). At its end the Project triggers the follower
(§5.2), so the plugin's writes reach the store as one version.

### 8.2 Hooks

The Project dispatches the hooks of note 09 §4: it queues one normal-priority task per plugin
that declares the hook, after the event:

| hook | queued by |
|---|---|
| `on_import` | the end of an import or rescan that added images |
| `on_purge` | the end of a purge, after its media cleanup |
| `on_project_open` | the open (§4.1 step 6) |

### 8.3 Descriptions without a process

`/actions` and hook dispatch need each plugin's functions and hooks before any call, but the
process starts on its first call. The Project reads the description from a cache: the plugin
writes it when its process starts, keyed by the plugin's installed version, in `panoptic.db`.
A plugin installed or updated starts once at install to fill it (note 09 §2). A started process
whose description changed updates the cache and pushes `plugins_info`.

## 9. Threads

Process-wide, shared by every open Project:

- the **async runtime** (tokio): HTTP, socket.io, plugin pipes, awaiting results. It never
  computes and never touches SQLite;
- the **compute pool** (rayon): every collection job of every project (note 07 §7.3);
- the **blocking pool**: SQLite reads, the follower, Rust tasks.

Per Project: one writer thread per file. That is three threads per open project, idle between
writes.

## 10. Open questions

- The grace before closing an unused project: 60 s like collections, or longer for a desktop
  app where the window may be hidden a long time?
- Should the poll in §5.2 use SQLite's `data_version` pragma instead of reading
  `sequence.id`? It costs nothing, but it only works on a connection kept open.
- Can a `disk` task and a plugin call that writes `data.db` heavily run at once without the
  writers waiting too long on each other? Measure with the batch size of note 09 §5.3.
- Should a plugin process be shared by several open projects to save memory (one CLIP model
  loaded once)? The call context already carries the project folder (note 09 §3).
