from pathlib import Path

from pydantic import BaseModel

from panoptic.core.project.project import Project
from panoptic.models import ActionContext, PropertyId, PropertyType, PropertyMode, InstancePropertyValue, DbCommit
from panoptic.models.results import ActionResult
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

        self.project.action.easy_add(self, self.convert_to_tags, ['group'])

    async def convert_to_tags(self, context: ActionContext, source: PropertyId):
        prop = await self.project.db.add_property('PluginProp', PropertyType.string)
        values = [InstancePropertyValue(property_id=prop.id, instance_id=i, value='I LOVE PLUGINS') for i in context.instance_ids]
        commit = DbCommit(instance_values=values, properties=[prop])
        commit = await self.project.undo_queue.do(commit)
        return ActionResult(commit=commit)
