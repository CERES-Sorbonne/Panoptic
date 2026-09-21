import logging
import threading
from abc import ABC, abstractmethod
from typing import Callable

from panoptic.models.models import TaskState


class TaskCancelled(BaseException):
    """Raised inside a task's thread when the task does not stop by itself.

    It extends BaseException so that `except Exception` blocks in task code do not catch it.
    """


class Task(ABC):
    """A unit of background work run by the TaskManager.

    Every task can be stopped. A task that checks `is_cancelled()` between steps stops
    cleanly. A task that does not check is interrupted by the TaskManager (see
    TaskManager.stop_task), so the check is optional.
    """

    def __init__(self):
        self.key:  str      = type(self).__name__
        self.name: str      = self.key
        self.id:   str | None = None
        # Plugin that queued the task. Set by the plugin interface, None for core tasks.
        self.owner: str | None = None
        self.state = TaskState(id='unregistered', name=self.name, key=self.key)

        self._cancel_event   = threading.Event()
        self._finished_event = threading.Event()
        # Owned by TaskManager: the thread running start(), and the event set once the
        # task no longer holds the queue (it returned, or its thread was abandoned).
        self._thread: threading.Thread | None = None
        self._released = threading.Event()
        self._progress_callbacks: list[Callable[[TaskState], None]] = []

    def on_progress(self, callback: Callable[[TaskState], None]):
        self._progress_callbacks.append(callback)
        return self

    def stop(self):
        """Ask the task to stop. Use TaskManager.stop_task to stop a queued or running task."""
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        """True once a stop was requested. Check it between steps to stop cleanly."""
        return self._cancel_event.is_set()

    def set_step(self, step: str, detail: str | None = None):
        """Update the task's current phase, e.g. 'Scanning folder structure', 'Loading plugin'."""
        self.state.step = step
        self.state.detail = detail
        self._notify()

    def set_workers(self, workers: int):
        self.state.workers = workers
        self._notify()

    def wait(self):
        self._finished_event.wait()

    def _notify(self):
        for cb in self._progress_callbacks:
            try:
                cb(self.state)
            except Exception as e:
                logging.error(f"Progress callback failed: {e}")

    def on_last(self) -> None:
        """Called by TaskManager after the last queued/running task of this key finishes.
        Also called when that last task was stopped, so the work done so far is used.
        Override to trigger post-batch work (e.g. rebuilding a Faiss index after all
        vector computation tasks complete).
        """
        pass

    @abstractmethod
    def start(self):
        pass
