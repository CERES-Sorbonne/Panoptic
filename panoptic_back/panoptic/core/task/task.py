from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from panoptic.core.project.project import Project

class Task:
    """
    Base class for a Task managed by the TaskQueue.
    To use the task class outside the TaskQueue you need to set_executor manually
    """
    def __init__(self, priority=False):
        self._project: Project | None = None
        self.has_priority = priority
        self.name = type(self).__name__
        self.key = type(self).__name__

    def set_project(self, project: Project):
        self._project = project

    def get_id(self):
        return self.key

    async def run_async(self, function, *args):
        """
        Make function awaitable and execute in Executor
        """
        return await self._project.run_async(function, *args)

    async def run(self):
        raise NotImplementedError()

    async def run_if_last(self):
        pass
