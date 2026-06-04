from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List

from pydantic import BaseModel


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
    file = 'file'


@dataclass(slots=True)
class Property:
    id: int
    name: str
    type: PropertyType
    mode: PropertyMode
    property_group_id: int | None = None
    computed: bool = False


@dataclass(slots=True)
class Tag:
    id: int
    property_id: int
    value: str
    parents: list[int]
    color: int

    def __post_init__(self):
        self.value = str(self.value)


@dataclass(slots=True)
class Instance:
    id: int
    folder_id: int
    name: str
    extension: str
    sha1: str
    url: str
    height: int
    width: int


class TaskState(BaseModel):
    id: str
    name: str
    key: str
    total: int = 0
    done: int = 0
    failed: int = 0
    running: bool = False
    finished: bool = False

    @property
    def remain(self) -> int:
        return self.total - self.done - self.failed

    def to_dict(self) -> dict:
        return self.model_dump()


class ProjectSettings(BaseModel):
    image_small_size: int = 128
    image_medium_size: int = 256
    image_large_size: int = 1024

    save_image_small: bool = True
    save_image_medium: bool = True
    save_image_large: bool = False

    save_file_raw: bool = False
