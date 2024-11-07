from pydantic import BaseModel
from panoptic.core.plugin.plugin import APlugin
from panoptic.core.plugin.plugin_project_interface import PluginProjectInterface
from panoptic.models import ActionContext, PropertyId
from panoptic.models.results import ActionResult


class TestParams(BaseModel):
    base_text: str = None
    base_number: int = 0
    base_floating: float = 2.4
    base_prop: PropertyId = 1


class PluginBase(APlugin):
    def __init__(self, project: PluginProjectInterface, plugin_path: str, name: str):
        super().__init__(name=name, project=project, plugin_path=plugin_path)
        self.params = TestParams()

        self.add_action_easy(self.test_function, ['execute'])

    async def test_function(self, context: ActionContext, number: int, text: str, floating: float, prop: PropertyId):
        print(self.params)
        print(context)
        print(number, text, floating, prop)
        return ActionResult()

