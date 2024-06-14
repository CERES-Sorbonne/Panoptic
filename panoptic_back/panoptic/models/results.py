from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from panoptic.models import InstanceProperty, Tag, DbCommit


@dataclass
class Group:
    ids: list[int] = None
    sha1s: list[str] = None
    scores: list[int] = None

    score: int = None
    name: str = None


@dataclass
class ActionResult:
    instances: Group = None
    groups: list[Group] = None

    datas: list[dict] = None
    urls: list[str] = None

    commit: DbCommit = None

    errors: list[ActionError] = None


@dataclass
class ActionError:
    name: str
    message: str = ""
    trace: str = None


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
class DeleteTagResult:
    tag_id: int
    updated_values: list[InstanceProperty]
    updated_tags: list[Tag]
