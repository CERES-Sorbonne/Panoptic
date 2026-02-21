import asyncio
import importlib.util
import sys
import logging
from pathlib import Path
from panoptic.core.task.task import Task
from panoptic.models import PluginKey, PluginType

logger = logging.getLogger('LoadPluginTask')


class LoadPluginTask(Task):
    """
    Sequentially loads plugins. 
    Simplifies the lifecycle to a single start() loop without batching overhead.
    """

    def __init__(self, plugin_keys: list[PluginKey], enable_watch: bool = True):
        super().__init__()
        self.name = 'Load Plugin'
        self._plugin_keys = plugin_keys
        self.enable_watch = enable_watch
        self.state.total = len(plugin_keys)

    async def start(self):
        self.state.running = True
        self._notify()

        for key in self._plugin_keys:
            if self._cancel_event.is_set():
                break

            try:
                # 1. Import (Blocking I/O moved to thread)
                path, module = await asyncio.to_thread(self._import_plugin, key)

                # 2. Instantiate and Start (Back on Event Loop)
                plugin = module.plugin_class(
                    project=self._project,
                    plugin_path=path,
                    name=key.name
                )

                self._project.add_plugin(plugin)
                await plugin.start()

                # 3. Handle Watcher
                if self.enable_watch and hasattr(self._project, 'plugin_watcher'):
                    self._project.plugin_watcher.add_plugin_watch(key, path)

                # 4. Progress
                self.state.done += 1
                self._project.on.sync.emitProjectState(self._project.get_state())
                self._notify()

            except Exception as e:
                logger.error(f"Failed to load plugin {key.name}: {e}", exc_info=True)

        self.state.running = False
        self.state.finished = True
        self._finished_event.set()
        self._notify()

    def _import_plugin(self, key: PluginKey):
        """Standard blocking import logic, now simplified."""
        if key.type == PluginType.pip:
            module = importlib.import_module(key.source)
            path = module.__path__[0]
            return path, module

        # Local Path loading
        path = key.path
        file_path = path if path.endswith('__init__.py') else str(Path(path) / '__init__.py')

        # Use a unique module name to avoid collision
        module_name = key.name
        sys.path.append(str(Path(path).parent))  # Ensure parent is in path for relative imports

        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not find plugin at {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        return path, module