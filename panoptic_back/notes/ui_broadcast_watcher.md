# UI broadcast — poll-based async loop

---

## Concept

Instead of the `Project` class pushing updates to connected clients directly, a separate async `DbWatcher` task polls the data DB on a fixed interval. When new commits are found since the last known sequence, it reads the delta and broadcasts it to connected Socket.IO clients.

This decouples the project's write path entirely from the UI notification path. Any process that writes to the DB — the app, a background task, or an external script — is automatically picked up. The project class has zero knowledge of connected users.

---

## Why polling instead of file watching

A 100ms poll interval is fast enough to feel real-time in a data annotation UI (games target 16ms and feel instant). A file watcher offers sub-10ms latency but introduces significant complexity:

- `data.db-wal` may not exist yet on a fresh DB
- inotify doesn't work reliably on Docker over NFS/CIFS/overlayfs
- macOS FSEvents coalesces events with up to ~1s delay — slower than polling
- Checkpoint events delete and recreate the WAL file, causing spurious watch errors
- Platform differences require different code paths or heavy abstraction (watchfiles)

Polling sidesteps all of this. The sequence-based read is a pure memory query (SQLite page cache) — no disk I/O, no SSD wear, negligible CPU, negligible battery impact. 10 queries/second on a cached 1-row table costs less than a log statement.

---

## Architecture

```
[Project write thread]       [External script]
        │                           │
        ▼                           ▼
  data_db.sqlite  ◄────────────────┘
        │
        │  (asyncio.sleep(0.1) loop)
        ▼
  DbWatcher (async loop)
   ├─ tracks last_seen_sequence
   ├─ every 100ms: DataReader.get_commits_since(last_seen_sequence)
   ├─ reads changed entities
   └─ broadcasts delta to Socket.IO server
        │
        ▼
  Panoptic Socket.IO layer
   ├─ manages user sessions + auth
   ├─ routes events to the right users / projects
   └─ sends delta to connected clients
```

---

## The sequence as cursor

Every commit written by `DataWriter` atomically increments the `sequence` table. `EntitySchema` stores the sequence number alongside every row in the main table. `get_since(sequence)` fetches everything newer.

The watcher maintains a single integer `last_seen_sequence` per watched DB:

```python
async def _check(self):
    commits = self._reader.get_commits_since(self._last_seq)
    if not commits:
        return
    self._last_seq = max(c.sequence for c in commits)
    for commit in commits:
        await self._broadcast({'project_id': self._project_id, 'commit_id': commit.id})
```

This is robust regardless of timing:
- Multiple rapid writes are all caught in a single read (no commits missed)
- Race conditions are impossible — WAL readers always see fully committed state

---

## Broadcast strategy

The watcher never sends entity data through Socket.IO. It only sends a lightweight signal:

```json
{ "project_id": "...", "commit_id": 42 }
```

The client reacts by calling the relevant REST endpoints to re-fetch what it needs. This means:

- The async loop never touches entity data — no serialization risk, no size threshold logic
- The client controls what it re-fetches based on what it currently displays
- REST endpoints are already implemented and handle all the heavy lifting
- The extra round trip is imperceptible to the user, who just committed something and is already waiting for the UI to update

Sending full deltas through Socket.IO would only be worth the complexity in a collaborative real-time editor with many users making rapid concurrent edits. That is not this use case.

---

## Auth and user management

User sessions, passwords, and permissions live in the `Panoptic`-level Socket.IO layer, completely outside `Project` and `DbWatcher`. The watcher only produces project-level events. The Socket.IO layer decides:

- Which connected users are subscribed to this project
- Which users have read permission
- Which users get which subset of the delta (future: per-user visibility)

`DbWatcher` has no concept of users. It emits events to a channel; the Socket.IO layer consumes and routes them.

---

## External script support

An external script that writes to the DB using `DataWriter` will:

1. Write commits and increment the sequence
2. Be picked up by the watcher at the next 100ms tick
3. Cause a broadcast to all connected clients — with no app involvement

This works correctly as long as the script uses `ProjectDB` for ID allocation (commits, instances, files, etc.). If it bypasses `ProjectDB` and picks IDs manually, ID collisions are possible.

---

## Design notes

### 1. ID allocation from external scripts
`ProjectDB` is the single authority for allocating IDs. External scripts that bypass it risk ID collisions.

**Resolved:** External scripts will use a future `GlobalProjectDB` class that links all three DBs together and handles ID allocation correctly, without requiring the full project runtime. External scripts should not interact with the DBs directly.

### 2. Cold-start state for new connections
The watcher only broadcasts deltas. A client connecting for the first time needs the full current state.

**Resolved:** Handled by a `get_data` route — same pattern as the current implementation, which does an optimised streamed load of all project data on first connect.

### 3. Multiple projects
Each open project gets its own `DbWatcher` instance with its own poll loop. The Panoptic layer manages the collection. Projects are fully independent. Not a problem.

