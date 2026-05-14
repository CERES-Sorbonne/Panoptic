# `Project2` architecture — design notes

---

## Problems with the current design

1. **Async infection.** The entire stack is `async def` all the way down. One badly-written
   plugin that blocks (sleep, CPU loop, synchronous HTTP) stalls the event loop for every
   connected client.
2. **`sha1_to_files` in-memory index.** Rebuilt from the full DB on every `start()`. For
   1M+ rows this is a multi-second blocking scan at startup. It also drifts silently if
   files are deleted externally.
3. **No thread safety.** The `Project` class is used as a shared singleton from async route
   handlers. The `asyncio.Lock`-based `DB_LOCK` serializes writes but only within the async
   event loop — meaningless once any code moves off it.
4. **Heavy transforms in the event loop.** Even a Python `list()` over 1M msgspec structs
   is hundreds of milliseconds of GIL-holding work. Doing this inside an `async def` blocks
   all other coroutines.
5. **`close()` swallows all errors.** Silent teardown makes resource leaks invisible.

---

## Core constraints for the new design

- **No async anywhere in `Project2`.** All methods are sync. FastAPI bridges the gap.
- **No persistent single write connection.** SQLite's own `BEGIN IMMEDIATE` + 30s timeout
  serializes concurrent writers. The application does not need an extra lock.
- **Connection lifetime matches the work.** Route handlers open a `DataWriter`, write, and
  close it. Tasks open a `DataWriter` at task start and close it when the task finishes.
  Process tasks open their own connection inside the subprocess.
- **Any thread can read.** Each call that needs to read opens its own `DataReader` (read-only
  WAL connection). Unlimited concurrent readers, no locking needed.
- **No in-memory indexes** that duplicate DB state. The DB has proper indexes; a point-query
  is fast enough.
- **FastAPI integration is a thin shell.** Routes are plain `def`, so FastAPI automatically
  runs them in its thread pool. `Project2` never knows about asyncio.

---

## Why the solo write thread was dropped

The previous design proposed a `ThreadPoolExecutor(max_workers=1)` to serialize writes at
the application level. This was a solution for async concurrency — two coroutines on the same
thread interleaving inside a write. In a thread model that problem doesn't arise.

What remains is ordinary multi-thread write concurrency, and SQLite handles that natively:
`BEGIN IMMEDIATE` blocks the second writer until the first commits. The 30s timeout in
`SQLiteWriter` is more than enough for any realistic write, including bulk imports.

**The solo writer pattern adds no safety, and blocks normal writes during long tasks.**
If an import runs on the write thread, every property edit from the UI waits for the import
to finish. That is unacceptable.

---

## Folder layout

```
<project_folder>/
  project.db      ← ProjectDB  (IDs, config, task state)
  data.db         ← DataWriter / DataReader  (all content: instances, files, values…)
  media.db        ← MediaDB   (image miniatures, vectors, atlas)
```

These filenames are constants, not configurable. Every component that needs them derives the
paths from a single `project_folder: Path` argument.

---

## Connection lifetime rules

| Caller | DataWriter | DataReader | ProjectDB |
|--------|-----------|-----------|-----------|
| FastAPI route (small write) | open → write → close | open → read → close | open → allocate IDs → close |
| FastAPI route (read-only) | — | open → read → close | — |
| Thread task (long write) | open at `task.start()`, close at task end | open per read call | open at `task.start()`, close at task end |
| Process task (CPU-heavy) | open inside subprocess | open inside subprocess | open inside subprocess |

All connections to the same file are safe to open concurrently. SQLite serializes writes.
The only rule: **never share a connection across threads or processes.**

---

## `Project2` structure

```python
class Project2:
    def __init__(self, project_folder: Path):
        self.folder         = project_folder
        self.project_db_path = project_folder / 'project.db'
        self.data_db_path    = project_folder / 'data.db'
        self.media_db_path   = project_folder / 'media.db'
        self.task_manager   = TaskManager(
            project_db_path=str(self.project_db_path),
            data_db_path=str(self.data_db_path),
        )
        self.config: ProjectConfig | None = None

    def start(self):
        # Read config once at startup — ProjectDB is opened and closed here
        with ProjectDB(self.project_db_path) as db:
            db.start()
            self.config = db.config

    def close(self):
        self.task_manager.close()
```

### Read methods — one DataReader per call

```python
def get_instances(self, **filters) -> list[Instance]:
    with DataReader(self.data_db_path) as r:
        return r.get_instances(**filters)

def get_commits(self, **filters) -> list[Commit]:
    with DataReader(self.data_db_path) as r:
        return r.get_commits(**filters)
```

`DataReader` already implements `__enter__` / `__exit__` for use as a context manager.

### Write methods — one DataWriter per call (small, fast commits)

```python
def apply_commit(self, source: str, commit: UpsertCommit) -> Commit:
    with ProjectDB(self.project_db_path) as project_db:
        project_db.start()
        builder = CommitBuilder(project_db)
        # caller already filled the builder, or we build here
    with DataWriter(self.data_db_path) as writer:
        writer.start()
        return writer.apply_upsert_commit(source, commit)
```

For UI-paced writes (one at a time, triggered by user action) this open/start/write/close
cycle takes ~1ms. Acceptable. If profiling shows it is a bottleneck, a persistent
`DataWriter` can be added as an option later — but optimize last.

