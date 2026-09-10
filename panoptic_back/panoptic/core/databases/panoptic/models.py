from typing import Annotated, Optional

import msgspec

from panoptic.core.databases.entity_schema import PrimaryKey, Index


class PanopticConfig(msgspec.Struct, array_like=True):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    # "stop asking me about old (0.x) projects found on this machine"
    legacy_scan_dismissed: bool = False

class User(msgspec.Struct, array_like=True):
    id: Annotated[str, PrimaryKey]
    name: Annotated[str, Index(unique=True)]
    description: Optional[str]
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


class LegacyMigration(msgspec.Struct, array_like=True):
    """One old (0.x) project folder we have already dealt with.

    `legacy_path` is the identity key: the startup scan only offers a legacy
    project whose path has no `done`/`dismissed` row here.
    """
    legacy_path: Annotated[str, PrimaryKey]
    new_path: Optional[str] = None
    project_id: Optional[str] = None
    shape: Optional[str] = None
    migrated_at: Optional[str] = None
    report_path: Optional[str] = None
    status: Optional[str] = None  # done | failed | dismissed
