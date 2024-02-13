from dataclasses import dataclass
from typing import Any


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
