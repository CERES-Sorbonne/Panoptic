from typing import NamedTuple


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
