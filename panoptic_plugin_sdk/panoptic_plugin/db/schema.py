"""Minimal schema knowledge of the project databases (see DB_FORMAT.md / the python reference
`panoptic/core/databases/**`).

Every query names its columns explicitly: column order can differ in migrated databases
(e.g. `commits.redoable` was appended by ALTER TABLE), so `SELECT *` is never used.
"""
from __future__ import annotations

import datetime
import json
from array import array
from dataclasses import dataclass, field

from .. import models as m

try:
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None

OP_CREATE = 1
OP_UPDATE = 0
OP_DELETE = -1

# Synthetic always-enabled commit holding the folded baseline (data/create.py)
GENESIS_COMMIT_ID = 0
# SQLite variable budget per statement used by the reference (entity_schema._SQLITE_MAX_VARS)
MAX_VARS = 900

TAG_DTYPES = {'tag', 'multi_tags'}
MONO_TAG_DTYPE = 'tag'


@dataclass(frozen=True)
class Table:
    name: str
    model: type
    columns: tuple[str, ...]          # data columns, struct field order (no commit_id/operation)
    pk: tuple[str, ...]
    logged: bool = False              # has commit_id + operation columns (result tables)
    sequenced: bool = False           # has a `sequence` column (delta sync)
    json_cols: frozenset = frozenset()
    array_cols: frozenset = frozenset()
    bool_cols: frozenset = frozenset()
    ts_cols: frozenset = frozenset()

    @property
    def row_columns(self) -> tuple[str, ...]:
        """Columns a full row upsert writes (struct fields, then sequence)."""
        cols = self.columns + (('commit_id', 'operation') if self.logged else ())
        return cols + (('sequence',) if self.sequenced else ())

    @property
    def model_columns(self) -> tuple[str, ...]:
        """Columns that map to the model fields (what reads select)."""
        return self.columns + (('commit_id', 'operation') if self.logged else ())

    def select_sql(self) -> str:
        return f"SELECT {', '.join(self.model_columns)} FROM {self.name}"

    # -- decoding -------------------------------------------------------------------------
    def decode(self, row: tuple):
        data = dict(zip(self.model_columns, row))
        for c in self.json_cols:
            data[c] = json_load(data.get(c))
        for c in self.array_cols:
            if data.get(c) is not None:
                data[c] = decode_vector(data[c])
        for c in self.bool_cols:
            if data.get(c) is not None:
                data[c] = bool(data[c])
        for c in self.ts_cols:
            if isinstance(data.get(c), (str, bytes)):
                data[c] = parse_timestamp(data[c])
        return self.model(**data)

    # -- encoding -------------------------------------------------------------------------
    def encode(self, obj, sequence: int | None = None) -> list:
        """Row values in `row_columns` order (json.dumps for JSON columns, like the reference)."""
        row = []
        for c in self.model_columns:
            v = getattr(obj, c)
            if v is not None:
                if c in self.json_cols:
                    v = json.dumps(v)
                elif c in self.array_cols:
                    v = encode_vector(v)
                elif c in self.ts_cols and isinstance(v, datetime.datetime):
                    v = v.isoformat(' ')
                elif c in self.bool_cols:
                    v = int(bool(v))
            row.append(v)
        if self.sequenced:
            row.append(sequence)
        return row

    def upsert_sql(self, n: int) -> str:
        cols = self.row_columns
        ph = '(' + ', '.join(['?'] * len(cols)) + ')'
        return f"INSERT OR REPLACE INTO {self.name} ({', '.join(cols)}) VALUES {', '.join([ph] * n)}"


def json_load(v):
    """Decode a JSON-declared column. Such columns have NUMERIC affinity in SQLite, so a
    json.dumps'd number comes back as an int/float, not as text."""
    if isinstance(v, (str, bytes)):
        return json.loads(v)
    return v


