"""Plugin tasks: long jobs run in the plugin process, tracked by the backend TaskManager.

Flow (see PLUGIN_PROTOCOL.md "Tasks"): ``task.create`` gives the task an id in the backend task
list. A *queued* task (default, same behaviour as the in-process TaskManager: one task at a time
per project, behind imports) waits for the backend's ``task.start``; then it runs in its own
thread and reports ``task.progress`` (throttled), and ends with ``task.done`` / ``task.failed``.
``task.stop`` from the backend sets the cancel flag; a task that does not return within
STOP_GRACE seconds gets TaskCancelled raised in its thread.
"""
from __future__ import annotations

import ctypes
import itertools
import logging
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger('panoptic_plugin.tasks')

STOP_GRACE = 3.0
INTERRUPT_GRACE = 3.0
PROGRESS_INTERVAL = 0.1   # seconds between two task.progress of one task


class TaskCancelled(BaseException):
    """Raised inside a task's thread when it does not stop by itself (BaseException so that
    `except Exception` in task code does not swallow it)."""


@dataclass
class TaskState:
    id: str | None = None
    name: str = ''
    key: str = ''
    total: int = 0
    done: int = 0
    failed: int = 0
    step: str | None = None
    detail: str | None = None
    workers: int | None = None
    vector_type_id: int | None = None
    running: bool = False
    finished: bool = False
    cancelled: bool = False

    def progress_params(self) -> dict:
        return {'task_id': self.id, 'total': self.total, 'done': self.done, 'failed': self.failed,
                'step': self.step, 'detail': self.detail, 'workers': self.workers}


class Task:
    """Base class of a plugin task. Override :meth:`run`.

    Same surface as the old in-process ``panoptic.core.task.task.Task`` so tasks port easily:
    ``self.state.total / done / failed``, ``self._notify()``, ``self.is_cancelled()``,
    ``self.set_step()``, ``self.set_workers()``, ``self.on_last()``.
    """

    def __init__(self, name: str | None = None, key: str | None = None):
        self.key: str = key or type(self).__name__
        self.name: str = name or self.key
        self.id: str | None = None
        self.vector_type_id: int | None = None
        self.state = TaskState(name=self.name, key=self.key)
        self._cancel_event = threading.Event()
        self._started = threading.Event()
        self._finished_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._runner: TaskRunner | None = None
        self._last_sent = 0.0
        self._progress_lock = threading.Lock()

    # -- to override --------------------------------------------------------------------
    def run(self) -> None:
        raise NotImplementedError

    def on_last(self) -> None:
        """Called after the last running/queued task of this key (in this plugin) finished,
        stopped tasks included, e.g. to rebuild an index once a batch of tasks is done."""

    # -- helpers for task code ----------------------------------------------------------
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def check_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise TaskCancelled()

    def set_total(self, total: int) -> None:
        self.state.total = total
        self._notify()

    def advance(self, done: int = 1, failed: int = 0) -> None:
        with self._progress_lock:
            self.state.done += done
            self.state.failed += failed
        self._notify()

    def set_step(self, step: str, detail: str | None = None) -> None:
        self.state.step = step
        self.state.detail = detail
        self._notify(force=True)

    def set_workers(self, workers: int) -> None:
        self.state.workers = workers
        self._notify()

    def _notify(self, force: bool = False) -> None:
        """Report progress to the backend (throttled; the final state is always sent)."""
        runner = self._runner
        if runner is None or self.id is None:
            return
        now = time.monotonic()
        if not force and now - self._last_sent < PROGRESS_INTERVAL:
            runner._schedule_flush(self)
            return
        self._last_sent = now
        runner._send_progress(self)

    def stop(self) -> None:
        self._cancel_event.set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._finished_event.wait(timeout)


class FunctionTask(Task):
    """A task running ``fn(task, *args, **kwargs)``."""

    def __init__(self, fn: Callable, name: str | None = None, key: str | None = None,
                 total: int = 0, args: tuple = (), kwargs: dict | None = None,
                 on_last: Callable[[], None] | None = None):
        super().__init__(name=name or getattr(fn, '__name__', 'task'), key=key or getattr(fn, '__name__', None))
        self._fn = fn
        self._args = args
        self._kwargs = kwargs or {}
        self._on_last = on_last
        self.state.total = total
        self.result: Any = None

    def run(self) -> None:
        self.result = self._fn(self, *self._args, **self._kwargs)

    def on_last(self) -> None:
        if self._on_last:
            self._on_last()


