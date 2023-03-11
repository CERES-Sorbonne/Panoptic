from typing import Optional, Any

from pydantic import BaseModel

from models import PropertyType, JSON


class ImagePayload(BaseModel):
    file_path: str


class PropertyPayload(BaseModel):
    name: str
    type: PropertyType


class UpdatePropertyPayload(BaseModel):
    id: int
    name: Optional[str]
    type: Optional[PropertyType]


class DeletePropertyPayload(BaseModel):
    id: int


class AddImagePropertyPayload(BaseModel):
    property_id: int
    sha1: str
    value: Any


class DeleteImagePropertyPayload(BaseModel):
    property_id: int
    sha1: str


class AddTagPayload(BaseModel):
    property_id: int
    value: str
    parent_id: Optional[int] = None
    color: Optional[str]


class UpdateTagPayload(BaseModel):
    id: int
    value: Optional[str]
    parent_id: Optional[int]
    color: Optional[str]