---

## Watcher implementation

```python
class DbWatcher:
    def __init__(self, db_path: Path, broadcast_fn: Callable):
        self._db_path = db_path
        self._broadcast = broadcast_fn
        self._last_seq = 0
        self._reader = DataReader(db_path)

    async def run(self):
        self._last_seq = self._reader.get_max_sequence()
        while True:
            await asyncio.sleep(0.1)
            await self._check()

    async def _check(self):
        commits = self._reader.get_commits_since(self._last_seq)
        if not commits:
            return
        new_seq = max(c.sequence for c in commits)
        delta = self._build_delta(commits)
        self._last_seq = new_seq
        await self._broadcast(delta)
```

---

## Relation to the async loop

`DbWatcher` runs inside the Socket.IO server's asyncio event loop — it is async and only does fast cached DB reads. It never calls into the `Project` class. `Project` runs in its own sync threads and never calls into the watcher. The two halves communicate only through the DB file on disk.

---

## Task events — direct callback, not polling

`DbWatcher` handles data changes from `data.db`. Task state is different: tasks always run
inside the app process, never in an external script. There is no reason to round-trip through
the database.

`TaskManager` accepts an `on_update` callback at construction time. `Panoptic2` wires this
to the Socket.IO broadcast when it loads the project:

```python
def load_project(self, uid: str) -> Project2:
    ...
    def broadcast_task_update(states: list[TaskState]):
        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(
                self._sio.emit('task_update', {
                    'project_id': uid,
                    'tasks': [s.model_dump() for s in states]
                })
            )
        )

    project = Project2(project_folder, on_task_update=broadcast_task_update)
    ...
```

`TaskManager._on_progress()` calls `on_update(self.get_states())` — that's all. No DB write,
no poll delay. Task progress reaches the client in the same 100ms window as the next
Socket.IO flush, or faster.

`Project2` stores nothing about users. The task update is broadcast to all subscribers of
that project — the Socket.IO layer filters by subscription.

### Summary: two separate channels

| Event type | Mechanism | Why |
|------------|-----------|-----|
| New data commit | `DbWatcher` polls `data.db` every 100ms | Must support external scripts |
| Task progress | Direct callback → `call_soon_threadsafe` | Always in-process, no DB roundtrip |

---

## Integration with FastAPI + Socket.IO — what the current code tells us

The current `main.py` creates:
1. `Panoptic` — owns project/plugin state
2. `PanopticServer(panoptic)` — owns `sio = socketio.AsyncServer(...)` and all Socket.IO events
3. FastAPI app — mounts `sio` at `/socket.io`, includes routers

`PanopticServer` is the async-world bridge. It wires project events to Socket.IO: when
`load_project` is called it registers a `broadcast_sync_event` callback on
`project.on.sync`. Every project event (commit, task, etc.) flows: `on.sync.emit` →
`broadcast_sync_event` → `sio.emit()`.

The start script owns FastAPI and uvicorn. Panoptic2 does NOT own the event loop.

**In the new design**, the equivalent split is:

```
start_script.py
 ├─ panoptic = Panoptic2(db_path)
 ├─ panoptic.start()                        ← sync, no event loop needed
 ├─ server = PanopticServer2(panoptic, sio)  ← owns sio, wires callbacks
 ├─ app = FastAPI(lifespan=...)
 │   └─ on_startup: panoptic.set_loop(asyncio.get_running_loop())
 └─ uvicorn.run(app)                         ← owns the event loop
```

`PanopticServer2` provides `broadcast_fn` to `Panoptic2`, which passes it to each
`DbWatcher`. `Panoptic2` never imports or references `socketio` directly.

---

## How DbWatcher gets scheduled into the event loop

When `load_project(uid)` is called from a FastAPI `def` route (running in a thread pool),
`Panoptic2` must schedule the watcher coroutine into the running event loop:

```python
# Inside Panoptic2.load_project():
watcher = DbWatcher(data_db_path, broadcast_fn=self._make_broadcast(uid))
self._watchers[uid] = watcher
self._loop.call_soon_threadsafe(
    lambda: asyncio.ensure_future(watcher.run())
)
```

`self._loop` is stored by `Panoptic2.set_loop(loop)`, called from FastAPI's startup event.
`asyncio.ensure_future` schedules the coroutine as a background task in the event loop.
`call_soon_threadsafe` is the standard bridge from a sync thread back into the event loop.

Similarly, `close_project` cancels the watcher:

```python
# Inside Panoptic2.close_project():
watcher = self._watchers.pop(uid, None)
if watcher:
    self._loop.call_soon_threadsafe(watcher.stop)
```

`DbWatcher.stop()` sets a flag that breaks the `while True` loop on the next iteration
(or uses `asyncio.Task.cancel()` if we store the task handle — see open questions).

---

## Task update callback bridge (sync → async)

`TaskManager.on_update` is a sync callable (tasks run in threads). `sio.emit()` is async.
The bridge is `call_soon_threadsafe`:

