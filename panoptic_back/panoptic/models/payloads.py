from __future__ import annotations

from typing import Any

from fastapi_camelcase import CamelModel

from .models import PropertyType, ActionParam, ActionContext, SetMode, ColumnOption


class ImagePayload(CamelModel):
    file_path: str


class PropertyPayload(CamelModel):
    name: str
    type: PropertyType
    mode: str = 'id'


class UpdatePropertyPayload(CamelModel):
    id: int
    name: str
    # id: PropertyType | None


class ExportPropertiesPayload(CamelModel):
    name: str | None
    properties: list[int] | None
    images: list[int] | None
    export_images: bool | None


class SetPropertyValuePayload(CamelModel):
    property_id: int
    instance_ids: list[int] | None
    value: Any


class SetTagPropertyValuePayload(SetPropertyValuePayload):
    mode: SetMode


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
    parent_id: list[int] | None
    color: int | None


class MakeClusterPayload(CamelModel):
    nb_groups: int = 50
    image_list: list[str] = []


class GetSimilarImagesPayload(CamelModel):
    sha1_list: list[str]


class GetSimilarImagesFromTextPayload(CamelModel):
    input_text: str


class ChangeProjectPayload(CamelModel):
    project: str


class StrPayload(CamelModel):
    value: str


class UpdateActionsPayload(CamelModel):
    updates: list[ActionParam]


class ExecuteActionPayload(CamelModel):
    action: str
    function: str = None
    context: ActionContext


class OptionsPayload(CamelModel):
    options: dict[int, ColumnOption]
