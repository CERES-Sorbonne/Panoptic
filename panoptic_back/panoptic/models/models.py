from __future__ import annotations

from enum import Enum
from typing import TypeAlias, Optional, Any, Union, List, Dict

import numpy as np
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
    type: str


class PropertyValue(BaseModel):
    property_id: int
    value: Any


class ImageProperty(PropertyValue):
    sha1: str


class Tag(BaseModel):
    id: int
    property_id: int
    parents: list[int]
    value: str
    color: Optional[str]


class Image(BaseModel):
    sha1: str
    url: str
    width: int
    height: int
    paths: list[str]
    extension: str
    properties: Optional[dict[int, PropertyValue]] = {}
    vector: Any
    ahash: str|None


class ImageVector(BaseModel):
    sha1: str
    vector: numpy.ndarray
    ahash: str

    class Config:
        arbitrary_types_allowed = True


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
    id: int | None
    name: str | None
    data: dict | None


Images: TypeAlias = dict[str, Image]
JSON: TypeAlias = Union[dict[str, "JSON"], list["JSON"], str, int, float, bool, None]
Tags: TypeAlias = dict[int, dict[int, Tag]]
Properties: TypeAlias = dict[int, Property]
