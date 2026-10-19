"""Plain data models of the plugin API.

Action models mirror `panoptic/models/action_models.py`; DB models mirror the msgspec structs of
`panoptic/core/databases/{data,media}/models.py` (same field names and order). They are
dataclasses so the SDK does not depend on msgspec or on the `panoptic` package.
"""
from __future__ import annotations

import dataclasses
import datetime
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

try:  # numpy is optional
    import numpy as _np
except ImportError:  # pragma: no cover - exercised only without numpy
    _np = None


# ---------------------------------------------------------------------------
# Sentinel types used as action parameter annotations (same names as before)
# ---------------------------------------------------------------------------

class PropertyId(int):
    """Marks a parameter as a property selector in the UI."""


class OwnVectorType(str):
    """Marks a parameter as a vector-type selector limited to this plugin's types.

    The action receives a :class:`VectorType`.
    """


class InputFile(str):
    """Marks a parameter as a file upload input in the UI. The action receives base64 text."""


class _ServerPath(str):
    """A path string that can also be used as a field of a plugin params model."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        from pydantic_core import core_schema
        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())


class FolderPath(_ServerPath):
    """Marks a parameter as a server folder path, picked with the file explorer."""


class FilePath(_ServerPath):
    """Marks a parameter as a server file path, picked with the file explorer."""


# ---------------------------------------------------------------------------
# Action invocation context / result
# ---------------------------------------------------------------------------

@dataclass
class ActionContext:
    instance_ids: list[int] | None = None
    group_name: str | None = None
    ui_inputs: dict[str, Any] = field(default_factory=dict)
    # New in the socket protocol: who triggered the action (None when unknown)
    user_id: str | None = None
    # Set when the backend cancels the request ($/cancel). Long actions may poll it.
    cancelled: Any = field(default=None, repr=False, compare=False)

    def is_cancelled(self) -> bool:
        return bool(self.cancelled is not None and self.cancelled.is_set())


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
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'


@dataclass
class NotifFunction:
    """An action the UI offers to run from a notification (frontend `NotifFunction`)."""
    function: str
    message: str
    context: dict = field(default_factory=dict)


@dataclass
class Notif:
    type: NotifType
    name: str | None = None
    message: str | None = None
    data: Any = None
    functions: list[NotifFunction] | None = None


@dataclass
class ActionResult:
    groups: list[Group] | None = None
    datas: list[dict] | None = None
    urls: list[str] | None = None
    notifs: list[Notif] | None = None
    value: Any = None
    # Id of a task queued by the action, so the UI can follow its progress
    task_id: str | None = None


# ---------------------------------------------------------------------------
# DB models  (data.db)
# ---------------------------------------------------------------------------

@dataclass
class Commit:
    id: int
    group_id: int | None
    source: str
    timestamp: Any
    active: int
    author: str | None = None
    redoable: int | None = 1


@dataclass
class FileSource:
    id: int
    dtype: str
    name: str | None
    root_url: str | None
    metadata: dict | None = None
    sync_status: dict | None = None


@dataclass
class Folder:
    id: int
    source_id: int | None
    path: str | None
    name: str | None
    parent: int | None


@dataclass
class File:
    id: int
    name: str | None
    folder_id: int | None
    sha1: str | None
    width: int | None = None
    height: int | None = None
    format: str | None = None
    created_at: Any = None


@dataclass
class Instance:
    id: int
    file_id: int | None
    sha1: str | None


@dataclass
class Property:
    id: int
    dtype: str | None = None
    mode: str | None = None
    name: str | None = None
    access: str | None = None
    tag_list_id: int | None = None
    system_key: str | None = None
    property_group_id: int | None = None
    commit_id: int | None = None
    operation: int | None = None


@dataclass
class PropertyGroup:
    id: int
    name: str | None = None
    commit_id: int | None = None
    operation: int | None = None


@dataclass
class Tag:
    id: int
    list_id: int | None = None
    parents: list[int] | None = None
    value: str | None = None
    color: int | None = None
    commit_id: int | None = None
    operation: int | None = None


@dataclass
class InstanceValue:
    property_id: int
    instance_id: int
    value: Any = None
    commit_id: int | None = None
    operation: int | None = None


@dataclass
class Sha1Value:
    property_id: int
    sha1: str
    value: Any = None
    commit_id: int | None = None
    operation: int | None = None


@dataclass
class FileValue:
    property_id: int
    file_id: int
    value: Any = None
    commit_id: int | None = None
    operation: int | None = None


@dataclass
class InstanceTagValue:
    instance_id: int
    property_id: int
    tag_id: int
    commit_id: int | None = None
    operation: int | None = None


@dataclass
class Sha1TagValue:
    sha1: str
    property_id: int
    tag_id: int
    commit_id: int | None = None
    operation: int | None = None


@dataclass
class DataCommit:
    """Writes to the *logged* (undoable) entities, same shape as the reference DataCommit.

    Each entity row carries its own ``operation``: ``None``/OP_CREATE/OP_UPDATE upsert it (the
    writer diffs against the current row, so send full rows), OP_DELETE deletes it (with the
    same cascade as the reference). A value row asserts the full value of its cell: for tag
    properties the value is the complete list of tag ids, ``None`` clears the cell.

    Negative ids in ``properties``, ``property_groups`` and ``tags`` are placeholders: the writer
    allocates real ids and rewrites every reference (tag_list_id, property_group_id, list_id,
    parents, value property ids). The id map is returned by the commit.
    """
    properties: list[Property] = field(default_factory=list)
    property_groups: list[PropertyGroup] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)
    instance_values: list[InstanceValue] = field(default_factory=list)
    sha1_values: list[Sha1Value] = field(default_factory=list)
    file_values: list[FileValue] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.properties or self.property_groups or self.tags or self.instance_values
                    or self.sha1_values or self.file_values)

    @classmethod
    def from_dict(cls, d: dict) -> 'DataCommit':
        return cls(
            properties=[from_dict(Property, r) for r in d.get('properties') or []],
            property_groups=[from_dict(PropertyGroup, r) for r in d.get('property_groups') or []],
            tags=[from_dict(Tag, r) for r in d.get('tags') or []],
            instance_values=[from_dict(InstanceValue, r) for r in d.get('instance_values') or []],
            sha1_values=[from_dict(Sha1Value, r) for r in d.get('sha1_values') or []],
            file_values=[from_dict(FileValue, r) for r in d.get('file_values') or []],
        )


@dataclass
class CommitResult:
    """What a commit returns: the commit row (None when nothing changed), the placeholder id map
    ``{'properties': {-1: 12}, 'tags': {...}, 'property_groups': {...}}`` and the sequence."""
    commit: Commit | None
    ids: dict[str, dict[int, int]] = field(default_factory=dict)
    sequence: int | None = None

    def real_id(self, kind: str, placeholder: int) -> int:
        if placeholder >= 0:
            return placeholder
        return self.ids.get(kind, {})[placeholder]


# ---------------------------------------------------------------------------
# DB models  (media.db)
# ---------------------------------------------------------------------------

@dataclass(eq=True)
class VectorType:
    id: int
    source: str
    params: dict

    def __str__(self):
        model = str(self.params.get('model', 'default').replace('/', ''))
        return f"{self.source}_{model}_{self.id}"

    def __hash__(self):
        return hash(str(self))


@dataclass
class Vector:
    type_id: int
    sha1: str
    data: Any   # numpy float32 array when numpy is installed, else array('f')


@dataclass
class Map:
    id: int
    source: str
    name: str
    key: str
    count: int
    data: Any = None


@dataclass
class ImageType:
    id: int
    name: str
    format: str
    width: int | None
    height: int | None
    auto_gen: bool = True


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def from_dict(cls, d: dict):
    """Build dataclass ``cls`` from a dict, ignoring unknown keys."""
    if isinstance(d, cls):
        return d
    names = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in names})


def to_jsonable(obj: Any) -> Any:
    """Convert results to JSON-compatible data: dataclasses, enums, paths, numpy values.

    Non-finite floats become ``None`` (JSON has no NaN/Infinity; the protocol forbids them).
    The ``cancelled`` field of ActionContext is never serialized.
    """
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, Enum):
        return to_jsonable(obj.value)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out = {}
        for f in dataclasses.fields(obj):
            if f.name == 'cancelled' and isinstance(obj, ActionContext):
                continue
            out[f.name] = to_jsonable(getattr(obj, f.name))
        return out
    if isinstance(obj, dict):
        return {str(k) if not isinstance(k, str) else k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat(' ') if isinstance(obj, datetime.datetime) else obj.isoformat()
    if _np is not None:
        if isinstance(obj, _np.ndarray):
            return to_jsonable(obj.tolist())
        if isinstance(obj, _np.generic):
            return to_jsonable(obj.item())
    if hasattr(obj, 'model_dump'):  # pydantic model
        return to_jsonable(obj.model_dump(mode='json'))
    if hasattr(obj, 'tolist'):  # array.array
        return to_jsonable(obj.tolist())
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def result_from_any(value: Any) -> dict:
    """Normalize an action's return value to the ActionResult wire shape."""
    if value is None:
        value = ActionResult()
    if not isinstance(value, ActionResult):
        if isinstance(value, dict) and set(value) <= {f.name for f in dataclasses.fields(ActionResult)}:
            value = ActionResult(**value)
        else:
            value = ActionResult(value=value)
    return to_jsonable(value)
