import asyncio
import logging
import sys
import traceback
from concurrent.futures import Executor
from typing import Dict, List

from panoptic.core.task.task import Task

logger = logging.getLogger('TaskQueue')


class TaskQueue:
    def __init__(self, executor: Executor, num_workers: int = 1):
        self._executor = executor
        self._priority_tasks = asyncio.Queue()
        self._tasks = asyncio.Queue()
        self._num_workers = num_workers
        self._workers: List[asyncio.Task] = []
        self._working: Dict[int, bool] = {}

        for i in range(num_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

    def empty(self):
        return self._priority_tasks.empty() and self._tasks.empty()

    def add_task(self, task: Task):
        if task.has_priority:
            self._priority_tasks.put_nowait(task)
        else:
            self._tasks.put_nowait(task)

    async def _worker(self, worker_id: int):
        while True:
            try:
                # if nothing to do mark as inactive
                if self.empty():
                    self._working[worker_id] = False

                # if we have priority tasks take it
                if not self._priority_tasks.empty():
                    task = await self._priority_tasks.get()
                # else normal task
                else:
                    if self._tasks.empty():
                        await asyncio.sleep(0.5)  # sleep a bit if no tasks available
                        continue
                    task = await self._tasks.get()

                # set working Flag and execute task
                self._working[worker_id] = True
                task.set_executor(self._executor)
                await task.run()

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                logger.error("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
                logger.error(e)

    async def close(self):
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