class TaskRunner:
    """Runs a plugin's tasks; one per plugin process (``plugin.tasks``)."""

    def __init__(self, bridge=None, owner: str = ''):
        self._bridge = bridge          # runtime bridge (None = offline: tasks run immediately)
        self._owner = owner
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._local_ids = itertools.count(1)
        self._flush_timers: dict[str, threading.Timer] = {}
        self._closed = False

    # -- public ---------------------------------------------------------------------------
    def add(self, task: Task, high_priority: bool = False, queued: bool = True) -> Task:
        """Register ``task`` with the backend and start it (when the backend says so if queued).
        Returns the task, with its ``id`` set. Same role as the old ``project.add_task``."""
        if self._closed:
            raise RuntimeError('task runner is closed')
        task.state.name, task.state.key, task.state.vector_type_id = task.name, task.key, task.vector_type_id
        task._runner = self
        if self._bridge is not None:
            res = self._bridge.call('task.create', {
                'key': task.key, 'name': task.name, 'total': task.state.total,
                'vector_type_id': task.vector_type_id, 'step': task.state.step,
                'detail': task.state.detail, 'queued': queued, 'high_priority': high_priority,
            })
            task.id = res['task_id']
        else:
            task.id = f'{task.key}#{next(self._local_ids)}'
            queued = False
        task.state.id = task.id
        with self._lock:
            self._tasks[task.id] = task
        task._thread = threading.Thread(target=self._thread_main, args=(task,), daemon=True,
                                        name=f'Task-{task.id}')
        if not queued:
            task._started.set()
        task._thread.start()
        return task

    def run(self, fn: Callable, name: str | None = None, total: int = 0, key: str | None = None,
            vector_type_id: int | None = None, args: tuple = (), kwargs: dict | None = None,
            on_last: Callable[[], None] | None = None, high_priority: bool = False,
            queued: bool = True) -> Task:
        """Run ``fn(task, *args)`` as a tracked task. ``task.advance()`` reports progress,
        ``task.is_cancelled()`` tells when to stop."""
        task = FunctionTask(fn, name=name, key=key, total=total, args=args, kwargs=kwargs, on_last=on_last)
        task.vector_type_id = vector_type_id
        return self.add(task, high_priority=high_priority, queued=queued)

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def active(self) -> list[Task]:
        with self._lock:
            return [t for t in self._tasks.values() if not t.state.finished]

    # -- backend events -------------------------------------------------------------------
    def on_start(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            task._started.set()

    def on_stop(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None or task.state.finished:
            return False
        already = task.state.cancelled
        task.state.cancelled = True
        task.stop()
        if not task._started.is_set():
            task._started.set()          # the thread sees the cancel flag and ends at once
        elif not already:
            threading.Thread(target=self._escalate, args=(task,), daemon=True,
                             name=f'TaskStop-{task_id}').start()
        return True

    def stop_all(self, wait: float = STOP_GRACE + INTERRUPT_GRACE) -> None:
        tasks = self.active()
        for t in tasks:
            if t.id:
                self.on_stop(t.id)
        deadline = time.monotonic() + wait
        for t in tasks:
            t.wait(max(0.0, deadline - time.monotonic()))

    def close(self) -> None:
        self._closed = True
        self.stop_all()
        for timer in list(self._flush_timers.values()):
            timer.cancel()

    # -- internals ------------------------------------------------------------------------
    def _thread_main(self, task: Task) -> None:
        task._started.wait()
        ran = False
        error: BaseException | None = None
        try:
            if not task.is_cancelled():
                ran = True
                task.state.running = True
                task._notify(force=True)
                task.run()
        except TaskCancelled:
            log.info(f'task {task.id} interrupted')
        except Exception as e:
            log.exception(f'task {task.id} failed')
            error = e
        finally:
            self._finish(task, error)
        if ran:
            self._maybe_on_last(task)

    def _finish(self, task: Task, error: BaseException | None) -> None:
        with self._lock:
            if task.state.finished:
                return
            task.state.running = False
            task.state.finished = True
        timer = self._flush_timers.pop(task.id, None)
        if timer:
            timer.cancel()
        if self._bridge is not None:
            self._send_progress(task)
            if error is not None:
                self._bridge.notify('task.failed', {'task_id': task.id, 'error': {
                    'type': type(error).__name__, 'message': str(error),
                    'traceback': ''.join(traceback.format_exception(type(error), error, error.__traceback__)),
                }})
            else:
                self._bridge.notify('task.done', {'task_id': task.id, 'cancelled': task.is_cancelled()})
        task._finished_event.set()

    def _maybe_on_last(self, task: Task) -> None:
        with self._lock:
            pending = any(t.key == task.key and not t.state.finished and not t.state.cancelled
                          for t in self._tasks.values() if t is not task)
        if pending:
            return
        try:
            task.on_last()
        except Exception:
            log.exception(f'task {task.id} on_last() failed')

    def _escalate(self, task: Task) -> None:
        if task._finished_event.wait(STOP_GRACE):
            return
        thread = task._thread
        if thread is not None and thread.is_alive():
            log.warning(f'task {task.id} did not stop by itself, interrupting it')
            _raise_in_thread(thread, TaskCancelled)
        if task._finished_event.wait(INTERRUPT_GRACE):
            return
        log.warning(f'task {task.id} is blocked, abandoning its thread')
        self._finish(task, None)

    def _send_progress(self, task: Task) -> None:
        if self._bridge is not None:
            self._bridge.notify('task.progress', task.state.progress_params())

    def _schedule_flush(self, task: Task) -> None:
        """Make sure a throttled update is eventually sent."""
        if task.id in self._flush_timers:
            return

        def flush():
            self._flush_timers.pop(task.id, None)
            if not task.state.finished:
                task._last_sent = time.monotonic()
                self._send_progress(task)

        timer = threading.Timer(PROGRESS_INTERVAL, flush)
        timer.daemon = True
        self._flush_timers[task.id] = timer
        timer.start()


def _raise_in_thread(thread: threading.Thread, exc_type: type[BaseException]) -> None:
    ident = ctypes.c_ulong(thread.ident)
    count = ctypes.pythonapi.PyThreadState_SetAsyncExc(ident, ctypes.py_object(exc_type))
    if count > 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ident, None)
