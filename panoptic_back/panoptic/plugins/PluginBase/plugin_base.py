from pydantic import BaseModel
from panoptic.core.plugin.plugin import Plugin
from panoptic.core.plugin.plugin_project_interface import PluginProjectInterface
from panoptic.models import ActionContext, PropertyId


class TestParams(BaseModel):
    base_text: str = None
    base_number: int = 0
    base_floating: float = 2.4
    base_prop: PropertyId = 1


class PluginBase(Plugin):
    def __init__(self, project: PluginProjectInterface, plugin_path: str):
        super().__init__(name='TestPlugin1', project=project, plugin_path=plugin_path)
        self.params = TestParams()

        self.add_action_easy(self.test_function, ['execute'])

    async def test_function(self, context: ActionContext, number: int, text: str, floating: float, prop: PropertyId):
        print(self.params)
        print(context)
        print(number, text, floating, prop)

