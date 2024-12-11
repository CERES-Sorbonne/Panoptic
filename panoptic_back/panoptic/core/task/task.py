import asyncio
from concurrent.futures import Executor


class Task:
    """
    Base class for a Task managed by the TaskQueue.
    To use the task class outside the TaskQueue you need to set_executor manually
    """
    def __init__(self, priority=False):
        self._executor: Executor | None = None
        self.has_priority = priority
        self.name = type(self).__name__
        self.key = type(self).__name__

    def set_executor(self, executor: Executor):
        self._executor = executor

    def get_id(self):
        return str(self.__class__)

    async def _async(self, function, *args):
        """
        Make function awaitable and execute in Executor
        """
        return await asyncio.wrap_future(self._executor.submit(function, *args))

    async def run(self):
        raise NotImplementedError()

    async def run_if_last(self):
        pass
