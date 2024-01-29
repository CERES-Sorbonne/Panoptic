import inspect
import logging
from pathlib import Path
from typing import Any, Awaitable, List

from panoptic.models import Files, Instances, Images, Vectors, Properties, ActionContext
from panoptic.plugin import Plugin
from panoptic.utils import AsyncCallable


def get_params(f):
    signature = inspect.signature(f)
    parameters = signature.parameters
    return {k: parameters[k].annotation for k in parameters}


possible_dependencies = [Files, Instances, Images, Vectors, Properties]
possible_inputs = [int, str, List[str], bool, Path]


def get_dependencies(f):
    types = get_params(f)
    return {t: types[t] for t in types if types[t] in possible_dependencies}


def get_inputs(f):
    types = get_params(f)
    return {t: types[t] for t in types if types[t] in possible_inputs}


def verify_dependencies(f: AsyncCallable, required: List):
    dependencies = get_dependencies(f).values()

    if Instances in dependencies and Images in dependencies:
        return False

    count = 0
    required_nb = len(required)
    if Instances in required and Images in required:
        required_nb -= 1

    for r in required:
        if r in dependencies:
            count += 1

    return count == required_nb


class Action:
    def __init__(self, id_: str, source: Any, function: AsyncCallable):
        self.id = id_
        self.source = source
        self._function = function

    async def call(self, *args, **kwargs):
        return await self._function(*args, **kwargs)


class ProjectAction:
    def __init__(self, required: List):
        self._possible_actions: List[Action] = []
        self._selected_action = None
        self._required = required

    def can_call(self):
        return self._selected_action is not None

    def register(self, source: Plugin, function: AsyncCallable):
        id_ = source.name + '.' + function.__name__
        action = Action(source=source, function=function, id_=id_)
        self._possible_actions.append(action)
        if not self.can_call():
            self._selected_action = 0

    async def call(self, context: ActionContext):
        action = self._possible_actions[self._selected_action]
        return await action.call(context, **context.ui_inputs)


class ProjectActions:
    def __init__(self):
        self.filter_images = ProjectAction([Instances, Images])
        self.group_images = ProjectAction([Instances, Images])
        self.find_images = ProjectAction([Instances, Images])
        self.action_images = ProjectAction([Instances, Images])
        self.action_group = ProjectAction([Instances, Images])
        self.import_properties = ProjectAction([Files])
        self.export_properties = ProjectAction([Instances, Images])
