# Task manager rewrite — sync design

---

## Goals

- Tasks must be **visible to the UI** — progress, running state, errors. No invisible threads.
- Support both **thread** and **process** execution modes per task.
- Plugins will be rewritten sync — no `await plugin.start()` in the future.
- `LoadPluginTask` exists because some plugins are slow to initialize, and we want the rest
  of the UI to be usable while they load. This is a thread task, not a process task.

---

## The solo writer question — resolved

The original idea was: keep one persistent `DataWriter` per project on a dedicated write thread
to serialize all DB writes. This made sense as an application-level lock in an async world
where calling `await` inside a write would release the GIL and let another coroutine try to
write concurrently.

**In the sync thread model, SQLite already serializes writes for you.**

WAL mode + `BEGIN IMMEDIATE` + a 30s timeout means: if two threads both try to write at the
same time, the second one waits. No error, no corruption, no lost data. SQLite is the write
serializer.

**The solo writer pattern adds nothing here. Drop it.**

Instead: **create a `DataWriter` connection for the lifetime of the work that needs it.**

```
Route handler (small, fast)   → open DataWriter at start, write, close at end
Task (long, many commits)     → open DataWriter at task start, close when task finishes
Process task (CPU heavy)      → each process opens its own DataWriter from the db path string
```

This works in all cases including subprocesses, where a shared connection is impossible
anyway. The timeout of 30s is more than generous for UI-paced writes; even long task commits
(bulk inserts of 10k rows) finish in well under a second.

**One consequence:** `ProjectDB` (ID allocation) follows the same pattern. Route handlers
and tasks each open their own `ProjectDB` connection for ID allocation. SQLite serializes the
`BEGIN IMMEDIATE` transactions that allocate IDs.

---

## What changes in the sync rewrite

| Old | New |
|-----|-----|
| `asyncio.Event` | `threading.Event` |
| `asyncio.Queue` | `queue.Queue` |
| `asyncio.create_task()` | `executor.submit()` (thread or process pool) |
| `asyncio.gather(stage1, stage2, stage3)` | `threading.Thread` per stage + `thread.join()` |
| `loop.run_in_executor(pool, fn)` | `ProcessPoolExecutor.submit(fn)` + `concurrent.futures.as_completed()` |
| `asyncio.to_thread(fn)` | just `fn()` — already in a thread |
| `asyncio.sleep(0)` yield | delete — no event loop to starve |
| `await task.wait()` | `task._finished_event.wait()` (blocking) |
| persistent solo writer | `DataWriter(path)` per task / per request |

### `asyncio.to_thread` is a no-op in thread context

Tasks already run in a thread. `asyncio.to_thread(self._scan_folder_thread, folder)` becomes
just `self._scan_folder_thread(folder)`. Delete the wrapper.

### `asyncio.sleep(0)` yields are unnecessary

These exist only to give the event loop a chance to handle network events between chunks.
In the thread model there is no event loop to starve. Delete all of them.

### ProcessPoolExecutor still works without asyncio

```python
# Old (async)
fut = loop.run_in_executor(pool, fn, chunk)
done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

# New (sync)
fut = pool.submit(fn, chunk)
for fut in concurrent.futures.as_completed(pending):
    result = fut.result()
    write_queue.put(result)
```

---

## Task base class (sync)

```python
import threading
import logging
from abc import ABC, abstractmethod
from typing import Callable

class Task(ABC):
    def __init__(self):
        self.key   = type(self).__name__
        self.name  = self.key
        self.id: str | None = None
        self.state = TaskState(id='unregistered', name=self.name, key=self.key)
        self._cancel_event   = threading.Event()
        self._finished_event = threading.Event()
        self._progress_callbacks: list[Callable[[TaskState], None]] = []

    def stop(self):
        self._cancel_event.set()

    def wait(self):
        self._finished_event.wait()

    def _notify(self):
        for cb in self._progress_callbacks:
            try:    cb(self.state)
            except Exception as e: logging.error(f"Progress callback failed: {e}")

    @abstractmethod
    def start(self):
        pass
```

---

## TaskManager design (sync)

One `TaskManager` per loaded project (owned by `Project2`).

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, Future
from collections import defaultdict
import threading

