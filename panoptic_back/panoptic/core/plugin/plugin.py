from __future__ import annotations

from abc import ABC
from typing import List, Any
from typing import TYPE_CHECKING

from pydantic import BaseModel

from panoptic.core.plugin.plugin_project_interface import PluginProjectInterface
from panoptic.models import PluginBaseParamsDescription, FunctionDescription, PluginDescription
from panoptic.utils import get_model_params_description, AsyncCallable

if TYPE_CHECKING:
    from panoptic.core.project.project import Project


def assign_attributes(target: BaseModel, source):
    if not target:
        return
    target = target.copy(update=source)
    return target


class APlugin(ABC):
    def __init__(self, name: str, project: PluginProjectInterface, plugin_path: str):
        self.params: Any | None = None
        self.name: str = name
        self._project = project.get_project()
        self.project = project
        self.registered_functions: List[FunctionDescription] = []
        self.path = plugin_path
        self.base_key = f'{self.name}.base'

    async def start(self):
        db_defaults = await self._project.db.get_plugin_data(self.base_key)
        self.params = assign_attributes(self.params, db_defaults)

    async def update_params(self, params: Any):
        self.params = assign_attributes(self.params, params)
        await self._project.db.set_plugin_data(self.base_key, self.params.dict())
        return self.params

    def add_action(self, function: AsyncCallable, description: FunctionDescription):
        self._project.action.add(function, description)

    def add_action_easy(self, function: AsyncCallable, hooks: list[str] = None):
        source = self
        self._project.action.easy_add(source, function, hooks)

    def _get_param_description(self):
        if not self.params:
            return PluginBaseParamsDescription()
        description = self.params.__doc__
        if description and '@' in description:
            description = description[0: description.index('@')]

        params = get_model_params_description(self.params)
        for p in params:
            p.id = p.name
            p.default_value = self.params.__dict__[p.id]
        return PluginBaseParamsDescription(description=description, params=params)

    async def get_description(self):
        name = self.name
        description = self.__doc__
        path = self.path

        base_params = self._get_param_description()

        res = PluginDescription(name=name, description=description, path=path, base_params=base_params,
                                registered_functions=self.registered_functions)
        return res