```python
def _make_task_callback(uid: str, loop, sio) -> Callable:
    def on_update(states: list[TaskState]):
        async def _emit():
            await sio.emit('tasks', {'project_id': uid, 'tasks': [...]})
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(_emit()))
    return on_update
```

`PanopticServer2` builds this callback and passes it into `Project2(on_update=...)`.
`Panoptic2` never references `sio` — `PanopticServer2` owns that concern.

---

## Resolved design decisions

### D1 — DbWatcher stop: flag-based

`DbWatcher.stop()` is sync and sets `self._running = False`. The `run()` loop checks the flag
on each iteration and exits cleanly. Up to 100ms delay — unnoticeable. No asyncio primitives
stored in `Panoptic2`.

```python
async def run(self):
    self._running = True
    self._last_seq = self._reader.get_max_sequence()
    while self._running:
        await asyncio.sleep(0.1)
        await self._check()

def stop(self):
    self._running = False
```

---

### D2 — `broadcast_fn` is async

`DbWatcher` `await`s the callback directly — it already runs in the event loop so no
`call_soon_threadsafe` needed inside the watcher itself:

```python
async def _check(self):
    commits = self._reader.get_commits_since(self._last_seq)
    if not commits:
        return
    self._last_seq = max(c.id for c in commits)
    await self._broadcast_fn(self._project_uid, [c.id for c in commits])
```

`broadcast_fn: Callable[[str, list[int]], Coroutine]` — takes the project uid and a list
of new commit IDs. `DbWatcher` is only ever created and run inside the async layer; it is
never called from an external script.

---

### D3 — `Panoptic2` is fully sync, `PanopticServer2` owns all async wiring

`Panoptic2` has zero asyncio imports. It never touches the event loop.
`Panoptic2.load_project(uid)` returns the `Project2` instance and exposes `data_db_path`.
`PanopticServer2` creates the `DbWatcher`, schedules it into the event loop, and manages
the task-update callback bridge.

This means `Panoptic2` can be used from a script with no event loop at all — useful for
batch processing and testing.

```
script.py                      server.py (start script)
  panoptic = Panoptic2(...)      panoptic = Panoptic2(...)
  panoptic.start()               panoptic.start()
  project = panoptic             server = PanopticServer2(panoptic, sio)
              .load_project(uid)  uvicorn.run(app)   ← owns event loop
  project.get_instances()
  # no sio, no loop needed
```

---

### D4 — `PanopticServer2` is a class in `panoptic2/`

Responsibilities mirror the current `PanopticServer`:
- Owns `sio = socketio.AsyncServer(...)`
- Manages connection state: `sid → connection_id`, `connection_id → project_uid`
- Creates `DbWatcher` per loaded project and schedules/cancels it
- Builds the `broadcast_fn` and task-update callbacks
- Handles Socket.IO events: `connect`, `disconnect`, `load_project`, etc.
- Routes broadcasts to the correct SIDs based on which project each connection is subscribed to

`PanopticServer2` wraps `Panoptic2` — it calls `panoptic.load_project()` then wires the async
layer on top. `Panoptic2` is never aware of `sio` or client connections.

---

## Updated architecture

```
start_script.py
 ├─ panoptic = Panoptic2(panoptic_db_path)
 ├─ panoptic.start()                              ← sync, reads PanopticDB config
 ├─ sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
 ├─ server = PanopticServer2(panoptic, sio)        ← owns sio + async wiring
 ├─ app = FastAPI(lifespan=lifespan)
 │   └─ on_startup: server.on_startup()            ← stores running loop
 └─ uvicorn.run(socketio.ASGIApp(sio, app))

PanopticServer2.on_startup():
    self._loop = asyncio.get_running_loop()

PanopticServer2 (on load_project from a Socket.IO or HTTP event):
    project = panoptic.load_project(uid)           ← sync
    watcher = DbWatcher(project.data_db_path,
                        project_uid=uid,
                        broadcast_fn=self._broadcast_commits)
    asyncio.ensure_future(watcher.run())           ← runs in sio's event loop
    task_cb = self._make_task_callback(uid)
    project.task_manager._on_update = task_cb

async def _broadcast_commits(uid, commit_ids):
    sids = self._get_project_sids(uid)
    await sio.emit('commits', {'project_id': uid, 'commit_ids': commit_ids}, to=sids)

def _make_task_callback(uid):
    def on_update(states):
        async def _emit():
            sids = self._get_project_sids(uid)
            await sio.emit('tasks', {'project_id': uid, 'tasks': [...]}, to=sids)
        asyncio.ensure_future(_emit())   ← already in event loop (called via call_soon_threadsafe)
    return on_update
```

Note: `_make_task_callback` returns a sync callable. Task threads call it via
`call_soon_threadsafe` so by the time `on_update` executes it is back in the event loop,
making `asyncio.ensure_future` safe.