class ExecutorMode:
    THREAD  = 'thread'
    PROCESS = 'process'

class TaskManager:
    def __init__(self, project_db_path: str, data_db_path: str):
        self._project_db_path = project_db_path
        self._data_db_path    = data_db_path
        self._tasks:   dict[str, Task]   = {}
        self._futures: dict[str, Future] = {}
        self._thread_pool   = ThreadPoolExecutor(max_workers=4)
        self._process_pool  = ProcessPoolExecutor(max_workers=4)
        self._counters: defaultdict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def add_task(self, task: Task, mode: str = ExecutorMode.THREAD) -> Task:
        with self._lock:
            task.id = self._generate_id(task)
            task.state.id = task.id
            task.on_progress(self._on_progress)
            self._tasks[task.id] = task

        pool = self._process_pool if mode == ExecutorMode.PROCESS else self._thread_pool
        future = pool.submit(self._run_wrapper, task)
        with self._lock:
            self._futures[task.id] = future
        return task

    def _run_wrapper(self, task: Task):
        try:
            task.start()
        except Exception:
            logging.exception(f"Task {task.id} failed")
            task.state.running = False
            task.state.finished = True
        finally:
            with self._lock:
                self._futures.pop(task.id, None)
            self._on_progress(task.state)

    def stop_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if task:
            task.stop()

    def get_states(self) -> list[TaskState]:
        return [t.state for t in self._tasks.values()]

    def _generate_id(self, task: Task) -> str:
        self._counters[task.key] += 1
        return f"{task.key}#{self._counters[task.key]}"

    def _on_progress(self, state: TaskState):
        # see Progress broadcasting below
        pass

    def close(self):
        for task in self._tasks.values():
            task.stop()
        self._thread_pool.shutdown(wait=True)
        self._process_pool.shutdown(wait=True)
```

---

## Process tasks — special constraints

When a task runs in a subprocess:
1. **The task object must be picklable.** No open file handles, connections, or locks.
   Pass `db_path: str` and open connections inside the subprocess.
2. **A shared `DataWriter` is impossible.** The subprocess opens its own `DataWriter(data_db_path)`.
3. **Progress callbacks cannot cross process boundaries.** `_notify()` won't reach the main process.

Progress from a subprocess must go through the DB (see Progress broadcasting below).

**Process task pattern:**

```python
class MyProcessTask(Task):
    def __init__(self, project_db_path: str, data_db_path: str, ...):
        super().__init__()
        self._project_db_path = project_db_path  # strings are picklable
        self._data_db_path    = data_db_path

    def start(self):
        # This runs inside a subprocess — open fresh connections
        project_db = ProjectDB(self._project_db_path)
        project_db.start()
        writer = DataWriter(self._data_db_path)
        writer.start()
        ...
```

---

## 3-stage pipeline with threads

Keeps the read/compute/write overlap for throughput.

```python
def start(self):
    self.state.running = True
    read_q  = queue.Queue(maxsize=10)
    write_q = queue.Queue(maxsize=10)

    with ProcessPoolExecutor(max_workers=10) as pool:
        t_read    = threading.Thread(target=self._reader_stage,  args=(read_q,),           daemon=True)
        t_compute = threading.Thread(target=self._compute_stage, args=(read_q, write_q, pool), daemon=True)
        t_write   = threading.Thread(target=self._writer_stage,  args=(write_q,),          daemon=True)

        for t in (t_read, t_compute, t_write): t.start()
        for t in (t_read, t_compute, t_write): t.join()

    self.state.running  = False
    self.state.finished = True
    self._finished_event.set()
    self._notify()
```

Reader and writer stages end with `queue.put(None)` sentinel as before. No asyncio needed.

---

## Progress broadcasting

Tasks always run inside the app process. There is no external-script scenario for task state.
A direct callback is therefore the right mechanism — no DB roundtrip, no poll delay.

`TaskManager` accepts an `on_update: Callable[[list[TaskState]], None]` at construction.
`_on_progress()` calls it whenever any task changes state. `Panoptic2` wires it to
`loop.call_soon_threadsafe` so the Socket.IO broadcast fires from the async event loop:

```python
def _on_progress(self, state: TaskState):
    if self._on_update:
        self._on_update(self.get_states())
