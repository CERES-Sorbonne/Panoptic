from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from panoptic.models import InstancePropertyValue, Tag


@dataclass(slots=True)
class Group:
    ids: list[int]
    score: int = None
    meta: Any = None


@dataclass(slots=True)
class GroupResult:
    groups: list[Group]


@dataclass(slots=True)
class InstanceMatch:
    id: int
    score: float


@dataclass(slots=True)
class SearchResult:
    matches: list[InstanceMatch]


@dataclass
class ActionError:
    type: str
    data: Any


@dataclass
class ActionResult:
    action: str
    result: Any
    errors: list[ActionError] = None


@dataclass(slots=True)
class DeleteTagResult:
    tag_id: int
    updated_values: list[InstancePropertyValue]
    updated_tags: list[Tag]
