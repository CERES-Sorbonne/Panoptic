import asyncio
import os
from pathlib import Path
from typing import Dict, Set
from watchfiles import awatch, Change
import sys

from panoptic.core.task.load_plugin_task import LoadPluginTask
from panoptic.models import PluginType, PluginKey


class PluginWatcher:
    """Surveille les changements dans les dossiers de plugins et les recharge automatiquement."""

    def __init__(self, project):
        self.watching = True if os.getenv('PANOPTIC_WATCH_PLUGINS', '0') == '1' else False
        self._project = project
        self._watching_paths: Dict[str, PluginKey] = {}  # path -> plugin_key
        self._watcher_task = None
        self._running = False
        self._reload_lock = asyncio.Lock()  # Lock pour éviter les rechargements concurrents



    def add_plugin_watch(self, plugin_key: PluginKey, path: str):
        """Ajoute un plugin à surveiller."""
        if path in self._watching_paths:
            return
        # Normalise le chemin pour pointer vers le dossier du plugin
        plugin_path = Path(path)
        if plugin_path.is_file():
            plugin_path = plugin_path.parent

        self._watching_paths[str(plugin_path)] = plugin_key
        print(f"Watching plugin: {plugin_key.name} at {plugin_path}")

    async def start(self):
        """Démarre la surveillance des plugins."""
        if self._running:
            return

        self._running = True
        self._watcher_task = asyncio.create_task(self._watch_plugins())
        print("Plugin watcher started")

    async def stop(self):
        """Arrête la surveillance des plugins."""
        self._running = False
        if self._watcher_task:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
        print("Plugin watcher stopped")

    async def _watch_plugins(self):
        """Boucle principale de surveillance."""
        if not self._watching_paths:
            print("No plugins to watch")
            return

        try:
            async for changes in awatch(*self._watching_paths.keys(), stop_event=None):
                await self._handle_changes(changes)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in plugin watcher: {e}")

    async def _handle_changes(self, changes: Set[tuple]):
        """Gère les changements détectés dans les fichiers."""
        plugins_to_reload = set()

        for change_type, file_path in changes:
            file_path = Path(file_path)

            # Ignore les fichiers temporaires et __pycache__
            if self._should_ignore_file(file_path):
                continue

            # Trouve le plugin concerné par ce changement
            plugin_key = self._find_plugin_for_path(file_path)
            if plugin_key:
                change_name = self._get_change_name(change_type)
                print(f"{change_name}: {file_path.name} in plugin '{plugin_key.name}'")
                plugins_to_reload.add(plugin_key)

        # Recharge les plugins modifiés (avec un petit délai pour éviter les recharges multiples)
        if plugins_to_reload:
            await asyncio.sleep(0.5)  # Débounce
            for plugin_key in plugins_to_reload:
                await self._reload_plugin(plugin_key)

    def _should_ignore_file(self, file_path: Path) -> bool:
        """Détermine si un fichier doit être ignoré."""
        ignore_patterns = [
            '__pycache__',
            '.pyc',
            '.pyo',
            '.pyd',
            '.swp',
            '.tmp',
            '~',
            '.git',
            '.DS_Store'
        ]

        path_str = str(file_path)
        return any(pattern in path_str for pattern in ignore_patterns)

    def _find_plugin_for_path(self, file_path: Path) -> PluginKey | None:
        """Trouve le plugin correspondant à un chemin de fichier."""
        for watched_path, plugin_key in self._watching_paths.items():
            if str(file_path).startswith(watched_path):
                return plugin_key
        return None

    def _get_change_name(self, change_type: Change) -> str:
        """Convertit le type de changement en texte lisible."""
        change_names = {
            Change.added: "Added",
            Change.modified: "Modified",
            Change.deleted: "Deleted"
        }
        return change_names.get(change_type, "Changed")

    async def _reload_plugin(self, plugin_key: PluginKey):
        """Recharge un plugin."""
        print(f"Reloading plugin: {plugin_key.name}")

        try:
            # Nettoie les modules en cache
            self._clear_module_cache(plugin_key)

            # Recharge le plugin
            load_task = LoadPluginTask(plugin_key)
            self._project.task_queue.add_task(load_task)

            print(f"Plugin '{plugin_key.name}' reloaded successfully")

        except Exception as e:
            print(f"Error reloading plugin '{plugin_key.name}': {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def _clear_module_cache(plugin_key: PluginKey):
        """Nettoie les modules du plugin du cache de Python."""
        # Pour les plugins pip
        if plugin_key.type == PluginType.pip:
            module_name = plugin_key.source
            modules_to_remove = [
                name for name in sys.modules
                if name == module_name or name.startswith(f"{module_name}.")
            ]
        # Pour les plugins locaux
        else:
            module_name = plugin_key.name
            modules_to_remove = [
                name for name in sys.modules
                if name == module_name or name.startswith(f"{module_name}.")
            ]

        for module_name in modules_to_remove:
            del sys.modules[module_name]
