"""PluginWatcher — hot-reloads plugins when their source files change.

Enabled by setting the PANOPTIC_WATCH_PLUGINS=1 environment variable.
Each changed plugin is cleared from the Python module cache, removed from
the project's plugin list, and re-loaded via a fresh LoadPluginTask.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from watchfiles import awatch

from panoptic.core.databases.panoptic.models import PluginKey

if TYPE_CHECKING:
    from panoptic.core.project.project import Project

WATCH_PLUGINS: bool = os.getenv('PANOPTIC_WATCH_PLUGINS', '0') == '1'

print(f'[PluginWatcher] PANOPTIC_WATCH_PLUGINS={os.getenv("PANOPTIC_WATCH_PLUGINS")!r} → WATCH_PLUGINS={WATCH_PLUGINS}')

_IGNORE = ('__pycache__', '.pyc', '.pyo', '.pyd', '.swp', '.tmp', '~', '.git', '.DS_Store')


class PluginWatcher:
    def __init__(self, project: Project) -> None:
        self._project = project
        self._watching: dict[str, PluginKey] = {}  # watched dir path → key

    def watch(self, key: PluginKey) -> None:
        path = Path(key.install_path)
        if path.is_file():
            path = path.parent
        print(f'[PluginWatcher] watch({key.id!r}): install_path={key.install_path!r} source_type={key.source_type!r} exists={path.exists()}')
        if path.exists():
            self._watching[str(path)] = key
            print(f'[PluginWatcher] registered {key.id!r} → {path}')
        else:
            print(f'[PluginWatcher] SKIPPED {key.id!r} — path does not exist: {path}')

    async def run(self) -> None:
        if not self._watching:
            print('[PluginWatcher] no paths to watch — watcher not started')
            return
        print(f'[PluginWatcher] started, watching: {list(self._watching.keys())}')
        try:
            async for changes in awatch(*self._watching.keys()):
                await self._handle_changes(changes)
        except asyncio.CancelledError:
            print('[PluginWatcher] stopped (cancelled)')
        except Exception as e:
            print(f'[PluginWatcher] ERROR in run(): {e}')
            import traceback; traceback.print_exc()

    async def _handle_changes(self, changes: set[tuple]) -> None:
        to_reload: dict[str, PluginKey] = {}
        for _, file_path in changes:
            if any(p in file_path for p in _IGNORE):
                continue
            key = next(
                (k for watched, k in self._watching.items() if file_path.startswith(watched)),
                None,
            )
            if key:
                print(f'[PluginWatcher] change detected in {key.id!r}: {Path(file_path).name}')
                to_reload[key.id] = key

        if not to_reload:
            return

        await asyncio.sleep(0.3)  # debounce: wait for editor to finish writing
        for key in to_reload.values():
            await self._reload(key)

    async def _reload(self, key: PluginKey) -> None:
        print(f'[PluginWatcher] reloading {key.id!r} ...')
        try:
            _clear_module_cache(key)
            self._project.plugins = [p for p in self._project.plugins if p.name != key.id]

            from panoptic.core.plugin.load_plugin_task import LoadPluginTask
            self._project.add_task(LoadPluginTask(self._project, [key]))
            print(f'[PluginWatcher] reload task queued for {key.id!r}')
        except Exception as e:
            print(f'[PluginWatcher] reload ERROR for {key.id!r}: {e}')
            import traceback; traceback.print_exc()


def _clear_module_cache(key: PluginKey) -> None:
    module_name = key.id
    to_remove = [n for n in sys.modules if n == module_name or n.startswith(f'{module_name}.')]
    for name in to_remove:
        del sys.modules[name]
    if to_remove:
        print(f'[PluginWatcher] cleared {len(to_remove)} cached module(s) for {key.id!r}')
