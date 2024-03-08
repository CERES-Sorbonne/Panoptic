from pathlib import Path

from pydantic import BaseModel

from panoptic.core.project.project import Project
from panoptic.models import ActionContext
from panoptic.plugin import Plugin


class TestParams(BaseModel):
    eau: str = None
    terre: int = 0
    feu: float = 2.4
    air: Path = None


class PluginBase(Plugin):
    def __init__(self, project: Project, plugin_path: str):
        super().__init__(name='TestPlugin1', project=project, plugin_path=plugin_path)
        self.params = TestParams()

        self.project.action.group_images.register(self, self.firefly)

    async def firefly(self, context: ActionContext, damage: int):
        pass
