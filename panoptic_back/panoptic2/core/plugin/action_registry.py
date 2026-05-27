"""ActionRegistry — introspects plugin functions and dispatches calls."""
from __future__ import annotations

import inspect
import logging
from enum import Enum
from pathlib import Path
from typing import Callable

from panoptic2.core.databases.media.models import VectorType
from panoptic2.models.action_models import (
    ActionContext, ActionResult, FunctionDescription, OwnVectorType,
    ParamDescription, PropertyId, InputFile,
)

# String type tags understood by the UI
_TYPE_MAP: dict = {
    int:           'int',
    float:         'float',
    str:           'str',
    bool:          'bool',
    Path:          'path',
    PropertyId:    'property',
    OwnVectorType: 'own_vector_type',
    VectorType:    'vector_type',
    InputFile:     'input_file',
}

POSSIBLE_INPUT_TYPES = set(_TYPE_MAP.values()) | {'enum', 'vector_type'}


def _to_str_type(t) -> str | None:
    if t in _TYPE_MAP:
        return _TYPE_MAP[t]
    try:
        if issubclass(t, Enum):
            return 'enum'
    except TypeError:
        pass
    return None


def _param_description_from_doc(fn: Callable, param_name: str) -> str | None:
    doc = fn.__doc__
    token = f'@{param_name}: '
    if not doc or token not in doc:
        return None
    start = doc.index(token) + len(token)
    end = doc.index('@', start) if '@' in doc[start:] else len(doc)
    return doc[start:end].strip()


def _build_param_descriptions(fn: Callable) -> list[ParamDescription]:
    sig = inspect.signature(fn)
    result = []
    for name, param in sig.parameters.items():
        t = param.annotation
        str_type = _to_str_type(t)
        if str_type not in POSSIBLE_INPUT_TYPES:
            if str_type is not None:
                logging.warning(f'Action param {name!r} has unsupported type {t!r}, skipped')
            continue
        default = None if param.default is inspect.Parameter.empty else param.default
        desc = ParamDescription(
            name=name,
            type=str_type,
            default_value=default,
            description=_param_description_from_doc(fn, name),
        )
        if str_type == 'enum':
            desc.possible_values = [e.value for e in t]
        result.append(desc)
    return result


def build_function_description(plugin_name: str, fn: Callable, hooks: list[str] = None) -> FunctionDescription:
    fn_name = fn.__name__
    doc = fn.__doc__ or ''
    description = doc[:doc.index('@')].strip() if '@' in doc else doc.strip() or None
    return FunctionDescription(
        id=f'{plugin_name}.{fn_name}',
        name=fn_name,
        description=description,
        params=_build_param_descriptions(fn),
        hooks=hooks or [],
    )


# ---------------------------------------------------------------------------
# Action — wraps a single callable
# ---------------------------------------------------------------------------

class Action:
    def __init__(self, fn: Callable, description: FunctionDescription):
        self.id = description.id
        self._fn = fn
        self.description = description

    def call(self, ctx: ActionContext) -> ActionResult:
        sig = inspect.signature(self._fn)
        kwargs: dict = {}
        for desc in self.description.params:
            raw = ctx.ui_inputs.get(desc.name)
            if raw is None:
                continue
            # Coerce enum and complex types back from their serialised form
            param_type = sig.parameters[desc.name].annotation
            if desc.type == 'enum':
                raw = param_type(raw)
            elif desc.type in ('own_vector_type', 'vector_type'):
                if isinstance(raw, dict):
                    raw = VectorType(**raw)
            kwargs[desc.name] = raw
        return self._fn(ctx, **kwargs)


# ---------------------------------------------------------------------------
# ActionRegistry — central registry per project
# ---------------------------------------------------------------------------

class ActionRegistry:
    def __init__(self):
        self.actions: dict[str, Action] = {}

    def add(self, fn: Callable, description: FunctionDescription) -> None:
        self.actions[description.id] = Action(fn, description)

    def easy_add(self, plugin_name: str, fn: Callable, hooks: list[str] = None) -> FunctionDescription:
        desc = build_function_description(plugin_name, fn, hooks)
        self.add(fn, desc)
        return desc

    def call(self, function_id: str, ctx: ActionContext) -> ActionResult:
        if function_id not in self.actions:
            raise KeyError(f'Action {function_id!r} not found')
        return self.actions[function_id].call(ctx)

    def get_all(self) -> dict[str, FunctionDescription]:
        return {action_id: a.description for action_id, a in self.actions.items()}
