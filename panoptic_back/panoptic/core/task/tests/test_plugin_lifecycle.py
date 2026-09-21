"""Stopping and restarting a plugin inside a real Project.

Run from panoptic_back/:
    .venv/bin/python -m pytest panoptic/core/task/tests
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from panoptic.core.databases.panoptic.models import PluginKey
from panoptic.core.project.project import Project

PLUGIN_SOURCE = textwrap.dedent('''
    import threading
    from panoptic.core.plugin.plugin import APlugin
    from panoptic.core.task.task import Task

    EVENTS = []

    class Forever(Task):
        """Never checks is_cancelled(): the TaskManager has to interrupt it."""
        def __init__(self):
            super().__init__()
            self.started = threading.Event()

        def start(self):
            self.started.set()
            while True:
                threading.Event().wait(0.01)

    class FakePlugin(APlugin):
        def __init__(self, name, project, plugin_path):
            super().__init__(name=name, project=project, plugin_path=plugin_path)
            self.project.on_import_complete(lambda root: EVENTS.append(('import', self.name)))
            self.add_action_easy(self.hello, ['execute'])
            self.task = None

        def hello(self, ctx):
            """Say hello"""
            return None

        def _start(self):
            EVENTS.append(('start', self.name))
            self.task = self.project.add_task(Forever())

        def _stop(self):
            EVENTS.append(('stop', self.name))

    plugin_class = FakePlugin
''')

PLUGIN_ID = 'fake_lifecycle_plugin'


def wait_until(predicate, timeout: float = 10.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


class PluginLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        plugin_dir = Path(self.tmp.name) / 'plugins' / PLUGIN_ID
        plugin_dir.mkdir(parents=True)
        (plugin_dir / '__init__.py').write_text(PLUGIN_SOURCE)
        key = PluginKey(id=PLUGIN_ID, install_path=str(plugin_dir), source_type='local',
                        source_path=str(plugin_dir))
        self.project = Project(Path(self.tmp.name) / 'project', plugin_keys=[key])
        self.project.task_manager._stop_grace = 0.2
        self.project.task_manager._interrupt_grace = 0.2
        self.project.start()
        self.assertTrue(wait_until(lambda: self.project.is_plugin_loaded(PLUGIN_ID)))
        self.events = sys.modules[PLUGIN_ID].EVENTS
        self.events.clear()

    def tearDown(self):
        self.project.close()
        sys.modules.pop(PLUGIN_ID, None)
        self.tmp.cleanup()

    def _plugin(self):
        return next(p for p in self.project.plugins if p.name == PLUGIN_ID)

    def _action_ids(self):
        return [i for i, a in self.project.action.actions.items() if a.owner == PLUGIN_ID]

    def test_stop_removes_everything_the_plugin_registered(self):
        task = self._plugin().task
        self.assertTrue(task.started.wait(5))
        self.assertEqual(task.state.owner, PLUGIN_ID)
        self.assertEqual(self._action_ids(), [f'{PLUGIN_ID}.hello'])

        self.assertTrue(self.project.unload_plugin(PLUGIN_ID))
        self.assertFalse(self.project.is_plugin_loaded(PLUGIN_ID))
        self.assertEqual(self._action_ids(), [])
        self.assertIn(('stop', PLUGIN_ID), self.events)

        self.project._trigger_import_complete(None)
        self.assertNotIn(('import', PLUGIN_ID), self.events)

        # Its task ignores the stop flag, so it is interrupted
        self.assertTrue(wait_until(lambda: task.state.finished, 5))
        self.assertTrue(task.state.cancelled)

        descriptions = self.project.get_plugin_descriptions()
        self.assertEqual([(d.name, d.running) for d in descriptions], [(PLUGIN_ID, False)])

    def test_restart_does_not_duplicate_callbacks(self):
        self.project.unload_plugin(PLUGIN_ID)
        self.project.load_plugin(PLUGIN_ID)
        self.assertTrue(wait_until(lambda: self.project.is_plugin_loaded(PLUGIN_ID)))
        self.assertEqual(self._action_ids(), [f'{PLUGIN_ID}.hello'])

        # The module is executed again on load, so its EVENTS list is a new one
        events = sys.modules[PLUGIN_ID].EVENTS
        events.clear()
        self.project._trigger_import_complete(None)
        self.assertEqual(events, [('import', PLUGIN_ID)])

    def test_removing_the_plugin_key_stops_it(self):
        self.project.set_plugin_keys([])
        self.assertFalse(self.project.is_plugin_loaded(PLUGIN_ID))
        self.assertEqual(self.project.get_plugin_descriptions(), [])
        with self.assertRaises(KeyError):
            self.project.load_plugin(PLUGIN_ID)


if __name__ == '__main__':
    unittest.main()
