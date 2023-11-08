from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias, Any, Union, Dict

import numpy
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


class Property(BaseModel):
    id: int
    name: str
    type: PropertyType
    mode: str


@dataclass(slots=True)
class PropertyValue:
    property_id: int

    image_id: int
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


@dataclass(slots=True)
class Image:
    # Should be equal order to SQL
    id: int
    folder_id: int
    name: str
    extension: str

    sha1: str
    url: str
    height: int
    width: int

    properties: dict[int, PropertyValue] = field(default_factory=dict)
    ahash: str = field(default=None)


@dataclass(slots=True)
class ImageImportTask:
    image_path: str
    folder_id: int


@dataclass(slots=True)
class ComputedValue:
    sha1: str
    ahash: str
    vector: numpy.ndarray


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
    name: str | None = None
    data: dict | None = None


@dataclass(slots=True)
class Clusters:
    clusters: list[list[str]]
    distances: list[int]

JSON: TypeAlias = Union[dict[str, "JSON"], list["JSON"], str, int, float, bool, None]
Tags: TypeAlias = dict[int, dict[int, Tag]]
Properties: TypeAlias = dict[int, Property]
