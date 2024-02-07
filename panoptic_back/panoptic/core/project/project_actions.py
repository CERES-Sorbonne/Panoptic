import inspect
import logging
from pathlib import Path
from typing import Any, List

from panoptic.models import ActionContext, FunctionDescription, ParamDescription, ActionDescription, ActionUpdate
from panoptic.plugin import Plugin
from panoptic.utils import AsyncCallable, to_str_type


def get_params(f):
    signature = inspect.signature(f)
    parameters = signature.parameters
    return {k: parameters[k].annotation for k in parameters}


possible_inputs = [int, float, str, List[str], bool, Path]


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
    return [ParamDescription(name=t, type=to_str_type(types[t]), description=get_param_description(f, t))
            for t in types if types[t] in possible_inputs]


def get_registered_function_description(function_id: str, function: AsyncCallable, action_name: str):
    name = function.__name__
    description = function.__doc__
    if description and '@' in description:
        description = description[0: description.index('@')]
    params = get_params_description(function)
    return FunctionDescription(id=function_id, name=name, description=description, action=action_name, params=params)


# def verify_dependencies(f: AsyncCallable, required: List):
#     dependencies = get_dependencies(f).values()
#
#     if Instances in dependencies and Images in dependencies:
#         return False
#
#     count = 0
#     required_nb = len(required)
#     if Instances in required and Images in required:
#         required_nb -= 1
#
#     for r in required:
#         if r in dependencies:
#             count += 1
#
#     return count == required_nb


class Action:
    def __init__(self, id_: str, source: Any, function: AsyncCallable):
        self.id = id_
        self.source = source
        self._function = function

    async def call(self, *args, **kwargs):
        return await self._function(*args, **kwargs)


class ProjectAction:
    def __init__(self, name: str):
        self._possible_actions: List[Action] = []
        self._selected_action = None
        self.name = name

    def can_call(self):
        return self._selected_action is not None

    def register(self, source: Plugin, function: AsyncCallable):
        id_ = source.name + '.' + function.__name__
        action = Action(source=source, function=function, id_=id_)
        self._possible_actions.append(action)

        function_id = f'{source.name}.{function.__name__}'
        function_description = get_registered_function_description(function_id, function, self.name)
        source.registered_functions.append(function_description)
        if not self.can_call():
            self._selected_action = 0

    async def call(self, context: ActionContext):
        action = self._possible_actions[self._selected_action]
        return await action.call(context, **context.ui_inputs)

    def select_function(self, function_id):
        valid = [f.id for f in self._possible_actions]
        if function_id not in valid:
            logging.warning(f'{function_id} is not available in action {self.name}')
            return
        self._selected_action = valid.index(function_id)

    def get_description(self):
        selected = self._possible_actions[self._selected_action].id if self.can_call() else None
        available = [a.id for a in self._possible_actions]
        return ActionDescription(name=self.name, selected_function=selected, available_functions=available)


class ProjectActions:
    def __init__(self):
        self.filter_images = ProjectAction('filter')
        self.group_images = ProjectAction('group')
        self.find_images = ProjectAction('find_similar')
        self.action_images = ProjectAction('action_images')
        self.action_group = ProjectAction('action_group')
        self.import_properties = ProjectAction('import')
        self.export_properties = ProjectAction('export')

        action_list = [self.find_images, self.group_images, self.filter_images, self.action_images, self.action_group,
                       self.import_properties, self.export_properties]
        self.actions = {a.name: a for a in action_list}

    def get_actions_description(self):
        return [a.get_description() for a in self.actions.values()]

    def set_action_function(self, action_name: str, function_id: str):
        action = self.actions[action_name]
        action.select_function(function_id)

    def set_action_updates(self, action_updates: List[ActionUpdate]):
        [self.set_action_function(update.name, update.function) for update in action_updates]
