from typing import Optional, Any

from pydantic import BaseModel

from models import DataType, JSON


class ImagePayload(BaseModel):
    file_path: str


class DataPayload(BaseModel):
    name: str
    type: DataType


class UpdateDataPayload(BaseModel):
    id: int
    name: Optional[str]
    type: Optional[DataType]


class DeleteDataPayload(BaseModel):
    id: int


class AddImageDataPayload(BaseModel):
    data_id: int
    sha1: str
    value: Any
