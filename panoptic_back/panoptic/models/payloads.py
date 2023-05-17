from typing import Optional, Any
from fastapi_camelcase import CamelModel

from .models import PropertyType, JSON


class ImagePayload(CamelModel):
    file_path: str


class PropertyPayload(CamelModel):
    name: str
    type: PropertyType


class UpdatePropertyPayload(CamelModel):
    id: int
    name: Optional[str]
    type: Optional[PropertyType]


class AddImagePropertyPayload(CamelModel):
    property_id: int
    sha1: str
    value: Any


class DeleteImagePropertyPayload(CamelModel):
    property_id: int
    sha1: str


class AddTagPayload(CamelModel):
    property_id: int
    value: str
    parent_id: Optional[int] = None
    color: Optional[str]


class UpdateTagPayload(CamelModel):
    id: int
    value: Optional[str]
    parent_id: Optional[int]
    color: Optional[str]


class MakeClusterPayload(CamelModel):
    nb_groups: Optional[int] = 50
    image_list: Optional[list[str]] = []