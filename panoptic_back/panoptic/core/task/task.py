import logging
import threading
from abc import ABC, abstractmethod
from typing import Callable

from panoptic.models.models import TaskState


class Task(ABC):
    def __init__(self):
        self.key:  str      = type(self).__name__
        self.name: str      = self.key
        self.id:   str | None = None
        self.state = TaskState(id='unregistered', name=self.name, key=self.key)

        self._cancel_event   = threading.Event()
        self._finished_event = threading.Event()
        self._progress_callbacks: list[Callable[[TaskState], None]] = []

    def on_progress(self, callback: Callable[[TaskState], None]):
        self._progress_callbacks.append(callback)
        return self

    def stop(self):
        self._cancel_event.set()

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
        Override to trigger post-batch work (e.g. rebuilding a Faiss index after all
        vector computation tasks complete).
        """
        pass

    @abstractmethod
    def start(self):
        pass
