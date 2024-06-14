from __future__ import annotations

from typing import Any

from fastapi_camelcase import CamelModel

from .models import PropertyType, ActionParam, ActionContext, SetMode, ColumnOption, Property, InstanceProperty, \
    ImageProperty


class ImagePayload(CamelModel):
    file_path: str


class PropertyPayload(CamelModel):
    name: str
    type: PropertyType
    mode: str = 'id'


class UpdatePropertyPayload(CamelModel):
    id: int
    name: str
    # id: PropertyType | None = None


class ExportPropertiesPayload(CamelModel):
    name: str | None = None
    properties: list[int] | None = None
    images: list[int] | None = None
    export_images: bool | None = None


class SetPropertyValuePayload(CamelModel):
    property_id: int
    instance_ids: list[int] | None = None
    value: Any


class PropertyValuesPayload(CamelModel):
    instance_values: list[InstanceProperty] = []
    image_values: list[ImageProperty] = []


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
    parent_id: list[int] | None = None
    color: int | None = None


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
    function: str = None
    context: ActionContext


class OptionsPayload(CamelModel):
    options: dict[int, ColumnOption]


class ImportPayload(CamelModel):
    properties: dict[int, Property]
    fusion: str = 'new'
    exclude: list[int]
    relative: bool = False


class UIDataPayload(CamelModel):
    key: str = None
    data: Any = None


class PluginParamsPayload(CamelModel):
    plugin: str
    params: Any
