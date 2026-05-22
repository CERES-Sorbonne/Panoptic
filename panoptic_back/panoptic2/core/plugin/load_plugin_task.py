"""LoadPluginTask — imports and starts plugins during project startup."""
from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from panoptic.core.databases.panoptic.models import PluginKey
from panoptic2.core.task.task import Task

if TYPE_CHECKING:
    from panoptic2.core.project.project import Project2

logger = logging.getLogger(__name__)


class LoadPluginTask(Task):
    def __init__(self, project: Project2, plugin_keys: list[PluginKey]):
        super().__init__()
        self.name = 'Load Plugins'
        self._project    = project
        self._plugin_keys = plugin_keys
        self.state.total = len(plugin_keys)

    def start(self) -> None:
        self.state.running = True
        self._notify()

        for key in self._plugin_keys:
            if self._cancel_event.is_set():
                break
            try:
                module = _import_plugin(key)
                interface = self._project.make_plugin_interface(key.id)
                plugin = module.plugin_class(
                    project=interface,
                    plugin_path=key.install_path,
                    name=key.id,
                )
                plugin.start()
                self._project.add_plugin(plugin)
                self.state.done += 1
                logger.info(f'Loaded plugin {key.id!r}')
            except Exception:
                logger.exception(f'Failed to load plugin {key.id!r}')
            self._notify()

        self.state.running  = False
        self.state.finished = True
        self._finished_event.set()
        self._notify()


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------

def _import_plugin(key: PluginKey):
    """Import a plugin module from pip package or local path."""
    path = key.install_path

    # pip-installed package: import by module name (same as install_path for pip)
    init = Path(path) / '__init__.py'
    if not init.exists():
        module = importlib.import_module(path)
        return module

    # local / git path: load from filesystem
    module_name = key.id
    file_path = str(init)

    sys.path.insert(0, str(Path(path).parent))

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Could not load plugin from {file_path}')

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
