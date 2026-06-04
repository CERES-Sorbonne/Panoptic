from typing import Any, Annotated, Optional

import msgspec
import numpy

from panoptic.core.databases.entity_schema import PrimaryKey

class IdRegistry(msgspec.Struct, array_like=True):
    file_sources: int = 1
    folders: int = 1
    files: int = 1
    instances: int = 1
    properties: int = 1
    tags: int = 1
    property_groups: int = 1

    vector_types: int = 1
    image_types: int = 1
    image_atlas: int = 1
    maps: int = 1


class ProjectConfig(msgspec.Struct, array_like=True):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class PluginData(msgspec.Struct, array_like=True):
    plugin_id: Annotated[int, PrimaryKey]
    key: Annotated[str, PrimaryKey]

    data: Any

class TabData(msgspec.Struct, array_like=True):
    id: Annotated[str, PrimaryKey]
    user_id: str

    state: Any
    selection: Optional[Any]

class UserDefaults(msgspec.Struct, array_like=True):
    user_id: Annotated[str, PrimaryKey]
    key: Annotated[str, PrimaryKey]
    data: Any

