"""TaskManager stop behaviour.

Run from panoptic_back/:
    .venv/bin/python -m pytest panoptic/core/task/tests
"""
from __future__ import annotations

import threading
import time
import unittest

from panoptic.core.task.task import Task
from panoptic.core.task.task_manager import TaskManager

GRACE = 0.2


def wait_until(predicate, timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class RecordingTask(Task):
    """Finishes immediately and records that it ran."""

    def __init__(self, key: str = 'Recording', log: list | None = None):
        super().__init__()
        self.key = key
        self.ran = False
        self.log = log if log is not None else []

    def start(self):
        self.ran = True

    def on_last(self):
        self.log.append(('on_last', self.key))


class CooperativeTask(Task):
    """Loops until it is stopped, checking is_cancelled()."""

    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.clean_exit = False

    def start(self):
        self.started.set()
        while not self.is_cancelled():
            time.sleep(0.01)
        self.clean_exit = True


class StubbornTask(Task):
    """Ignores the stop flag and swallows every Exception."""

    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.cleanup_ran = False

    def start(self):
        self.started.set()
        try:
            while True:
                try:
                    time.sleep(0.01)
                except Exception:
                    pass
        finally:
            self.cleanup_ran = True


class BlockedTask(Task):
    """Blocks in a C-level wait that TaskCancelled cannot interrupt."""

    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.unblock = threading.Event()

    def start(self):
        self.started.set()
        self.unblock.wait()
        self.state.done = 999  # must not show: the state is frozen once abandoned


class TaskManagerStopTest(unittest.TestCase):
    def setUp(self):
        self.tm = TaskManager(stop_grace=GRACE, interrupt_grace=GRACE)

    def tearDown(self):
        self.tm.close()

    def _state(self, task: Task):
        return next(s for s in self.tm.get_states() if s.id == task.id)

    def test_cooperative_task_stops_cleanly(self):
        task = self.tm.add_task(CooperativeTask())
        self.assertTrue(task.started.wait(2))
        self.assertTrue(self.tm.stop_task(task.id))
        self.assertTrue(wait_until(lambda: self._state(task).finished, GRACE))
        self.assertTrue(task.clean_exit)
        self.assertTrue(self._state(task).cancelled)
        self.assertFalse(self._state(task).running)

    def test_task_ignoring_stop_is_interrupted(self):
        task = self.tm.add_task(StubbornTask())
        self.assertTrue(task.started.wait(2))
        self.tm.stop_task(task.id)
        self.assertTrue(wait_until(lambda: self._state(task).finished, 3 * GRACE))
        # Interrupted through TaskCancelled, so its own finally blocks still ran
        self.assertTrue(task.cleanup_ran)
        self.assertNotIn(task.id, self.tm._frozen)

    def test_blocked_task_is_abandoned_and_queue_moves_on(self):
        blocked = self.tm.add_task(BlockedTask())
        after = self.tm.add_task(RecordingTask())
        self.assertTrue(blocked.started.wait(2))
        self.tm.stop_task(blocked.id)
        self.assertTrue(wait_until(lambda: after.ran, 5 * GRACE))
        self.assertTrue(self._state(blocked).finished)
        self.assertTrue(self._state(blocked).cancelled)

        # The abandoned thread finishes later; its writes do not reach the reported state
        blocked.unblock.set()
        blocked._thread.join(2)
        self.assertEqual(self._state(blocked).done, 0)

    def test_queued_task_never_starts(self):
        running = self.tm.add_task(CooperativeTask())
        queued = self.tm.add_task(RecordingTask())
        sentinel = self.tm.add_task(RecordingTask())
        self.assertTrue(running.started.wait(2))
        self.assertTrue(self.tm.stop_task(queued.id))
        self.assertTrue(self._state(queued).finished)
        self.assertTrue(self._state(queued).cancelled)

        self.tm.stop_task(running.id)
        self.assertTrue(wait_until(lambda: sentinel.ran))
        self.assertFalse(queued.ran)

    def test_stop_finished_or_unknown_task_returns_false(self):
        task = self.tm.add_task(RecordingTask())
        self.assertTrue(wait_until(lambda: self._state(task).finished))
        self.assertFalse(self.tm.stop_task(task.id))
        self.assertFalse(self.tm.stop_task('Nope#1'))

    def test_on_last_runs_after_a_stop(self):
        log: list = []

        class Loop(CooperativeTask):
            def on_last(self):
                log.append('on_last')

        task = self.tm.add_task(Loop())
        self.assertTrue(task.started.wait(2))
        self.tm.stop_task(task.id)
        self.assertTrue(wait_until(lambda: log == ['on_last']))

    def test_on_last_runs_once_when_a_queued_duplicate_is_stopped(self):
        log: list = []
        gate = CooperativeTask()
        self.tm.add_task(gate)
        first = self.tm.add_task(RecordingTask('K', log))
        second = self.tm.add_task(RecordingTask('K', log))
        self.assertTrue(gate.started.wait(2))
        self.tm.stop_task(second.id)
        self.tm.stop_task(gate.id)
        self.assertTrue(wait_until(lambda: first.ran))
        time.sleep(0.2)
        self.assertEqual(log, [('on_last', 'K')])
        self.assertFalse(second.ran)

    def test_on_last_runs_when_the_last_pending_duplicate_is_stopped(self):
        log: list = []
        first = RecordingTask('K', log)
        gate = CooperativeTask()
        second = RecordingTask('K', log)
        for task in (first, gate, second):
            self.tm.add_task(task)
        # first finished while second was pending, so its on_last waits for second
        self.assertTrue(gate.started.wait(2))
        self.assertEqual(log, [])
        self.tm.stop_task(second.id)
        self.tm.stop_task(gate.id)
        self.assertTrue(wait_until(lambda: log == [('on_last', 'K')]))
        time.sleep(0.1)
        self.assertEqual(log, [('on_last', 'K')])
        self.assertFalse(second.ran)

    def test_stop_owner_tasks(self):
        running = CooperativeTask()
        running.owner = 'plugin_a'
        other = RecordingTask()
        mine = RecordingTask()
        mine.owner = 'plugin_a'
        self.tm.add_task(running)
        self.tm.add_task(other)
        self.tm.add_task(mine)
        self.assertTrue(running.started.wait(2))

        stopped = self.tm.stop_owner_tasks('plugin_a')
        self.assertEqual(sorted(stopped), sorted([running.id, mine.id]))
        self.assertEqual(self._state(running).owner, 'plugin_a')
        self.assertTrue(wait_until(lambda: other.ran))
        self.assertFalse(mine.ran)

    def test_dismiss_only_finished_tasks(self):
        running = self.tm.add_task(CooperativeTask())
        self.assertTrue(running.started.wait(2))
        self.assertFalse(self.tm.dismiss_task(running.id))
        self.tm.stop_task(running.id)
        self.assertTrue(wait_until(lambda: self._state(running).finished))
        self.assertTrue(self.tm.dismiss_task(running.id))
        self.assertEqual(self.tm.get_states(), [])


if __name__ == '__main__':
    unittest.main()
