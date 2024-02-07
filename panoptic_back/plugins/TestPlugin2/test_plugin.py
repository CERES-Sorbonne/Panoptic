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


class TestPlugin2(Plugin):
    def __init__(self, project: Project, plugin_path: str):
        super().__init__(name='TestPlugin2', project=project, plugin_path=plugin_path)
        self.params = TestParams()

        self.project.action.group_images.register(self, self.firefly)
        self.project.action.group_images.register(self, self.earthquake)
        self.project.action.group_images.register(self, self.tsunami)
        self.project.action.group_images.register(self, self.tornado)

        self.project.action.action_images.register(self, self.firefly)
        self.project.action.action_images.register(self, self.earthquake)
        self.project.action.action_images.register(self, self.tsunami)
        self.project.action.action_images.register(self, self.tornado)

        self.project.action.find_images.register(self, self.firefly)
        self.project.action.find_images.register(self, self.earthquake)
        self.project.action.find_images.register(self, self.tsunami)
        self.project.action.find_images.register(self, self.tornado)

        self.project.action.filter_images.register(self, self.firefly)
        self.project.action.filter_images.register(self, self.earthquake)
        self.project.action.filter_images.register(self, self.tsunami)
        self.project.action.filter_images.register(self, self.tornado)

        self.project.action.export_properties.register(self, self.firefly)
        self.project.action.export_properties.register(self, self.earthquake)
        self.project.action.export_properties.register(self, self.tsunami)
        self.project.action.export_properties.register(self, self.tornado)

        self.project.action.import_properties.register(self, self.firefly)
        self.project.action.import_properties.register(self, self.earthquake)
        self.project.action.import_properties.register(self, self.tsunami)
        self.project.action.import_properties.register(self, self.tornado)

    async def firefly(self, context: ActionContext, damage: int):
        pass

    async def earthquake(self, context: ActionContext, radius: float):
        pass

    async def tsunami(self, context: ActionContext, name: str):
        pass

    async def tornado(self, context: ActionContext, path: Path):
        pass