import collections
import ctypes
import logging
import threading
import time
from collections import defaultdict
from typing import Callable

from panoptic.models.models import TaskState
from panoptic.core.task.task import Task, TaskCancelled

PRIORITY_HIGH   = 0
PRIORITY_NORMAL = 10

# Seconds a stopped task gets to exit by itself before TaskCancelled is raised in it.
STOP_GRACE = 3.0
# Seconds an interrupted task gets before its thread is abandoned.
INTERRUPT_GRACE = 3.0


class TaskManager:
    """Runs queued tasks one at a time, each in its own thread.

    Any queued or running task can be stopped. Stopping a running task escalates:
      1. the task's cancel flag is set. Tasks that check `is_cancelled()` exit cleanly.
      2. after STOP_GRACE seconds, TaskCancelled is raised inside the task's thread.
      3. after INTERRUPT_GRACE more seconds, the thread is abandoned: the task is marked
         finished, its state is frozen and the next task starts. The thread keeps running
         until the C call it is blocked in returns (a GPU pass, a lock wait...).
    """

    def __init__(self, on_update: Callable[[list[TaskState]], None] = None,
                 stop_grace: float = STOP_GRACE, interrupt_grace: float = INTERRUPT_GRACE):
        self._high_queue:   collections.deque[Task] = collections.deque()
        self._normal_queue: collections.deque[Task] = collections.deque()
        self._condition = threading.Condition()
        self._tasks:    dict[str, Task] = {}
        self._counters: defaultdict[str, int] = defaultdict(int)
        # State snapshots of abandoned tasks. Their thread may still change the live state.
        self._frozen:   dict[str, TaskState] = {}
        # Task keys with finished work whose on_last() has not run yet
        self._on_last_due: set[str] = set()
        self._on_update = on_update
        self._stop_grace = stop_grace
        self._interrupt_grace = interrupt_grace
        self._stop = False

        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="TaskManager-worker")
        self._worker.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_task(self, task: Task, high_priority: bool = False) -> Task:
        with self._condition:
            task.id = self._generate_id(task)
            task.state.id = task.id
            # Subclasses often set name/key after Task.__init__ created the state
            task.state.name = task.name
            task.state.key = task.key
            task.state.owner = task.owner
            task.on_progress(self._on_progress)
            self._tasks[task.id] = task
            if high_priority:
                self._high_queue.append(task)
            else:
                self._normal_queue.append(task)
            self._condition.notify()
        self._emit()
        return task

    def stop_task(self, task_id: str) -> bool:
        """Stop a queued or running task. Returns False if the task is unknown or finished."""
        with self._condition:
            task = self._tasks.get(task_id)
            if task is None or task.state.finished:
                return False
            already_stopping = task.state.cancelled
            task.state.cancelled = True
            task.stop()
            running = task.state.running
            if not running:
                # Still queued: the worker skips it when it reaches it.
                task.state.finished = True
                task._finished_event.set()
        if running and not already_stopping:
            threading.Thread(target=self._escalate, args=(task,), daemon=True,
                             name=f'TaskStop-{task.id}').start()
        self._emit()
        return True

    def stop_owner_tasks(self, owner: str) -> list[str]:
        """Stop every unfinished task queued by `owner` (a plugin name). Returns their ids."""
        with self._condition:
            ids = [t.id for t in self._tasks.values() if t.owner == owner and not t.state.finished]
        return [task_id for task_id in ids if self.stop_task(task_id)]

    def dismiss_task(self, task_id: str) -> bool:
        """Remove a finished task from the list. Returns False if it is unknown or not finished."""
        with self._condition:
            task = self._tasks.get(task_id)
            if task is None or not task.state.finished:
                return False
            self._tasks.pop(task_id)
            self._frozen.pop(task_id, None)
        self._emit()
        return True

    def dismiss_finished(self) -> None:
        with self._condition:
            for task_id in [i for i, t in self._tasks.items() if t.state.finished]:
                self._tasks.pop(task_id)
                self._frozen.pop(task_id, None)
        self._emit()

    def get_states(self) -> list[TaskState]:
        with self._condition:
            return [self._frozen.get(t.id, t.state) for t in self._tasks.values()]

    def close(self):
        with self._condition:
            self._stop = True
            self._condition.notify()
            ids = list(self._tasks.keys())
        for task_id in ids:
            self.stop_task(task_id)
        self._worker.join(timeout=5)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _worker_loop(self):
        while True:
            with self._condition:
                while not self._stop and not self._high_queue and not self._normal_queue:
                    self._condition.wait()
                if self._stop:
                    break
                task = self._high_queue.popleft() if self._high_queue else self._normal_queue.popleft()
                # Decided under the lock so stop_task sees either a queued or a running task
                ran = not task.state.cancelled
                if ran:
                    task.state.running = True
                    task.state.started_at = time.monotonic()
                    task._thread = threading.Thread(target=self._run, args=(task,), daemon=True,
                                                    name=f'Task-{task.id}')
                    task._thread.start()

            if ran:
                self._emit()
                task._released.wait()
                self._emit()
            self._after_task(task, ran)

    def _run(self, task: Task):
        """Body of a task's thread."""
        try:
            task.start()
        except TaskCancelled:
            logging.info(f"Task {task.id} interrupted")
        except Exception:
            logging.exception(f"Task {task.id} failed")
        finally:
            try:
                self._release(task)
            except TaskCancelled:
                # Interrupted before the release finished: _escalate abandons the task.
                pass

    def _release(self, task: Task, abandoned: bool = False):
        """Mark the task finished and let the worker start the next one."""
        with self._condition:
            if task._released.is_set():
                return
            task.state.running = False
            task.state.finished = True
            if abandoned:
                self._frozen[task.id] = task.state.model_copy()
            task._finished_event.set()
            task._released.set()

    def _escalate(self, task: Task):
        """Interrupt, then abandon, a stopped task that does not exit by itself."""
        if task._released.wait(self._stop_grace):
            return
        with self._condition:
            # Checked under the lock: _release takes it too, so a released task is never interrupted.
            if task._released.is_set():
                return
            thread = task._thread
            if thread is not None and thread.is_alive():
                logging.warning(f"Task {task.id} did not stop by itself, interrupting it")
                _raise_in_thread(thread, TaskCancelled)
        if task._released.wait(self._interrupt_grace):
            return
        logging.warning(f"Task {task.id} is blocked, abandoning its thread")
        self._release(task, abandoned=True)

    def _after_task(self, task: Task, ran: bool) -> None:
        """Run on_last() once no other task of the same key is waiting in the queue."""
        with self._condition:
            if self._stop:
                return
            if ran:
                self._on_last_due.add(task.key)
            pending = any(
                t.key == task.key and not t.state.cancelled
                for q in (self._high_queue, self._normal_queue)
                for t in q
            )
            fire = task.key in self._on_last_due and not pending
            if fire:
                self._on_last_due.discard(task.key)
        if fire:
            try:
                task.on_last()
            except Exception:
                logging.exception(f"Task {task.id!r} on_last() failed")

    def _on_progress(self, state: TaskState):
        self._emit()

    def _emit(self):
        if self._on_update:
            try:
                self._on_update(self.get_states())
            except Exception as e:
                logging.error(f"TaskManager on_update callback failed: {e}")

    def _generate_id(self, task: Task) -> str:
        self._counters[task.key] += 1
        return f"{task.key}#{self._counters[task.key]}"


def _raise_in_thread(thread: threading.Thread, exc_type: type[BaseException]) -> None:
    """Raise exc_type in `thread` at its next Python bytecode.

    A thread blocked in C code (a lock wait, a GPU call) only sees it once that call returns.
    """
    ident = ctypes.c_ulong(thread.ident)
    count = ctypes.pythonapi.PyThreadState_SetAsyncExc(ident, ctypes.py_object(exc_type))
    if count > 1:
        # Should not happen: undo it rather than interrupt other threads.
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ident, None)
