from enum import Enum
from typing import TypeAlias, Optional, Any, Union

from pydantic import BaseModel


class DataType(Enum):
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


class DataModel(BaseModel):
    id: int
    name: str
    type: str


JSON: TypeAlias = Union[dict[str, "JSON"], list["JSON"], str, int, float, bool, None]


class DataValue(DataModel):
    value: Any


class Image(BaseModel):
    sha1: str
    url: str
    data: dict[int, DataValue]


Images: TypeAlias = dict[str, Image]