def parse_timestamp(val) -> datetime.datetime:
    """Same parsing as the reference sqlite3 converter (sqlite_types.py)."""
    if isinstance(val, str):
        val = val.encode()
    datepart, timepart = val.split(b" ")
    year, month, day = map(int, datepart.split(b"-"))
    timepart_full = timepart.split(b".")
    hours, minutes, seconds = map(int, timepart_full[0].split(b":"))
    microseconds = int('{:0<6.6}'.format(timepart_full[1].decode())) if len(timepart_full) == 2 else 0
    return datetime.datetime(year, month, day, hours, minutes, seconds, microseconds)


def decode_vector(blob: bytes):
    """Vectors are raw little-endian float32 (numpy `tobytes()` of a float32 array)."""
    if _np is not None:
        return _np.frombuffer(blob, dtype=_np.float32)
    a = array('f')
    a.frombytes(blob)
    return a


def encode_vector(data) -> bytes:
    if _np is not None and isinstance(data, _np.ndarray):
        return data.astype(_np.float32, copy=False).tobytes()
    if isinstance(data, array) and data.typecode == 'f':
        return data.tobytes()
    return array('f', data).tobytes()


# ---------------------------------------------------------------------------
# data.db
# ---------------------------------------------------------------------------

COMMITS = Table('commits', m.Commit,
                ('id', 'group_id', 'source', 'timestamp', 'active', 'author', 'redoable'), ('id',),
                ts_cols=frozenset({'timestamp'}))
FILE_SOURCES = Table('file_sources', m.FileSource,
                     ('id', 'dtype', 'name', 'root_url', 'metadata', 'sync_status'), ('id',),
                     sequenced=True, json_cols=frozenset({'metadata', 'sync_status'}))
FOLDERS = Table('folders', m.Folder, ('id', 'source_id', 'path', 'name', 'parent'), ('id',),
                sequenced=True)
FILES = Table('files', m.File,
              ('id', 'name', 'folder_id', 'sha1', 'width', 'height', 'format', 'created_at'), ('id',),
              sequenced=True, ts_cols=frozenset({'created_at'}))
INSTANCES = Table('instances', m.Instance, ('id', 'file_id', 'sha1'), ('id',), sequenced=True)
PROPERTIES = Table('properties', m.Property,
                   ('id', 'dtype', 'mode', 'name', 'access', 'tag_list_id', 'system_key',
                    'property_group_id'), ('id',), logged=True, sequenced=True)
PROPERTY_GROUPS = Table('property_groups', m.PropertyGroup, ('id', 'name'), ('id',),
                        logged=True, sequenced=True)
TAGS = Table('tags', m.Tag, ('id', 'list_id', 'parents', 'value', 'color'), ('id',),
             logged=True, sequenced=True, json_cols=frozenset({'parents'}))
INSTANCE_VALUES = Table('instance_values', m.InstanceValue, ('property_id', 'instance_id', 'value'),
                        ('property_id', 'instance_id'), logged=True, sequenced=True,
                        json_cols=frozenset({'value'}))
SHA1_VALUES = Table('sha1_values', m.Sha1Value, ('property_id', 'sha1', 'value'),
                    ('property_id', 'sha1'), logged=True, sequenced=True, json_cols=frozenset({'value'}))
FILE_VALUES = Table('file_values', m.FileValue, ('property_id', 'file_id', 'value'),
                    ('property_id', 'file_id'), logged=True, sequenced=True,
                    json_cols=frozenset({'value'}))
INSTANCE_TAG_VALUES = Table('instance_tag_values', m.InstanceTagValue,
                            ('instance_id', 'property_id', 'tag_id'),
                            ('instance_id', 'property_id', 'tag_id'), logged=True, sequenced=True)
SHA1_TAG_VALUES = Table('sha1_tag_values', m.Sha1TagValue, ('sha1', 'property_id', 'tag_id'),
                        ('sha1', 'property_id', 'tag_id'), logged=True, sequenced=True)

# Structural tables: sequenced, never logged, never written by plugins.
STRUCTURAL_TABLES = (FILE_SOURCES, FOLDERS, FILES, INSTANCES)
# Tables whose `sequence` column feeds the delta (DataReader.get_delta)
SEQUENCED_TABLES = ('instances', 'files', 'folders', 'properties', 'property_groups', 'tags',
                    'instance_values', 'sha1_values', 'file_values', 'instance_tag_values',
                    'sha1_tag_values')


