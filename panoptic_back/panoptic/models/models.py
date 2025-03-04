from __future__ import annotations

import dataclasses
from dataclasses import field, dataclass
from datetime import datetime
from enum import Enum
from typing import TypeAlias, Any, Union, Dict, List

import numpy
from fastapi_camelcase import CamelModel
from pydantic import BaseModel, ConfigDict


# from pydantic.dataclasses import dataclass

class ProjectId(BaseModel):
    name: str | None = None
    path: str | None = None


class PluginKey(BaseModel):
    name: str
    path: str
    source_url: str | None = None


class PanopticData(BaseModel):
    projects: list[ProjectId]
    last_opened: ProjectId | None = None
    plugins: List[PluginKey] = []
    ignored_plugins: dict[str, list[str]] = {}


class PanopticDataOld(BaseModel):
    projects: list[ProjectId]
    last_opened: ProjectId | None = None
    plugins: List[str] = []


class PropertyType(Enum):
    string = "text"
    number = "number"
    tag = "tag"
    multi_tags = "multi_tags"
    image_link = "image_link"
    url = "url"
    date = "date"
    path = "path"
    color = "color"
    checkbox = "checkbox"

    id = 'id'
    sha1 = 'sha1'
    ahash = 'ahash'
    folder = 'folder'
    width = 'width'
    height = 'height'


class PropertyMode(Enum):
    id = 'id'
    sha1 = 'sha1'


@dataclass
class Property:
    id: int
    name: str
    type: PropertyType
    mode: PropertyMode
    property_group_id: int | None = None
    computed: bool = False


@dataclass
class PropertyGroup:
    id: int
    name: str


@dataclass
class LoadState:
    finished_property: bool = False
    finished_instance: bool = False
    finished_tags: bool = False
    finished_instance_values: bool = False
    finished_image_values: bool = False
    finished_property_groups: bool = False

    counter_instance: int = 0
    counter_instance_value: int = 0
    counter_image_value: int = 0

    max_instance: int = 0
    max_instance_value: int = 0
    max_image_value: int = 0

    def finished(self):
        return self.finished_property and self.finished_instance and self.finished_tags and \
            self.finished_instance_values and self.finished_image_values and self.finished_property_groups


class PropertyDescription(Property):
    id: int | None = None
    type: PropertyType | None = None
    col: int


class PropertyUpdate(BaseModel):
    id: int
    name: str


@dataclass
class InstancePropertyKey:
    property_id: int
    instance_id: int


@dataclass
class ImagePropertyKey:
    property_id: int
    sha1: str


@dataclass
class InstanceProperty(InstancePropertyKey):
    value: Any | None = None


@dataclass
class ImageProperty(ImagePropertyKey):
    value: Any | None = None


@dataclass
class Tag:
    id: int
    property_id: int
    value: str
    parents: list[int]
    color: int

    def __post_init__(self):
        self.value = str(self.value)


class TagUpdate(CamelModel):
    id: int
    value: str
    parent_id: list[int] | None = None
    color: int | None = None


@dataclass
class Instance:
    # Should be equal order to SQL
    id: int
    folder_id: int
    name: str
    extension: str

    sha1: str
    url: str
    height: int
    width: int
    ahash: str = ''

    properties: dict[int, InstanceProperty] = field(default_factory=dict)


# @dataclass
# class Image:
#     sha1: str
#     path: str
#     properties: dict[int, PropertyValue] = field(default_factory=dict)


@dataclass
class ImageImportTask:
    image_path: str
    folder_id: int


@dataclasses.dataclass
class ComputedValue:
    sha1: str
    ahash: str
    vector: numpy.ndarray


@dataclasses.dataclass
class Vector:
    source: str
    type: str
    sha1: str
    data: numpy.ndarray


class VectorDescription(CamelModel):
    source: str
    type: str
    count: int | None = None
    id: str = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = f"{self.source}:{self.type}"


# @dataclass
# class VectorPack:
#     id: str
#     source: str
#     type: str
#     vectors: list[Vector]


class ProjectVectorDescriptions(CamelModel):
    vectors: list[VectorDescription] = []
    default_vectors: str | None = None


class Parameters(BaseModel):
    folders: list[str]
    tabs: list[dict]


