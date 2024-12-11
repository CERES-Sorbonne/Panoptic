import asyncio
import logging
import sys
import traceback
from collections import defaultdict
from concurrent.futures import Executor
from typing import Dict, List

from panoptic.core.task.task import Task
from panoptic.models import TaskState

logger = logging.getLogger('TaskQueue')


class TaskQueue:
    def __init__(self, executor: Executor, num_workers: int = 1):
        self._executor = executor
        self._priority_tasks = asyncio.Queue()
        self._tasks = asyncio.Queue()
        self._num_workers = num_workers
        self._workers: List[asyncio.Task] = []
        self._working: Dict[int, bool] = {}
        self.onFinish = asyncio.Event()

        self.counters: dict[str, int] = defaultdict(int)

        self._task_states: Dict[str, TaskState] = {}

        for i in range(num_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

    def get_task_states(self) -> List[TaskState]:
        return list(self._task_states.values())

    def empty(self):
        return self._priority_tasks.empty() and self._tasks.empty()

    def add_task(self, task: Task):
        if task.has_priority:
            self._priority_tasks.put_nowait(task)
        else:
            self._tasks.put_nowait(task)

        if task.get_id() not in self._task_states:
            self._task_states[task.get_id()] = TaskState(id=task.get_id(), name=task.name, total=0, remain=0)

        state = self._task_states[task.get_id()]
        state.done = False
        state.total += 1
        state.remain += 1

        self.counters[task.key] += 1

    async def _worker(self, worker_id: int):
        while True:
            try:
                # if nothing to do mark as inactive
                if self.empty():
                    self._working[worker_id] = False

                # if we have priority tasks take it
                if not self._priority_tasks.empty():
                    task = await self._priority_tasks.get()
                    state = self._task_states[task.get_id()]
                    state.remain -= 1
                # else normal task
                else:
                    if self._tasks.empty():
                        await asyncio.sleep(0.5)  # sleep a bit if no tasks available
                        continue
                    task = await self._tasks.get()
                    state = self._task_states[task.get_id()]
                    state.remain -= 1

                # set working Flag and execute task
                self._working[worker_id] = True
                task.set_executor(self._executor)
                try:
                    state.computing += 1
                    self.onFinish.clear()
                    await task.run()
                    state.computing -= 1
                    self.counters[task.key] -= 1
                except Exception as e:
                    state.computing -= 1
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    logger.error("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
                    logger.error(e)
                if state.remain == 0 and state.computing == 0:
                    state.done = True
                    self.onFinish.set()
                if self.counters[task.key] == 0:
                    await task.run_if_last()

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                logger.error("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
                logger.error(e)

    async def close(self):
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
