import inspect
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


possible_inputs = [int, float, str, List[str], bool, Path, PropertyId]


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
    return [ParamDescription(name=t, type=to_str_type(types[t][0]), default_value=types[t][1],
                             description=get_param_description(f, t))
            for t in types if types[t][0] in possible_inputs]


def get_function_description(source: APlugin, function: AsyncCallable):
    name = function.__name__
    function_id = f'{source.name}.{name}'
    description = function.__doc__
    if description and '@' in description:
        description = description[0: description.index('@')]
    params = get_params_description(function)
    return FunctionDescription(id=function_id, name=name, description=description, params=params)


class Action:
    def __init__(self, function: AsyncCallable, description: FunctionDescription):
        self.id = description.id
        self._function = function
        self.description = description

    async def call(self, ctx: ActionContext):
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

    async def call(self, function_id: str, ctx: ActionContext):
        return await self.actions[function_id].call(ctx)