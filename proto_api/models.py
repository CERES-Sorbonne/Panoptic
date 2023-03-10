from enum import Enum
from typing import TypeAlias, Optional, Any, Union

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


JSON: TypeAlias = Union[dict[str, "JSON"], list["JSON"], str, int, float, bool, None]


class Tag(BaseModel):
    id: int
    property_id: int
    parents: list[int]
    value: str

class PropertyValue(Property):
    value: Any


class Image(BaseModel):
    sha1: str
    url: str
    data: dict[int, PropertyValue]


Images: TypeAlias = dict[str, Image]