from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from panoptic.core.project.project import Project
from panoptic.core.task.task import Task


class LoadPluginTask(Task):
    def __init__(self, project: Project):
        super().__init__()
        self.name = 'Load Plugin'
        self.project = project

    async def run(self):
        FaissPlugin = await self._async(self.loadFaiss)
        plugin = FaissPlugin(self.project)
        await plugin.start()
        self.project.plugin = plugin

    async def run_if_last(self):
        self.project.plugin_loaded = True

    @staticmethod
    def loadFaiss():
        from panoptic.FaissPlugin.faiss_plugin import FaissPlugin
        return FaissPlugin