class Folder(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    id: int | None = None
    path: str
    name: str
    parent: int | None = None
    children: Dict[str, Folder] = {}


class Tab(BaseModel):
    id: int | None = None
    data: dict | None = None


class AddPluginPayload(CamelModel):
    path: str | None = None
    git_url: str | None = None
    plugin_name: str | None = None


class UpdatePluginPayload(BaseModel):
    path: str | None = None


class UpdateCounter(CamelModel):
    action: int = 0
    image: int = 0


class StatusUpdate(CamelModel):
    tasks: List[TaskState] = []
    plugin_loaded: bool = False
    update: UpdateCounter = UpdateCounter()


@dataclass
class Update:
    commits: list[DbCommit] = None
    plugins: list[PluginDescription] = None
    actions: list[ActionDescription] = None
    status: StatusUpdate = None


class TaskState(BaseModel):
    name: str
    id: str
    total: int
    remain: int
    computing: int = 0
    done: bool = True


@dataclass
class Clusters:
    clusters: list[list[str]]
    distances: list[int]


@dataclass
class ActionContext:
    instance_ids: List[int] | None = None
    property_ids: List[int] | None = None
    file: str | None = None
    text: str | None = None
    ui_inputs: Dict[str, Any] = field(default_factory=dict)


class ParamDescription(CamelModel):
    id: str = None
    name: str
    label: str = None
    description: str | None = None
    type: str
    default_value: Any
    possible_values: Any | None = None


class FunctionDescription(CamelModel):
    id: str
    name: str
    label: str | None = None
    description: str | None = None
    params: List[ParamDescription] | None = []
    hooks: list[str] = []


class PluginBaseParamsDescription(BaseModel):
    description: str | None = None
    params: List[ParamDescription] = []


class PluginDefaultParams(BaseModel):
    name: str
    # example: base.export_path = 'my/path'
    base: Dict[str, Any] = {}
    # example: functions.my_func.param1 = 'default_value'
    functions: Dict[str, Dict[str, Any]] = {}


class PluginDescription(CamelModel):
    name: str
    description: str | None = None
    path: str
    base_params: PluginBaseParamsDescription
    registered_functions: List[FunctionDescription] = []


class ActionDescription(CamelModel):
    name: str
    selected_function: str | None = None
    available_functions: List[str] = []


class ActionParam(CamelModel):
    name: str
    value: str


class SetMode(Enum):
    set = 'set'
    add = 'add'
    delete = 'delete'


class ColumnOption(BaseModel):
    ignore: bool = False
    mode: PropertyMode | None = None


@dataclass
class DbCommit:
    empty_instances: list[int] = field(default_factory=list)
    empty_property_groups: list[int] = field(default_factory=list)
    empty_properties: list[int] = field(default_factory=list)
    empty_tags: list[int] = field(default_factory=list)
    empty_instance_values: list[InstancePropertyKey] = field(default_factory=list)
    empty_image_values: list[ImagePropertyKey] = field(default_factory=list)

    folders: list[Folder] = field(default_factory=list)
    instances: list[Instance] = field(default_factory=list)
    property_groups: list[PropertyGroup] = field(default_factory=list)
    properties: list[Property] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)
    instance_values: list[InstanceProperty] = field(default_factory=list)
    image_values: list[ImageProperty] = field(default_factory=list)

    timestamp: datetime = field(default_factory=datetime.now)

    undo: bool | None = False
    history: CommitHistory | None = None


@dataclass
class CommitStat:
    timestamp: datetime
    tags: int = 0
    values: int = 0


@dataclass
class CommitHistory:
    undo: list[CommitStat] = field(default_factory=list)
    redo: list[CommitStat] = field(default_factory=list)


class PropertyId(int):
    pass


class ProjectSettings(BaseModel):
    image_small_size: int = 128
    image_medium_size: int = 256
    image_large_size: int = 1024

    save_image_small: bool = True
    save_image_medium: bool = True
    save_image_large: bool = False

    save_file_raw: bool = False


class UploadError(Enum):
    invalid_csv = "The csv file is invalid, are you using ';' as separator ? "
    no_key = 'No valid key (path or id) was found'
    invalid_type = 'Invalid column type'
    invalid_position = "A valid key (path or id) was found but should be on first column"
    missing_bracket = "Missing bracket: A column that is not a key should always be in the form name[type]"


@dataclass
class UploadConfirm:
    key: str
    col_to_property: dict[int, Property]
    errors: dict[int, UploadError]


@dataclass
class DeleteFolderConfirm:
    deleted_folders: list[int]
    deleted_instances: list[int]
    deleted_sha1s: list[str]


ImportOptions = dict[int, ColumnOption]

JSON: TypeAlias = Union[dict[str, "JSON"], list["JSON"], str, int, float, bool, None]
Tags: TypeAlias = dict[int, dict[int, Tag]]
# Properties: TypeAlias = dict[int, Property]
