import threading
import time

from panoptic2.core.task.task import Task
from panoptic2.core.task.task_manager import TaskManager, PRIORITY_HIGH, PRIORITY_NORMAL


class RecordingTask(Task):
    """Task that records when it ran into a shared list, with a configurable delay."""
    def __init__(self, name: str, record: list, delay: float = 0.0):
        super().__init__()
        self.name = name
        self._record = record
        self._delay = delay

    def start(self):
        if self._delay:
            time.sleep(self._delay)
        self._record.append(self.name)


def _make_manager() -> TaskManager:
    return TaskManager()


def test_normal_tasks_run_in_fifo_order():
    ran = []
    done = threading.Event()

    def on_update(states):
        if all(s.finished for s in states) and len(states) == 3:
            done.set()

    mgr = TaskManager(on_update=on_update)
    mgr.add_task(RecordingTask('A', ran))
    mgr.add_task(RecordingTask('B', ran))
    mgr.add_task(RecordingTask('C', ran))

    done.wait(timeout=3)
    mgr.close()
    assert ran == ['A', 'B', 'C']


def test_high_priority_jumps_normal_queue():
    ran = []
    slow_started = threading.Event()
    done = threading.Event()

    def on_update(states):
        if all(s.finished for s in states) and len(states) == 3:
            done.set()

    class SlowTask(Task):
        def __init__(self):
            super().__init__()
            self.name = 'slow'

        def start(self):
            slow_started.set()      # signal: worker is now inside this task
            time.sleep(0.1)
            ran.append('slow')

    mgr = TaskManager(on_update=on_update)
    mgr.add_task(SlowTask())

    # Only queue the other two once 'slow' is confirmed running,
    # otherwise the worker may pick 'high' before it ever starts 'slow'
    slow_started.wait(timeout=2)
    mgr.add_task(RecordingTask('normal', ran), high_priority=False)
    mgr.add_task(RecordingTask('high',   ran), high_priority=True)

    done.wait(timeout=5)
    mgr.close()

    assert ran == ['slow', 'high', 'normal']


def test_tasks_run_serially():
    ran = []
    active_at_same_time = []
    lock = threading.Lock()
    currently_running = []

    class OverlapCheckTask(Task):
        def __init__(self, name):
            super().__init__()
            self.name = name

        def start(self):
            with lock:
                currently_running.append(self.name)
                active_at_same_time.append(len(currently_running))
            time.sleep(0.05)
            with lock:
                currently_running.remove(self.name)
            ran.append(self.name)

    done = threading.Event()

    def on_update(states):
        if all(s.finished for s in states) and len(states) == 3:
            done.set()

    mgr = TaskManager(on_update=on_update)
    for name in ('T1', 'T2', 'T3'):
        mgr.add_task(OverlapCheckTask(name))

    done.wait(timeout=5)
    mgr.close()

    assert max(active_at_same_time) == 1, "Tasks ran concurrently"


def test_dismiss_removes_task_from_states():
    ran = []
    done = threading.Event()

    def on_update(states):
        if any(s.finished for s in states):
            done.set()

    mgr = TaskManager(on_update=on_update)
    task = mgr.add_task(RecordingTask('X', ran))
    done.wait(timeout=3)

    assert any(s.id == task.id for s in mgr.get_states())
    mgr.dismiss_task(task.id)
    assert all(s.id != task.id for s in mgr.get_states())
    mgr.close()


def test_stop_cancels_pending_chunks():
    ran = []

    class CancellableTask(Task):
        def __init__(self):
            super().__init__()
            self.name = 'cancellable'

        def start(self):
            for i in range(100):
                if self._cancel_event.is_set():
                    return
                ran.append(i)
                time.sleep(0.01)

    mgr = TaskManager()
    mgr.add_task(CancellableTask())
    time.sleep(0.05)
    mgr.stop_task('CancellableTask#1')
    mgr.close()

    assert len(ran) < 100
