import msgspec
from datetime import datetime
from typing import Any, Annotated, Optional

from panoptic.core.databases.entity_schema import PrimaryKey, Index


# --- ENTITY MODELS ---

class Commit(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    group_id: Optional[int]
    source: str
    timestamp: datetime
    # `active` is the *enabled* bit of the versioning model: a commit contributes to the
    # resolved state iff active == 1. Undo/redo simply flip it (see DataWriter.set_commit_active).
    active: int
    # Who authored the commit. Enables per-user, non-sequential selective undo: a user undoes
    # their own most-recent enabled commit regardless of its position in the global log.
    author: Optional[str] = None


class ChangeOp(msgspec.Struct, array_like=True):
    """A single partial-diff entry in the generic version log (``entity_log`` table).

    One row per (entity, commit). ``changes`` carries **only the fields a commit altered**,
    so the log is compact and undo is field-granular:

      * scalar field  ->  ``{field: new_value}``
      * set field     ->  ``{field: {"add": [...], "remove": [...]}}``  (e.g. tag.parents)
      * OP_CREATE     ->  full initial field set (the base image)
      * OP_UPDATE     ->  only the changed fields
      * OP_DELETE     ->  ``changes`` is None

    ``entity_key`` is the JSON-encoded primary key tuple of the target row (see resolver.encode_key),
    which lets one table hold ops for every entity kind (single- or composite-PK) uniformly.
    Materialized state is the fold of the *enabled* ops for a key — a pure function of the
    enabled set, hence order-independent and safe to toggle at any position.
    """
    entity_type: str
    entity_key: str
    commit: int
    op: int
    changes: Optional[dict] = None
    sequence: Optional[int] = None

# --- STRUCTURAL ENTITIES ---
# Sequenced (delta-synced) but NOT logged: created by import, hard-deleted, never undone.
# They carry no commit_id/operation columns.

class FileSource(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    dtype: str
    name: Optional[str]
    root_url: Optional[str]
    metadata: Optional[dict] = None
    # Snapshot of the last completed sync, e.g. {last_synced_at, status,
    # folder_count, file_count, imported_count, failed_count}. Set by
    # FileSourceReader.on_import_complete(), read-only from the API's perspective.
    sync_status: Optional[dict] = None

class Folder(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    source_id: Optional[int]
    path: Optional[str]
    name: Optional[str]
    parent: Optional[int]

class File(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    name: Optional[str]
    folder_id: Optional[int]
    sha1: Annotated[Optional[str], Index]
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    created_at: Optional[datetime] = None

class Instance(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    file_id: Optional[int]
    sha1: Annotated[Optional[str], Index]

class Property(msgspec.Struct, array_like=True):
    # data fields default to None so a delete stub is just Property(id=i, operation=OP_DELETE)
    id: Annotated[int, PrimaryKey]
    dtype: Optional[str] = None
    mode: Optional[str] = None
    name: Optional[str] = None
    access: Optional[str] = None
    tag_list_id: Optional[int] = None
    system_key: Optional[str] = None
    property_group_id: Optional[int] = None
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class PropertyGroup(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    name: Optional[str] = None
    commit_id: Optional[int] = None
    operation: Optional[int] = None

class TagList(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    name: Optional[str]

class Tag(msgspec.Struct, array_like=True):
    id: Annotated[int, PrimaryKey]
    list_id: Optional[int] = None
    parents: Optional[list[int]] = None
    value: Optional[str] = None
    color: Optional[int] = None
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


class DataCommit(msgspec.Struct):
    """Unified commit for the *logged* (revertable) entities only.

    Each entity carries its own ``operation`` (OP_CREATE / OP_UPDATE / OP_DELETE), so a
    single commit can create, update and delete in one shot. Structural entities
    (file_sources/folders/files/instances) are NOT part of this commit — they go through
    the structural write API (add_* / delete_*) and are never undone.
    """
    properties: list[Property] = msgspec.field(default_factory=list)
    property_groups: list[PropertyGroup] = msgspec.field(default_factory=list)
    tags: list[Tag] = msgspec.field(default_factory=list)
    instance_values: list[InstanceValue] = msgspec.field(default_factory=list)
    sha1_values: list[Sha1Value] = msgspec.field(default_factory=list)
    file_values: list[FileValue] = msgspec.field(default_factory=list)
