from pathlib import Path

from pydantic import BaseModel

from panoptic.core.project.project import Project
from panoptic.models import ActionContext, PropertyRequest
from panoptic.plugin import Plugin


# class TestParams(BaseModel):
#     eau: str = None
#     terre: int = 0
#     feu: float = 2.4
#     air: Path = None


class DefaultPlugin(Plugin):
    def __init__(self, project: Project, plugin_path: str):
        super().__init__(name='TestPlugin1', project=project, plugin_path=plugin_path)
        # self.params = TestParams()

        self.project.action.easy_add(self, self.convert_to_tags, ['group_images'])

    async def convert_to_tags(self, context: ActionContext, source: PropertyRequest):
        print(self.name, source)
