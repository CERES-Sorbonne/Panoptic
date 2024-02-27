from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias, Any, Union, Dict, List

import numpy
from dataclass_wizard import JSONWizard
from fastapi_camelcase import CamelModel
from pydantic import BaseModel


class PropertyType(Enum):
    string = "string"
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


class Property(BaseModel):
    id: int
    name: str
    type: PropertyType
    mode: PropertyMode
    computed: bool = False


class PropertyUpdate(BaseModel):
    id: int
    name: str


# @dataclass(slots=True)
# class PropertyValue:
#     property_id: int
#
#     image_id: int
#     sha1: str
#
#     value: Any


@dataclass(slots=True)
class InstancePropertyValue:
    property_id: int
    instance_id: int
    value: Any


class ImagePropertyValue(CamelModel):
    property_id: int
    sha1: str
    value: Any


@dataclass(slots=True)
class Tag:
    id: int
    property_id: int
    parents: list[int]
    value: str
    color: int

    def __post_init__(self):
        self.value = str(self.value)


class TagUpdate(CamelModel):
    id: int
    value: str
    parent_id: list[int] | None
    color: int | None


@dataclass(slots=True)
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

    properties: dict[int, InstancePropertyValue] = field(default_factory=dict)


# @dataclass(slots=True)
# class Image:
#     sha1: str
#     path: str
#     properties: dict[int, PropertyValue] = field(default_factory=dict)


@dataclass(slots=True)
class ImageImportTask:
    image_path: str
    folder_id: int


@dataclass(slots=True)
class ComputedValue:
    sha1: str
    ahash: str
    vector: numpy.ndarray


@dataclass(slots=True)
class Vector:
    source: str
    type: str
    sha1: str
    data: numpy.ndarray


class VectorDescription(CamelModel):
    source: str
    type: str
    count: int | None


class ProjectVectorDescriptions(CamelModel):
    vectors: list[VectorDescription] = []
    default_vectors: VectorDescription | None


class Parameters(BaseModel):
    folders: list[str]
    tabs: list[dict]


class Folder(BaseModel):
    id: int | None
    path: str
    name: str
    parent: int | None = None
    children: Dict[str, Folder] = {}


class Tab(BaseModel):
    id: int | None = None
    data: dict | None = None


class PathRequest(BaseModel):
    path: str


class UpdateCounter(CamelModel):
    action: int = 0
    image: int = 0


class StatusUpdate(CamelModel):
    tasks: List[TaskState] = []
    plugin_loaded = False
    update = UpdateCounter()


class TaskState(BaseModel):
    name: str
    id: str
    total: int
    remain: int
    computing: int = 0
    done: bool = True


@dataclass(slots=True)
class Clusters:
    clusters: list[list[str]]
    distances: list[int]


class ActionContext(CamelModel):
    instance_ids: List[int] | None
    property_ids: List[int] | None
    file: str | None
    text: str | None
    ui_inputs: Dict[str, Any] = {}


class ParamDescription(CamelModel):
    name: str
    description: str | None
    type: str
    default_value: Any


class FunctionDescription(CamelModel):
    id: str
    name: str
    description: str | None
    action: str
    params: List[ParamDescription] = []


class PluginBaseParamsDescription(BaseModel):
    description: str | None
    params: List[ParamDescription] = []


class PluginDefaultParams(BaseModel):
    name: str
    # example: base.export_path = 'my/path'
    base: Dict[str, Any] = {}
    # example: functions.my_func.param1 = 'default_value'
    functions: Dict[str, Dict[str, Any]] = {}


class PluginDescription(CamelModel):
    name: str
    description: str | None
    path: str
    base_params: PluginBaseParamsDescription
    registered_functions: List[FunctionDescription] = []
    defaults: PluginDefaultParams


class ActionDescription(CamelModel):
    name: str
    selected_function: str | None
    available_functions: List[str] = []


class ActionParam(CamelModel):
    name: str
    value: str


class SetMode(Enum):
    set = 'set'
    add = 'add'
    delete = 'delete'


JSON: TypeAlias = Union[dict[str, "JSON"], list["JSON"], str, int, float, bool, None]
Tags: TypeAlias = dict[int, dict[int, Tag]]
# Properties: TypeAlias = dict[int, Property]
