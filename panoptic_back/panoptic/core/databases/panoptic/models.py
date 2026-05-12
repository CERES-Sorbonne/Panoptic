from typing import Annotated, Optional

import msgspec

from panoptic.core.databases.entity_schema import PrimaryKey


class PanopticConfig(msgspec.Struct, array_like=True):
    uuid: str
    name: str
    description: str

class User(msgspec.Struct, array_like=True):
    uuid: Annotated[str, PrimaryKey]
    name: str
    description: str
    password_hash: Optional[str]

class ProjectKey(msgspec.Struct, array_like=True):
    path: Annotated[str, PrimaryKey]
    excluded_plugins: list[str]

class PluginKey(msgspec.Struct, array_like=True):
    id: Annotated[str, PrimaryKey]
    install_path: str
    source_type: str
    source_path: str
