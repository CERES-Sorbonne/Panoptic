import msgspec
from datetime import datetime
from typing import Any, Annotated, Optional

from panoptic2.core.databases.entity_schema import PrimaryKey, Index


# --- ENTITY MODELS ---

class Commit(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    group_id: Optional[int]
    source: str
    timestamp: datetime
    active: int

class FileSource(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    dtype: str
    name: Optional[str]
    root_url: Optional[str]
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class Folder(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    source_id: Optional[int]
    path: Optional[str]
    name: Optional[str]
    parent: Optional[int]
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class File(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    name: Optional[str]
    folder_id: Optional[int]
    sha1: Optional[str]
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    created_at: Optional[datetime] = None
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class Instance(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    file_id: Optional[int]
    sha1: Optional[str]
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class Property(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    dtype: Optional[str]
    mode: Optional[str]
    name: Optional[str]
    access: Optional[str]
    tag_list_id: Optional[int]
    system_key: Optional[str] = None
    property_group_id: Optional[int] = None
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class PropertyGroup(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    name: Optional[str]
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class TagList(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    name: Optional[str]

class Tag(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    list_id: Optional[int]
    parents: Optional[list[int]]
    value: Optional[str]
    color: Optional[int]
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class InstanceValue(msgspec.Struct, array_like=True):
    property_id: Annotated[int, PrimaryKey]
    instance_id: Annotated[int, PrimaryKey]
    value: Optional[Any] = None
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class Sha1Value(msgspec.Struct, array_like=True):
    property_id: Annotated[int, PrimaryKey]
    sha1: Annotated[str, PrimaryKey]
    value: Optional[Any] = None
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class FileValue(msgspec.Struct, array_like=True):
    property_id: Annotated[int, PrimaryKey]
    file_id:     Annotated[int, PrimaryKey]
    value: Optional[Any] = None
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class InstanceTagValue(msgspec.Struct, array_like=True):
    instance_id: Annotated[int, PrimaryKey]
    property_id: Annotated[int, PrimaryKey]
    tag_id:      Annotated[int, PrimaryKey, Index]
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class Sha1TagValue(msgspec.Struct, array_like=True):
    sha1:        Annotated[str, PrimaryKey]
    property_id: Annotated[int, PrimaryKey]
    tag_id:      Annotated[int, PrimaryKey, Index]
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class PropertyValueWrite(msgspec.Struct, array_like=True):
    stamp_mode: str | None = None
    keys: list[int | str] = msgspec.field(default_factory=list)
    values: Any = None

class DeleteCommit(msgspec.Struct):
    file_sources: set[str] = msgspec.field(default_factory=set)
    folders: set[int] = msgspec.field(default_factory=set)
    files: set[int] = msgspec.field(default_factory=set)
    instances: set[int] = msgspec.field(default_factory=set)
    properties: set[int] = msgspec.field(default_factory=set)
    tags: set[int] = msgspec.field(default_factory=set)
    property_groups: set[int] = msgspec.field(default_factory=set)

class UpsertCommit(msgspec.Struct):
    file_sources: dict[int, FileSource] = msgspec.field(default_factory=dict)
    folders: dict[int, Folder] = msgspec.field(default_factory=dict)
    files: dict[int, File] = msgspec.field(default_factory=dict)
    instances: dict[int, Instance] = msgspec.field(default_factory=dict)
    properties: dict[int, Property] = msgspec.field(default_factory=dict)
    tags: dict[int, Tag] = msgspec.field(default_factory=dict)
    property_groups: dict[int, PropertyGroup] = msgspec.field(default_factory=dict)
    instance_values: dict[int, list[InstanceValue]] = msgspec.field(default_factory=dict)
    sha1_values: dict[int, list[Sha1Value]] = msgspec.field(default_factory=dict)
    file_values: dict[int, list[FileValue]] = msgspec.field(default_factory=dict)