@dataclass(frozen=True)
class EntitySpec:
    """One logged entity kind (data/create.py LOGGED_ENTITY_META)."""
    entity_type: str
    table: Table
    pk_fields: tuple
    data_fields: tuple = ()
    set_fields: tuple = ()
    presence_only: bool = False
    # property-value merge rule (PropertyValueSchema) — informative only
    is_value: bool = field(default=False)


ENTITY_SPECS: dict[str, EntitySpec] = {s.entity_type: s for s in [
    EntitySpec('property', PROPERTIES, ('id',),
               ('dtype', 'mode', 'name', 'access', 'tag_list_id', 'system_key', 'property_group_id')),
    EntitySpec('group', PROPERTY_GROUPS, ('id',), ('name',)),
    EntitySpec('tag', TAGS, ('id',), ('list_id', 'value', 'color'), ('parents',)),
    EntitySpec('instance_value', INSTANCE_VALUES, ('property_id', 'instance_id'), ('value',), is_value=True),
    EntitySpec('sha1_value', SHA1_VALUES, ('property_id', 'sha1'), ('value',), is_value=True),
    EntitySpec('file_value', FILE_VALUES, ('property_id', 'file_id'), ('value',), is_value=True),
    EntitySpec('instance_tag_value', INSTANCE_TAG_VALUES, ('instance_id', 'property_id', 'tag_id'),
               presence_only=True),
    EntitySpec('sha1_tag_value', SHA1_TAG_VALUES, ('sha1', 'property_id', 'tag_id'), presence_only=True),
]}

# (junction entity type -> anchor pk field): the two cell-shaped tag junctions
TAG_JUNCTIONS = {'instance_tag_value': 'instance_id', 'sha1_tag_value': 'sha1'}


def encode_key(pk) -> str:
    """JSON pk tuple used as entity_log.entity_key (resolver.encode_key)."""
    return json.dumps(list(pk), separators=(',', ':'))


def decode_key(key: str) -> list:
    return json.loads(key)


def key_of(spec: EntitySpec, obj) -> str:
    return encode_key(tuple(getattr(obj, f) for f in spec.pk_fields))


# ---------------------------------------------------------------------------
# media.db
# ---------------------------------------------------------------------------

VECTOR_TYPES = Table('vector_types', m.VectorType, ('id', 'source', 'params'), ('id',),
                     json_cols=frozenset({'params'}))
VECTORS = Table('vectors', m.Vector, ('type_id', 'sha1', 'data'), ('type_id', 'sha1'),
                array_cols=frozenset({'data'}))
IMAGE_TYPES = Table('image_types', m.ImageType, ('id', 'name', 'format', 'width', 'height', 'auto_gen'),
                    ('id',), bool_cols=frozenset({'auto_gen'}))
MAPS = Table('maps', m.Map, ('id', 'source', 'name', 'key', 'count', 'data'), ('id',),
             json_cols=frozenset({'data'}))

# ---------------------------------------------------------------------------
# project.db
# ---------------------------------------------------------------------------

# Keys of the id_registry key-value table (project/models.py IdRegistry)
ID_REGISTRY_KEYS = ('file_sources', 'folders', 'files', 'instances', 'properties', 'tags',
                    'property_groups', 'vector_types', 'image_types', 'image_atlas', 'maps')
# Kinds a plugin may allocate
PLUGIN_ID_KINDS = ('properties', 'tags', 'property_groups', 'vector_types', 'maps')


def plugin_params_user_id(plugin_name: str) -> str:
    """user_defaults.user_id under which a plugin's params are stored (key = 'params')."""
    return f'plugin.{plugin_name}'


def where_in(col: str, n: int) -> str:
    return f"{col} IN ({', '.join(['?'] * n)})"


def chunks(seq: list, size: int = MAX_VARS):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

