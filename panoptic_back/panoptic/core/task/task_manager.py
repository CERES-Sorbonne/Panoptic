import collections
import logging
import threading
from collections import defaultdict
from typing import Callable

from panoptic.models.models import TaskState
from panoptic.core.task.task import Task

PRIORITY_HIGH   = 0
PRIORITY_NORMAL = 10


class TaskManager:
    def __init__(self, on_update: Callable[[list[TaskState]], None] = None):
        self._high_queue:   collections.deque[Task] = collections.deque()
        self._normal_queue: collections.deque[Task] = collections.deque()
        self._condition = threading.Condition()
        self._tasks:    dict[str, Task] = {}
        self._counters: defaultdict[str, int] = defaultdict(int)
        self._on_update = on_update
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
            task.on_progress(self._on_progress)
            self._tasks[task.id] = task
            if high_priority:
                self._high_queue.append(task)
            else:
                self._normal_queue.append(task)
            self._condition.notify()
        self._emit()
        return task

    def stop_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if task:
            task.stop()

    def dismiss_task(self, task_id: str):
        with self._condition:
            self._tasks.pop(task_id, None)
        self._emit()

    def get_states(self) -> list[TaskState]:
        return [t.state for t in self._tasks.values()]

    def close(self):
        with self._condition:
            self._stop = True
            self._condition.notify()
        for task in list(self._tasks.values()):
            task.stop()
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

            self._run_wrapper(task)

    def _run_wrapper(self, task: Task):
        task.state.running = True
        self._emit()
        try:
            task.start()
        except Exception:
            logging.exception(f"Task {task.id} failed")
        finally:
            task.state.running = False
            task.state.finished = True
            task._finished_event.set()
            self._emit()
        self._maybe_on_last(task)

    def _maybe_on_last(self, task: Task) -> None:
        with self._condition:
            pending = any(
                t.key == task.key
                for q in (self._high_queue, self._normal_queue)
                for t in q
            )
            running = any(
                t.state.running
                for t in self._tasks.values()
                if t.key == task.key and t.id != task.id
            )
        if not pending and not running:
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
