# task.py
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Callable

from panoptic.models import TaskState

logger = logging.getLogger('Task')


class Task(ABC):
    def __init__(self):
        self.key: str = type(self).__name__
        self.name: str = self.key
        self.id: str | None = None
        self.state = TaskState(id='unregistered', name=self.name, key=self.key)

        self._progress_callbacks: list[Callable[[TaskState], None]] = []
        self._cancel_event = asyncio.Event()
        self._finished_event = asyncio.Event()

    def get_id(self) -> str:
        if self.id is None:
            raise RuntimeError(f"Task '{self.key}' is unregistered.")
        return self.id

    def on_progress(self, callback: Callable[[TaskState], None]):
        self._progress_callbacks.append(callback)
        return self

    def _notify(self):
        for cb in self._progress_callbacks:
            try:
                cb(self.state)
            except Exception as e:
                logger.error(f"Progress callback failed: {e}")

    async def wait(self):
        await self._finished_event.wait()

    def stop(self):
        """Signals the task to cancel gracefully."""
        self._cancel_event.set()

    @abstractmethod
    async def start(self):
        """The concrete task implementation goes here."""
        pass