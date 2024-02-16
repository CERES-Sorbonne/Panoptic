from __future__ import annotations

from typing import List, Any, Dict
from typing import TYPE_CHECKING

from panoptic.models import PluginBaseParamsDescription, FunctionDescription, PluginDescription, PluginDefaultParams
from panoptic.utils import get_model_params_description

if TYPE_CHECKING:
    from panoptic.core.project.project import Project


class Plugin:
    def __init__(self, name: str, project: Project, plugin_path: str):
        self.params: Any | None = None
        self.name: str = name
        self.project = project
        self.registered_functions: List[FunctionDescription] = []
        self.path = plugin_path

    async def start(self):
        db_defaults = await self.project.db.get_raw_db().get_plugin_default_params(self.name)
        self.update_default_values(db_defaults)

    def update_default_values(self, params: PluginDefaultParams):
        if not self.params:
            return

        for param in params.base:
            if params.base[param]:
                setattr(self.params, param, params.base[param])

    def _get_param_description(self, db_base: Dict[str, Any]):
        if not self.params:
            return PluginBaseParamsDescription()
        description = self.params.__doc__
        if description and '@' in description:
            description = description[0: description.index('@')]

        params = get_model_params_description(self.params)
        # print('params', params)
        for p in params:
            if p.name in db_base and db_base[p.name]:
                p.default_value = db_base[p.name]
        return PluginBaseParamsDescription(description=description, params=params)

    async def get_description(self):
        name = self.name
        description = self.__doc__
        path = self.path

        defaults = PluginDefaultParams(name=name)
        db_defaults = await self.project.db.get_raw_db().get_plugin_default_params(plugin_name=name)

        base_params = self._get_param_description(db_defaults.base)
        # print(base_params)

        for param in base_params.params:
            defaults.base[param.name] = param.default_value

        for function in self.registered_functions:
            defaults.functions[function.name] = {}
            for param in function.params:
                defaults.functions[function.name][param.name] = param.default_value
                if function.name in db_defaults.functions and param.name in db_defaults.functions[function.name]:
                    defaults.functions[function.name][param.name] = db_defaults.functions[function.name][param.name]

        res = PluginDescription(name=name, description=description, path=path, base_params=base_params,
                                registered_functions=self.registered_functions, defaults=defaults)
        return res
