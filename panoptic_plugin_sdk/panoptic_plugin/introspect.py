"""Action / params introspection — port of panoptic/core/plugin/action_registry.py.

Builds the FunctionDescription / ParamDescription dicts the frontend action UI consumes
(snake_case wire names, as the python backend sends them) and coerces `ui_inputs` back to the
declared parameter types when an action is called.
"""
from __future__ import annotations

import inspect
import logging
import types
import typing
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .models import (
    FilePath, FolderPath, InputFile, OwnVectorType, PropertyId, VectorType, from_dict,
)

log = logging.getLogger('panoptic_plugin')

# String type tags understood by the UI (same table as action_registry._TYPE_MAP)
TYPE_MAP: dict = {
    int:           'int',
    float:         'float',
    str:           'str',
    bool:          'bool',
    Path:          'path',
    PropertyId:    'property',
    OwnVectorType: 'own_vector_type',
    VectorType:    'vector_type',
    InputFile:     'input_file',
    FolderPath:    'folder_path',
    FilePath:      'file_path',
}

POSSIBLE_INPUT_TYPES = set(TYPE_MAP.values()) | {'enum', 'vector_type'}

_UNION_TYPES = {typing.Union}
if hasattr(types, 'UnionType'):
    _UNION_TYPES.add(types.UnionType)


def _unwrap_optional(t):
    """`X | None` / `Optional[X]` -> X (the reference registry did not accept those)."""
    if typing.get_origin(t) in _UNION_TYPES:
        args = [a for a in typing.get_args(t) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return t


def to_str_type(t) -> str | None:
    t = _unwrap_optional(t)
    if t in TYPE_MAP:
        return TYPE_MAP[t]
    try:
        if issubclass(t, Enum):
            return 'enum'
    except TypeError:
        pass
    return None


def param_description_from_doc(doc: str | None, param_name: str) -> str | None:
    token = f'@{param_name}: '
    if not doc or token not in doc:
        return None
    start = doc.index(token) + len(token)
    end = doc.index('@', start) if '@' in doc[start:] else len(doc)
    return doc[start:end].strip()


def description_from_doc(doc: str | None) -> str | None:
    doc = doc or ''
    # Same expression as the reference: text before the first '@', or the whole docstring.
    return doc[:doc.index('@')].strip() if '@' in doc else doc.strip() or None


def _type_hints(fn: Callable) -> dict:
    """Resolved annotations. Unlike the reference, string annotations
    (`from __future__ import annotations`) are supported."""
    target = fn.__func__ if inspect.ismethod(fn) else fn
    try:
        return typing.get_type_hints(target)
    except Exception:
        return {}


def _param_desc(name: str, annotation, default, doc: str | None) -> dict | None:
    str_type = to_str_type(annotation)
    if str_type not in POSSIBLE_INPUT_TYPES:
        if str_type is not None:
            log.warning(f'Action param {name!r} has unsupported type {annotation!r}, skipped')
        return None
    desc = {
        'id': None,
        'name': name,
        'label': None,
        'description': param_description_from_doc(doc, name),
        'type': str_type,
        'default_value': default,
        'possible_values': None,
    }
    if str_type == 'enum':
        enum_cls = _unwrap_optional(annotation)
        desc['possible_values'] = [e.value for e in enum_cls]
        if isinstance(default, Enum):
            desc['default_value'] = default.value
    elif isinstance(default, Enum):
        desc['default_value'] = default.value
    return desc


def build_param_descriptions(fn: Callable) -> list[dict]:
    sig = inspect.signature(fn)
    hints = _type_hints(fn)
    result = []
    for name, param in sig.parameters.items():
        annotation = hints.get(name, param.annotation)
        default = None if param.default is inspect.Parameter.empty else param.default
        desc = _param_desc(name, annotation, default, fn.__doc__)
        if desc is not None:
            result.append(desc)
    return result


def build_function_description(plugin_name: str, fn: Callable, hooks: list[str] | None = None,
                               name: str | None = None, label: str | None = None) -> dict:
    fn_name = name or fn.__name__
    return {
        'id': f'{plugin_name}.{fn_name}',
        'name': fn_name,
        'label': label,
        'description': description_from_doc(fn.__doc__),
        'params': build_param_descriptions(fn),
        'hooks': list(hooks or []),
    }


def build_params_description(model_cls, current=None) -> dict:
    """PluginBaseParamsDescription of a pydantic params model.

    Each param gets ``id = name`` and ``default_value`` = the current value (as the reference
    `APlugin._get_base_params_description` does).
    """
    if model_cls is None:
        return {'description': None, 'params': []}
    doc = model_cls.__doc__ or ''
    description = doc[:doc.index('@')].strip() if '@' in doc else doc.strip() or None
    params = []
    for fname, finfo in model_cls.model_fields.items():
        default = None if finfo.is_required() else finfo.get_default(call_default_factory=True)
        desc = _param_desc(fname, finfo.annotation, default, model_cls.__doc__)
        if desc is None:
            continue
        desc['id'] = fname
        if current is not None:
            value = getattr(current, fname, None)
            desc['default_value'] = value.value if isinstance(value, Enum) else value
        params.append(desc)
    return {'description': description, 'params': params}


class InputError(ValueError):
    """A ui_input could not be converted to its declared type."""


def coerce_inputs(fn: Callable, params: list[dict], ui_inputs: dict[str, Any]) -> dict[str, Any]:
    """Port of action_registry.Action.call: build the kwargs of an action call.

    Inputs left empty (None / missing) are not passed, so the function default applies.
    """
    sig = inspect.signature(fn)
    hints = _type_hints(fn)
    kwargs: dict = {}
    for desc in params:
        name = desc['name']
        raw = (ui_inputs or {}).get(name)
        if raw is None or name not in sig.parameters:
            continue
        param_type = _unwrap_optional(hints.get(name, sig.parameters[name].annotation))
        try:
            t = desc['type']
            if t == 'enum':
                raw = param_type(raw)
            elif t in ('own_vector_type', 'vector_type'):
                if isinstance(raw, dict):
                    raw = from_dict(VectorType, raw)
            elif t in ('folder_path', 'file_path'):
                raw = param_type(raw)
            elif t == 'int' and isinstance(raw, str):
                raw = int(raw)
            elif t == 'float' and isinstance(raw, (str, int)) and not isinstance(raw, bool):
                raw = float(raw)
        except (ValueError, TypeError, KeyError) as e:
            raise InputError(f'Invalid value for {name!r} ({desc["type"]}): {raw!r}: {e}') from e
        kwargs[name] = raw
    return kwargs
