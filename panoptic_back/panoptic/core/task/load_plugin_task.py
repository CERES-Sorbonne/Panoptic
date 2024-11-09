from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from panoptic.core.plugin.plugin_project_interface import PluginProjectInterface
from panoptic.models import PluginKey

if TYPE_CHECKING:
    from panoptic.core.project.project import Project
from panoptic.core.task.task import Task

import importlib.util
import sys


def import_module_from_path(module_name, module_path):
    # Append the folder path to sys.path
    sys.path.append(module_path)

    # Construct the spec for the module
    spec = importlib.util.spec_from_file_location(module_name, module_path)

    # Import the module
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    # Finalize the loading
    spec.loader.exec_module(module)

    # Remove the path from sys.path to keep things clean
    # sys.path.remove(module_path)

    return module


class LoadPluginTask(Task):
    def __init__(self, project: Project, plugin_key: PluginKey):
        super().__init__()
        self.name = 'Load Plugin'
        self.project = project
        self.plugin_key = plugin_key

    async def run(self):
        path = self.plugin_key.path
        name = self.plugin_key.name
        file_path = path
        if not path.endswith('__init__.py'):
            file_path = str(Path(path) / '__init__.py')
        plugin_module = await self._async(import_module_from_path, name, file_path)
        project_interface = PluginProjectInterface(self.project)
        plugin = plugin_module.plugin_class(project=project_interface, plugin_path=path, name=name)
        await plugin.start()
        self.project.plugins.append(plugin)

    async def run_if_last(self):
        plugins = await self.project.plugins_info()

        self.project.plugin_loaded = True
        self.project.ui.update_counter.action += 1
        self.project.ui.plugins = plugins
        self.project.ui.actions = [a.description for a in self.project.action.actions.values()]
