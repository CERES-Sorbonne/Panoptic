import inspect
from enum import Enum
from pathlib import Path
from typing import List

from panoptic.models import ActionContext, FunctionDescription, ParamDescription, PropertyId
from panoptic.core.plugin.plugin import APlugin
from panoptic.utils import AsyncCallable, to_str_type


def get_params(f):
    signature = inspect.signature(f)
    parameters = signature.parameters

    res = {}
    for p in parameters:
        param = parameters[p]
        type_ = param.annotation
        default = param.default
        if default is inspect.Parameter.empty:
            default = None
        res[p] = (type_, default)
    return res


possible_inputs = [to_str_type(t) for t in [int, float, str, bool, Path, PropertyId, Enum]]


def get_param_description(f: AsyncCallable, param_name: str):
    doc: str = f.__doc__
    token = f'@{param_name}: '
    if not doc or token not in doc:
        return None

    token_start = doc.index(token)
    start = token_start + len(token)
    if '@' in doc[start:]:
        end = doc.index('@', start)
        return doc[start:end]
    return doc[start:]


def get_params_description(f: AsyncCallable) -> List[ParamDescription]:
    types = get_params(f)
    res = []
    for t in types:
        tt = types[t]
        str_type = to_str_type(tt[0])
        if str_type not in possible_inputs:
            continue

        desc = ParamDescription(name=t,
                                type=str_type,
                                default_value=tt[1],
                                description=get_param_description(f, t))
        if str_type == 'enum':
            desc.possible_values = [e.value for e in tt[0]]
        res.append(desc)
    return res


def get_function_description(source: APlugin, function: AsyncCallable):
    name = function.__name__
    function_id = f'{source.name}.{name}'
    description = function.__doc__
    if description and '@' in description:
        description = description[0: description.index('@')]
    if description:
        description = description.rstrip('\n')
        description = description.lstrip('\n')
        description = description.strip()
    params = get_params_description(function)
    return FunctionDescription(id=function_id, name=name, description=description, params=params)


class Action:
    def __init__(self, function: AsyncCallable, description: FunctionDescription):
        self.id = description.id
        self._function = function
        self.description = description

    async def call(self, ctx: ActionContext):
        params = get_params(self._function)
        for desc in self.description.params:
            if desc.type != 'enum':
                continue
            param_type = [params[p][0] for p in params if p == desc.name][0]
            if not ctx.ui_inputs.get(desc.name):
                continue
            ctx.ui_inputs[desc.name] = param_type(ctx.ui_inputs[desc.name])

        return await self._function(ctx, **ctx.ui_inputs)


class ProjectActions:
    def __init__(self):
        self.actions: dict[str, Action] = {}

    def add(self, function: AsyncCallable, description: FunctionDescription):
        self.actions[description.id] = Action(function, description)

    def easy_add(self, source: APlugin, function: AsyncCallable, hooks: list[str] = None):
        description = get_function_description(source, function)
        if hooks:
            description.hooks = hooks
        self.add(function, description)
        return description

    async def call(self, function_id: str, ctx: ActionContext):
        return await self.actions[function_id].call(ctx)
