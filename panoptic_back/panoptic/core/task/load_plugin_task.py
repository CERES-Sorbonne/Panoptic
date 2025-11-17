import importlib.util
import os
import sys
from pathlib import Path

from panoptic.core.task.task import Task
from panoptic.models import PluginKey, PluginType


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
    def __init__(self, plugin_key: PluginKey, enable_watch: bool = True):
        super().__init__()
        self.name = 'Load Plugin'
        self.plugin_key = plugin_key
        self.enable_watch = enable_watch

    async def run(self):
        plugin_type = self.plugin_key.type
        path = self.plugin_key.path
        name = self.plugin_key.name

        if plugin_type == PluginType.pip:
            plugin_module = await self.run_async(importlib.import_module, self.plugin_key.source)
            path = plugin_module.__path__[0]
        else:
            file_path = path
            if not path.endswith('__init__.py'):
                file_path = str(Path(path) / '__init__.py')
            plugin_module = await self.run_async(import_module_from_path, name, file_path)
        plugin = plugin_module.plugin_class(project=self._project, plugin_path=path, name=name)
        self._project.add_plugin(plugin)
        await plugin.start()

        if self.enable_watch and hasattr(self._project, 'plugin_watcher'):
            self._project.plugin_watcher.add_plugin_watch(self.plugin_key, path)

        self._project.on.sync.emitProjectState(self._project.get_state())
