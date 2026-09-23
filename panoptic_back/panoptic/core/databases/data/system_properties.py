from typing import NamedTuple

from panoptic.core.databases.data.models import Property


class SystemProperty(NamedTuple):
    key: str     # system_key identifier
    dtype: str   # property dtype ('id', 'sha1', 'text', 'number', 'date', 'folder')
    mode: str    # property mode: 'id' | 'sha1' | 'file'
    source: str  # DB lookup source: 'instance' | 'file'
    col: str     # column name in that source table


SYSTEM_PROPERTIES: list[SystemProperty] = [
    SystemProperty('id',         'id',     'id',   'instance', 'id'),
    SystemProperty('sha1',       'sha1',   'sha1', 'instance', 'sha1'),
    SystemProperty('file_id',    'number', 'id',   'instance', 'file_id'),
    SystemProperty('folder',     'folder', 'sha1', 'file',     'folder_id'),
    SystemProperty('name',       'text',   'file', 'file',     'name'),
    SystemProperty('format',     'text',   'sha1', 'file',     'format'),
    SystemProperty('width',      'number', 'sha1', 'file',     'width'),
    SystemProperty('height',     'number', 'sha1', 'file',     'height'),
    SystemProperty('created_at', 'date',   'file', 'file',     'created_at'),
]

# Keyed lookup for O(1) access by system_key
SYSTEM_PROPERTY_MAP: dict[str, SystemProperty] = {p.key: p for p in SYSTEM_PROPERTIES}


def is_system(prop: Property) -> bool:
    """A property is a system / metadata property if panoptic computes it from the
    instance or file tables (system_key). Those cannot be deleted: dropping one
    orphans its system_key resolution. Plain read-only properties (access='read',
    owned by a plugin or an import) can be deleted, only not edited.
    """
    return bool(prop.system_key)


def is_readonly(prop: Property) -> bool:
    """A property is read-only if panoptic computes it (system_key) or its owner
    (a plugin, an import) declared it non-editable via access='read'.

    Only the route layer enforces this: plugins and the importer commit straight
    through DataWriter and must stay able to write their own read-only properties.
    """
    return bool(prop.system_key) or prop.access == 'read'
