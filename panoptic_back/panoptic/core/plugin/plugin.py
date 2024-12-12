from __future__ import annotations

import json
import os
from abc import ABC
from pathlib import Path
from typing import List, Any
from typing import TYPE_CHECKING

from pydantic import BaseModel

from panoptic.core.plugin.plugin_project_interface import PluginProjectInterface
from panoptic.models import PluginBaseParamsDescription, FunctionDescription, PluginDescription, PropertyType, \
    PropertyMode
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
        self.slug = "_".join(self.name.split(' ')).lower()
        self.data_path = Path(self.project.base_path) / 'plugin_data' / self.slug
        self.data_path.mkdir(parents=True, exist_ok=True)

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
        return self._project.action.easy_add(source, function, hooks)

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

    async def get_or_create_property(self, property_name, property_type: PropertyType, property_mode: PropertyMode):
        properties = await self.project.get_properties()
        new_prop = None
        for prop in properties:
            if prop.name == property_name and prop.type == property_type and prop.mode == property_mode:
                new_prop = prop
                break
        if not new_prop:
            if property_type is not None and property_mode is not None:
                new_prop = self.project.create_property(property_name, property_type, property_mode)
            else:
                raise ValueError("No existing property found with this name and no property_type and mode provided to create one")
        return new_prop