```

**Process task progress** is the one exception. A subprocess cannot call `_notify()` on
the parent's `TaskManager` directly (different memory spaces). Options:
- Write progress to a small `tasks` table in `project.db` — the main process polls it
  via a lightweight thread that calls `_on_progress` when it detects a change.
- Use `multiprocessing.Queue` for progress messages — more complex, not persistent.

For now, process tasks report progress only on start and finish (the most common need).
Mid-task progress from a subprocess can be added later with the polling approach if needed.

Task states are **in-memory only** (`TaskManager._tasks` dict). They are not persisted to
the DB. A server restart clears them — the client sees an empty task list on reconnect.
If persistence becomes important, a `tasks` table can be added to `project.db` later.

---

## Task chaining

`ImportFolderTask` → `ImportInstanceTask`: just call `task_manager.add_task(next_task)` at
the end of `start()`. Straight function call. No chaining mechanism needed.

---

## Two-lane queue

Tasks execute **one at a time** on a single worker thread. There are two FIFO lanes:
- **High** — checked first, always drains completely before any normal task runs
- **Normal** — runs when the high lane is empty

```python
add_task(task, high_priority=False)   # normal lane
add_task(task, high_priority=True)    # high lane — jumps ahead of all normal tasks
```

A `threading.Condition` wakes the worker whenever either lane receives a task:

```python
class TaskManager:
    def __init__(self, on_update=None):
        self._high_queue   = collections.deque()
        self._normal_queue = collections.deque()
        self._condition    = threading.Condition()
        self._tasks: dict[str, Task] = {}
        self._on_update    = on_update
        self._counters     = defaultdict(int)
        self._worker       = threading.Thread(target=self._worker_loop, daemon=True)
        self._stop         = False
        self._worker.start()

    def add_task(self, task: Task, high_priority: bool = False) -> Task:
        with self._condition:
            task.id = self._generate_id(task)
            task.state.id = task.id
            task.on_progress(self._on_progress)
            self._tasks[task.id] = task
            if high_priority:
                self._high_queue.append(task)
            else:
                self._normal_queue.append(task)
            self._condition.notify()
        self._on_progress(task.state)
        return task

    def _worker_loop(self):
        while True:
            with self._condition:
                while not self._stop and not self._high_queue and not self._normal_queue:
                    self._condition.wait()
                if self._stop:
                    break
                task = self._high_queue.popleft() if self._high_queue else self._normal_queue.popleft()
            self._run_wrapper(task)

    def _run_wrapper(self, task: Task):
        try:
            task.start()
        except Exception:
            logging.exception(f"Task {task.id} failed")
            task.state.running = False
            task.state.finished = True
        finally:
            self._on_progress(task.state)

    def _on_progress(self, state: TaskState):
        if self._on_update:
            self._on_update(self.get_states())

    def stop_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if task:
            task.stop()

    def dismiss_task(self, task_id: str):
        with self._condition:
            self._tasks.pop(task_id, None)
        self._on_progress(None)

    def get_states(self) -> list[TaskState]:
        return [t.state for t in self._tasks.values()]

    def _generate_id(self, task: Task) -> str:
        self._counters[task.key] += 1
        return f"{task.key}#{self._counters[task.key]}"

    def close(self):
        with self._condition:
            self._stop = True
            self._condition.notify()
        for task in list(self._tasks.values()):
            task.stop()
        self._worker.join(timeout=5)
```

The worker holds the lock only while picking the next task, not while running it — so
`add_task` never blocks on a running task.

## Task history / cleanup

Finished tasks stay in `TaskManager._tasks` until the client explicitly dismisses them via
`DELETE /tasks/{task_id}`. The UI always shows what ran and any errors. No auto-pruning.

## Cancellation for process tasks

Thread tasks: `task.stop()` sets `threading.Event`. The task's loop checks
`self._cancel_event.is_set()` between chunks.

Process tasks: cancellation of a pending (not yet started) future works via the queue — the
task simply never starts. Cancellation of a *running* subprocess is not supported in the
initial implementation. `TaskManager.close()` calls `stop()` on all tasks and drains the
queue with sentinels.
