"""Action-related models for the plugin system."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Sentinel types used as function parameter type annotations
# ---------------------------------------------------------------------------

class PropertyId(int):
    """Marks a parameter as a property selector in the UI."""

class OwnVectorType(str):
    """Marks a parameter as a vector-type selector limited to this plugin's types."""

class InputFile(str):
    """Marks a parameter as a file upload input in the UI."""


# ---------------------------------------------------------------------------
# Parameter / function descriptions  (sent to the UI)
# ---------------------------------------------------------------------------

class ParamDescription(BaseModel):
    id: str | None = None
    name: str
    label: str | None = None
    description: str | None = None
    type: str
    default_value: Any = None
    possible_values: Any | None = None


class FunctionDescription(BaseModel):
    id: str
    name: str
    label: str | None = None
    description: str | None = None
    params: list[ParamDescription] = []
    hooks: list[str] = []


# ---------------------------------------------------------------------------
# Action invocation context
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ActionContext:
    instance_ids: list[int] | None = None
    group_name: str | None = None
    ui_inputs: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Action result
# ---------------------------------------------------------------------------

@dataclass
class ScoreList:
    values: list[float]
    min: float
    max: float
    description: str = ''
    max_is_best: bool = True


@dataclass
class Score:
    value: float
    min: float
    max: float
    description: str = ''
    max_is_best: bool = True


@dataclass
class Group:
    ids: list[int] | None = None
    sha1s: list[str] | None = None
    scores: ScoreList | None = None
    score: Score | None = None
    name: str | None = None


class NotifType(Enum):
    DEBUG   = 'debug'
    INFO    = 'info'
    WARNING = 'warning'
    ERROR   = 'error'


@dataclass
class Notif:
    type: NotifType
    name: str | None = None
    message: str | None = None
    data: Any = None


@dataclass
class ActionResult:
    groups: list[Group] | None = None
    datas:  list[dict]  | None = None
    urls:   list[str]   | None = None
    notifs: list[Notif] | None = None
    value:  Any         = None


# ---------------------------------------------------------------------------
# Plugin description  (sent to the UI via /plugins_info)
# ---------------------------------------------------------------------------

class PluginBaseParamsDescription(BaseModel):
    description: str | None = None
    params: list[ParamDescription] = []


class PluginDescription(BaseModel):
    name: str
    description: str | None = None
    path: str
    base_params: PluginBaseParamsDescription
    registered_functions: list[FunctionDescription] = []
