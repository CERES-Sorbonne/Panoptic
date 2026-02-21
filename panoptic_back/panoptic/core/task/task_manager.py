from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from panoptic.core.project.project import Project
    from panoptic.core.task.task import Task

from panoptic.models import TaskState
from panoptic.utils import EventListener

logger = logging.getLogger('TaskManager')


class TaskManager:
    def __init__(self, project: Project):
        self.project = project
        self._tasks: Dict[str, Task] = {}
        self._runners: Dict[str, asyncio.Task] = {}
        self._counters: Dict[str, int] = defaultdict(int)

        # Observable event for UI updates
        self.on_update = EventListener()

    def add_task(self, task: Task) -> Task:
        """
        Assigns a unique ID, connects progress tracking,
        and schedules the task for execution.
        """
        # 1. Identity & State Setup
        task.id = self._generate_id(task)
        task.state.id = task.id

        # 2. Connect progress callback to manager's emitter
        task.on_progress(self._on_progress)

        # 3. Registration
        self._tasks[task.id] = task

        # 4. Execution
        # We wrap the run in a native asyncio Task to manage its lifecycle
        runner = asyncio.create_task(self._run_wrapper(task))
        self._runners[task.id] = runner

        # Initial UI Update
        self.on_update.emit(self.get_states())
        return task

    # ------------------------------------------------------------------
    # Lifecycle Management
    # ------------------------------------------------------------------

    async def _run_wrapper(self, task: Task):
        """
        A wrapper around task.start() to handle cleanup,
        cancellation, and error reporting.
        """
        try:
            # The heart of the task execution
            await task.start()
        except asyncio.CancelledError:
            logger.info(f"Task {task.id} was cancelled.")
            # Ensure the state reflects cancellation if the task didn't set it
            task.state.running = False
        except Exception:
            logger.exception(f"Task {task.id} raised an unexpected error.")
            task.state.running = False
        finally:
            # Remove from runners regardless of outcome
            t = self._runners.pop(task.id, None)

            # Final state notification (mark as finished/not running)
            self.on_update.emit(self.get_states())

    def stop_task(self, task_id: str):
        """Request a task to stop gracefully."""
        task = self._tasks.get(task_id)
        if task:
            task.stop()  # Sets the internal asyncio.Event()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_states(self) -> List[TaskState]:
        return [t.state for t in self._tasks.values()]

    def get_running(self) -> List[Task]:
        return [self._tasks[tid] for tid in self._runners]

    def _generate_id(self, task: Task) -> str:
        self._counters[task.key] += 1
        return f"{task.key}#{self._counters[task.key]}"

    def _on_progress(self, state: TaskState):
        """Triggered whenever a task calls self._notify()."""
        self.on_update.emit(self.get_states())

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self):
        """Gracefully shut down all running tasks."""
        # First, signal all tasks to stop their internal loops
        for task in self.get_running():
            task.stop()

        if self._runners:
            # Allow tasks a moment to clean up (e.g., closing file handles)
            # return_exceptions=True prevents one crash from stopping other cleanups
            await asyncio.gather(*self._runners.values(), return_exceptions=True)

        self._runners.clear()
        logger.info("TaskManager closed. All tasks stopped.")