### Long operations — TaskManager

```python
def import_folder(self, paths: list[str]) -> str:
    task = ImportFolderTask(
        project_db_path=str(self.project_db_path),
        data_db_path=str(self.data_db_path),
        paths=paths,
    )
    self.task_manager.add_task(task, mode=ExecutorMode.THREAD)
    return task.id

def get_task_states(self) -> list[TaskState]:
    return self.task_manager.get_states()
```

---

## FastAPI bridge

FastAPI runs plain `def` route handlers in its own thread pool automatically. No wrappers
needed:

```python
@router.post("/commit")
def apply_commit(body: CommitRequest, project: Project2 = Depends(get_project)):
    return project.apply_commit('ui', body.commit)

@router.get("/instances")
def get_instances(project: Project2 = Depends(get_project)):
    return project.get_instances()

@router.post("/import")
def import_folder(body: ImportRequest, project: Project2 = Depends(get_project)):
    task_id = project.import_folder(body.paths)
    return {"task_id": task_id}
```

Multiple reads run truly in parallel. Writes contend at the SQLite level and queue naturally.
The event loop is never blocked.

---

## Replacing `sha1_to_files`

The current index is used to skip re-importing a file whose sha1 is already known.
The equivalent DB query:

```sql
-- index created once in the schema:
CREATE INDEX IF NOT EXISTS idx_files_sha1 ON files(sha1);

-- query at import time:
SELECT sha1 FROM files WHERE sha1 IN (?, ?, ?, ...)
```

On a 1M-row table with this index, a batch of 900 sha1s resolves in ~1ms. Rebuilding the
in-memory dict took seconds. The DB query is always fresh, costs nothing at startup, and
never drifts.

---

## Undo / redo

The backend has `DataWriter.set_commit_active(commit_id, active)` which toggles a commit on
or off and re-computes the current state of all affected rows.

**The undo stack lives in the UI.** The client tracks which commit IDs have been applied and
calls `set_commit_active` to reverse them. The backend has no undo queue. This removes all
state management from `Project2` and makes undo transparent to the backend.

---

## Task state visibility

`TaskManager` accepts an `on_update` callback. `Panoptic2` wires this to a Socket.IO
broadcast when it loads the project. Whenever any task calls `_notify()`, the callback fires
on the calling thread and schedules a Socket.IO emit via `loop.call_soon_threadsafe`.

This is a direct in-process connection — no DB roundtrip, no poll delay. Tasks always run
inside the app, so there is no external-script scenario that would require polling.

Data changes (`data.db` commits) still go through `DbWatcher` polling because external
scripts can write there. Task state does not need that indirection.

See `task_manager_rewrite.md` and `ui_broadcast_watcher.md` for the full design.

---

## Thread safety analysis

| Component | Thread safety | Notes |
|-----------|--------------|-------|
| `DataReader` | Safe — one per call | Read-only WAL, no shared state |
| `DataWriter` | Safe — one per task/request | `BEGIN IMMEDIATE` prevents DB corruption; open/close per use |
| `ProjectDB` | Safe — one per task/request | Same pattern as DataWriter |
| `TaskManager` | Needs `threading.Lock` on task dict | Submissions come from multiple threads |
| `Project2` public API | Safe | All state is either stateless reads or in the DB |

No application-level write lock is needed. SQLite is the lock.

---

## Data flow for a typical commit

```
HTTP POST /commit
    │
    ▼  (FastAPI thread pool — plain def route)
project.apply_commit('ui', commit)
    ├─ ProjectDB(project.db)  → allocate IDs   [open → use → close, ~0.5ms]
    └─ DataWriter(data.db)    → write commit    [open → use → close, ~1ms]
    │
    ▼  (FastAPI thread returns result)
JSON response to client
```

---

## Data flow for a long import

```
HTTP POST /import
    │
    ▼  (FastAPI thread pool)
project.import_folder(paths)
    └─ task_manager.add_task(ImportFolderTask(...), mode=THREAD)
    return {"task_id": "ImportFolderTask#1"}   ← immediate response
    │
    ▼  (TaskManager thread pool — running concurrently)
ImportFolderTask.start()
    ├─ ProjectDB(project.db)  → open, allocate IDs throughout task
    ├─ DataWriter(data.db)    → open, write commits throughout task
    └─ task._notify() every N files
            └─ ProjectDB.set_task_state(state)   → picked up by DbWatcher → UI signal
```

---

## Plugin execution model

Plugins register new functions on `Project2`. A FastAPI route calls a plugin function; the
function runs either inline (fast, on the FastAPI thread) or submits a task to `TaskManager`
(slow, tracked).

```
FastAPI route
    └─ project.run_plugin_function("my_plugin", "compute_vectors", args)
            └─ plugin.compute_vectors(args)           ← sync, runs on FastAPI thread
                    └─ [if heavy] task_manager.add_task(ComputeVectorsTask(...))
                                  return task_id      ← immediate response
```

Plugins receive `project_db_path` and `data_db_path` as strings so they can open their own
connections (including inside subprocesses). They never hold a persistent connection — same
rule as the rest of the system.

The plugin API surface `Project2` exposes:
- `project_db_path: str` — for ID allocation
- `data_db_path: str` — for reading and writing
- `task_manager: TaskManager` — to submit long work

Plugins do not get a reference to the `Project2` instance itself to avoid tight coupling.


