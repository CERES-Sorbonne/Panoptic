from typing import Optional, Any
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
    # type: Optional[PropertyType]


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