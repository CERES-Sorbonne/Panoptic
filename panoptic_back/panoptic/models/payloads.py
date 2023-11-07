from __future__ import annotations

from typing import Any
from fastapi_camelcase import CamelModel
from .models import PropertyType, JSON


class ImagePayload(CamelModel):
    file_path: str


class PropertyPayload(CamelModel):
    name: str
    type: PropertyType
    mode: str = 'id'


class UpdatePropertyPayload(CamelModel):
    id: int
    name: str
    # type: PropertyType | None


class ExportPropertiesPayload(CamelModel):
    properties: list[int] | None
    images: list[int] | None


class SetPropertyValuePayload(CamelModel):
    property_id: int
    image_ids: list[int] | None
    sha1s: list[str] | None
    value: Any
    mode: str | None


class DeleteImagePropertyPayload(CamelModel):
    property_id: int
    image_id: int


class AddTagPayload(CamelModel):
    property_id: int
    value: str
    parent_id: int = None
    color: int = 0


class AddTagParentPayload(CamelModel):
    tag_id: int
    parent_id: int


class UpdateTagPayload(CamelModel):
    id: int
    value: str
    parent_id: list[int]
    color: int


class MakeClusterPayload(CamelModel):
    nb_groups: int = 50
    image_list: list[str] = []


class GetSimilarImagesPayload(CamelModel):
    sha1_list: list[str]


class GetSimilarImagesFromTextPayload(CamelModel):
    input_text: str


class ChangeProjectPayload(CamelModel):
    project: str
