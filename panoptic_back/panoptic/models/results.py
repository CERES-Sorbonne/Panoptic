from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from panoptic.models import InstanceProperty, Tag, DbCommit, ExecuteActionPayload, ActionContext, LoadState


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
    ids: list[int] = None
    sha1s: list[str] = None
    # scores of the ids or sha1's
    scores: ScoreList = None
    # score of the group
    score: Score = None
    name: str = None


@dataclass
class ActionResult:
    groups: list[Group] = None

    datas: list[dict] = None
    urls: list[str] = None

    commit: DbCommit = None

    notifs: list[Notif] = None


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


@dataclass
class NotifType(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class NotifFunction(ExecuteActionPayload):
    message: str


@dataclass
class Notif:
    type: NotifType = None
    id: int = None
    created_at: datetime = None
    received_at: datetime = None
    name: str = None
    message: str = None
    data: Any = None
    functions: list[NotifFunction] = None
    read: bool = None


@dataclass
class LoadResult:
    chunk: DbCommit
    state: LoadState
