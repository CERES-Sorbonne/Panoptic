from typing import Annotated, Optional

import msgspec

from panoptic.core.databases.entity_schema import PrimaryKey, Index


class PanopticConfig(msgspec.Struct, array_like=True):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None

class User(msgspec.Struct, array_like=True):
    id: Annotated[str, PrimaryKey]
    name: Annotated[str, Index(unique=True)]
    description: str
    password_hash: Optional[str]

class ProjectKey(msgspec.Struct, array_like=True):
    id: Annotated[str, PrimaryKey]
    path: str
    name: str
    excluded_plugins: list[str]

class PluginKey(msgspec.Struct, array_like=True):
    id: Annotated[str, PrimaryKey]
    install_path: str
    source_type: str
    source_path: str
