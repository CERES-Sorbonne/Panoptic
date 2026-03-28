import msgspec
from datetime import datetime
from typing import Any

# --- ENTITY MODELS ---

class Commit(msgspec.Struct, array_like=True):
    id: int
    group_id: int | None
    source: str
    timestamp: datetime

class FileSource(msgspec.Struct, array_like=True):
    id: str
    dtype: str
    name: str | None
    root_url: str | None
    commit_id: int

class Folder(msgspec.Struct, array_like=True):
    id: int
    source_id: str | None
    path: str | None
    name: str | None
    parent: int | None
    commit_id: int

class File(msgspec.Struct, array_like=True):
    id: int
    name: str | None
    folder_id: str | None
    sha1: str | None
    commit_id: int

class Instance(msgspec.Struct, array_like=True):
    id: int
    file_id: int | None
    sha1: str | None
    commit_id: int

class Property(msgspec.Struct, array_like=True):
    id: int
    dtype: str | None
    mode: str | None
    name: str | None
    commit_id: int

class Tag(msgspec.Struct, array_like=True):
    id: int
    property_id: int | None
    parents: list[int] | None
    value: str | None
    color: int | None
    commit_id: int

# --- VALUE MODELS ---

class InstanceValue(msgspec.Struct, array_like=True):
    property_id: int
    instance_id: int
    value: Any
    commit_id: int

class Sha1Value(msgspec.Struct, array_like=True):
    property_id: int
    sha1: str
    value: Any
    commit_id: int

# --- HISTORY MODELS ---

class FileSourceHistory(msgspec.Struct, array_like=True):
    id: str
    dtype: str | None
    name: str | None
    root_url: str | None
    commit_id: int
    operation_type: int | None

class FolderHistory(msgspec.Struct, array_like=True):
    id: int
    source_id: str | None
    path: str | None
    name: str | None
    parent: int | None
    commit_id: int
    operation_type: int | None

class FileHistory(msgspec.Struct, array_like=True):
    id: int
    name: str | None
    folder_id: str | None
    sha1: str | None
    commit_id: int
    operation_type: int | None

class InstanceHistory(msgspec.Struct, array_like=True):
    id: int
    file_id: int | None
    sha1: str | None
    commit_id: int
    operation_type: int | None

class PropertyHistory(msgspec.Struct, array_like=True):
    id: int
    dtype: str | None
    mode: str | None
    name: str | None
    commit_id: int
    operation_type: int | None

class TagHistory(msgspec.Struct, array_like=True):
    id: int
    property_id: int | None
    parents: list[int] | None
    value: str | None
    color: int | None
    commit_id: int
    operation_type: int | None

class InstanceValueHistory(msgspec.Struct, array_like=True):
    property_id: int
    instance_id: int
    value: Any
    commit_id: int
    operation_type: int | None

class Sha1ValueHistory(msgspec.Struct, array_like=True):
    property_id: int
    sha1: str
    value: Any
    commit_id: int
    operation_type: int | None

# --- WRITE MODELS ---

class PropertyValueWrite(msgspec.Struct, array_like=True):
    stamp_mode: str | None = None
    keys: list[int | str] = msgspec.field(default_factory=list)
    values: Any = None

# --- COMMIT CONTAINERS ---

class DeleteCommit(msgspec.Struct):
    file_sources: set[str] = msgspec.field(default_factory=set)
    folders: set[int] = msgspec.field(default_factory=set)
    files: set[int] = msgspec.field(default_factory=set)
    instances: set[int] = msgspec.field(default_factory=set)
    properties: set[int] = msgspec.field(default_factory=set)
    tags: set[int] = msgspec.field(default_factory=set)

class UpsertCommit(msgspec.Struct):
    file_sources: dict[str, FileSource] = msgspec.field(default_factory=dict)
    folders: dict[int, Folder] = msgspec.field(default_factory=dict)
    files: dict[int, File] = msgspec.field(default_factory=dict)
    instances: dict[int, Instance] = msgspec.field(default_factory=dict)
    properties: dict[int, Property] = msgspec.field(default_factory=dict)
    tags: dict[int, Tag] = msgspec.field(default_factory=dict)
    instance_values: dict[int, PropertyValueWrite] = msgspec.field(default_factory=dict)
    sha1_values: dict[int, PropertyValueWrite] = msgspec.field(default_factory=dict)