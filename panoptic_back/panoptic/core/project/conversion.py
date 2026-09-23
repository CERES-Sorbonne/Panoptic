"""Detect and convert project folders whose data DB predates the generic-log rewrite.

Before the rewrite, every logged entity had its own ``<table>_log`` table and the result
tables were written directly. The current writer resolves logged entities from
``entity_log`` only, so such a DB is unusable as-is: its result rows have no genesis op and
the first edit of any of them tombstones it (and older layouts even crash on read, because
their column lists differ).

Conversion rebuilds ``data.db`` from the *current state* of the old result tables:

* structural rows (sources / folders / files / instances) are copied as-is;
* alive logged rows go through one ``apply_commit`` which is then compacted into the
  genesis baseline, so the tag-junction expansion and mono-tag rules are the writer's own.

The undo history is not carried over. The old file is kept next to the new one as a
complete backup (``data.db.backup-<timestamp>``), written with the SQLite backup API so the
WAL content is included and the original is never modified before the swap.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import msgspec

from panoptic.core.databases.data.create import (
    datastore_desc, ALL_SCHEMAS, FILE_SOURCES_SCHEMA, FOLDERS_SCHEMA, FILES_SCHEMA,
    INSTANCES_SCHEMA, PROPERTIES_SCHEMA, PROPERTY_GROUPS_SCHEMA, TAG_LISTS_SCHEMA, TAGS_SCHEMA,
    INSTANCE_VALUES_SCHEMA, SHA1_VALUES_SCHEMA, FILE_VALUES_SCHEMA,
    INSTANCE_TAG_VALUES_SCHEMA, SHA1_TAG_VALUES_SCHEMA,
)
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.data.models import (
    DataCommit, FileSource, Folder, File, Instance, Property, PropertyGroup, TagList, Tag,
    InstanceValue, Sha1Value, FileValue,
)
from panoptic.core.databases.entity_schema import OP_CREATE, OP_DELETE
from panoptic.models.models import PropertyType

logger = logging.getLogger(__name__)

STATUS_OK = 'ok'
STATUS_OUTDATED = 'outdated'          # old data DB layout: can be converted
STATUS_INCOMPATIBLE = 'incompatible'  # unknown / newer layout: cannot be opened
STATUS_MISSING = 'missing'            # folder or project.db is gone

DATA_DB = 'data.db'
_TAG_DTYPES = {PropertyType.tag.value, PropertyType.multi_tags.value}
# Tables that had a per-entity `_log` table before the rewrite.
_LOGGED_TABLES = ('properties', 'property_groups', 'tags', 'instance_values', 'sha1_values',
                  'file_values', 'instance_tag_values', 'sha1_tag_values')

_expected_columns: dict[str, list[str]] | None = None


class ProjectCompatibility(msgspec.Struct):
    status: str
    reason: str | None = None


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def _get_expected_columns() -> dict[str, list[str]]:
    """Column lists of the current data DB layout, read from a throwaway in-memory DB."""
    global _expected_columns
    if _expected_columns is None:
        conn = sqlite3.connect(':memory:')
        try:
            for schema in ALL_SCHEMAS:
                conn.executescript(schema.create_table_sql())
            _expected_columns = {s.table: _columns(conn, s.table) for s in ALL_SCHEMAS}
        finally:
            conn.close()
    return _expected_columns


def _open_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, detect_types=sqlite3.PARSE_DECLTYPES)


def check_project(folder: str | Path) -> ProjectCompatibility:
    """Classify a project folder without writing to it. Never raises."""
    folder = Path(folder)
    try:
        if not (folder / 'project.db').is_file():
            return ProjectCompatibility(STATUS_MISSING, f"{folder} has no project.db")
        data_path = folder / DATA_DB
        if not data_path.is_file():
            return ProjectCompatibility(STATUS_OK)
        conn = _open_readonly(data_path)
        try:
            return _check_data_db(conn)
        finally:
            conn.close()
    except (OSError, sqlite3.Error) as exc:
        return ProjectCompatibility(STATUS_INCOMPATIBLE, f"cannot read the project: {exc}")


def _check_data_db(conn: sqlite3.Connection) -> ProjectCompatibility:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    legacy_logs = sorted(f"{t}_log" for t in _LOGGED_TABLES if f"{t}_log" in tables)
    if legacy_logs:
        return ProjectCompatibility(STATUS_OUTDATED, "data DB uses the per-entity log layout")

    # Result rows without any journal would be tombstoned on their first edit.
    if 'properties' in tables and conn.execute("SELECT 1 FROM properties LIMIT 1").fetchone():
        if 'entity_log' not in tables or not conn.execute("SELECT 1 FROM entity_log LIMIT 1").fetchone():
            return ProjectCompatibility(STATUS_OUTDATED, "data DB has no entity_log journal")

    version = datastore_desc.version
    if '_version' in tables:
        row = conn.execute("SELECT value FROM _version WHERE key = 'db_version'").fetchone()
        version = row[0] if row else 1
    if version > datastore_desc.version:
        return ProjectCompatibility(
            STATUS_INCOMPATIBLE, f"data DB version {version} is newer than this Panoptic")

    # Below the current version the migrations still have to run and fix the columns.
    if version == datastore_desc.version:
        for table, expected in _get_expected_columns().items():
            if table in tables and _columns(conn, table) != expected:
                return ProjectCompatibility(STATUS_OUTDATED, f"table {table!r} has an old column layout")

    return ProjectCompatibility(STATUS_OK)


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def _rows(conn: sqlite3.Connection, table: str, tables: set[str]) -> list[dict]:
    if table not in tables:
        return []
    cur = conn.execute(f"SELECT * FROM {table}")
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur]


def _json(value):
    if isinstance(value, (str, bytes)):
        return json.loads(value)
    return value


def _build(struct_cls, row: dict, json_fields: tuple[str, ...] = ()):
    """Struct from an old row, by column name: missing columns take the field default."""
    data = {}
    for f in msgspec.structs.fields(struct_cls):
        if f.name in ('commit_id', 'operation'):
            continue
        if f.name in row:
            v = row[f.name]
            data[f.name] = _json(v) if (f.name in json_fields and v is not None) else v
        elif f.required:
            data[f.name] = None
    return struct_cls(**data)


def _alive(row: dict) -> bool:
    return row.get('operation') != OP_DELETE


def _read_old(conn: sqlite3.Connection) -> tuple[dict, DataCommit]:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def rows(schema):
        return _rows(conn, schema.table, tables)

    structural = {
        'file_sources': [_build(FileSource, r, ('metadata', 'sync_status')) for r in rows(FILE_SOURCES_SCHEMA)],
        'folders': [_build(Folder, r) for r in rows(FOLDERS_SCHEMA)],
        'files': [_build(File, r) for r in rows(FILES_SCHEMA)],
        'instances': [_build(Instance, r) for r in rows(INSTANCES_SCHEMA)],
        'tag_lists': [_build(TagList, r) for r in rows(TAG_LISTS_SCHEMA)],
    }

    groups = [_build(PropertyGroup, r) for r in rows(PROPERTY_GROUPS_SCHEMA) if _alive(r)]
    properties = [_build(Property, r) for r in rows(PROPERTIES_SCHEMA) if _alive(r)]
    tags = [_build(Tag, r, ('parents',)) for r in rows(TAGS_SCHEMA) if _alive(r)]
    for x in (*groups, *properties, *tags):
        x.operation = OP_CREATE

    dtypes = {p.id: p.dtype for p in properties}
    tag_ids = {t.id for t in tags}
    tag_props = {pid for pid, d in dtypes.items() if d in _TAG_DTYPES}
    group_ids = {g.id for g in groups}
    for p in properties:
        # a property must not point at a group that no longer exists
        if p.property_group_id is not None and p.property_group_id not in group_ids:
            p.property_group_id = None

    def scalar_values(schema, cls, anchor):
        res = []
        for r in rows(schema):
            if not _alive(r) or r['property_id'] not in dtypes or r['property_id'] in tag_props:
                continue
            res.append(cls(**{'property_id': r['property_id'], anchor: r[anchor],
                              'value': _json(r['value']) if r['value'] is not None else None}))
        return res

    def tag_values(schema, cls, anchor):
        cells: dict[tuple, list[int]] = {}
        for r in rows(schema):
            if not _alive(r) or r['property_id'] not in tag_props or r['tag_id'] not in tag_ids:
                continue
            cells.setdefault((r['property_id'], r[anchor]), []).append(r['tag_id'])
        return [cls(**{'property_id': pid, anchor: a, 'value': sorted(ids)})
                for (pid, a), ids in cells.items()]

    commit = DataCommit(
        property_groups=groups,
        properties=properties,
        tags=tags,
        instance_values=scalar_values(INSTANCE_VALUES_SCHEMA, InstanceValue, 'instance_id')
                        + tag_values(INSTANCE_TAG_VALUES_SCHEMA, InstanceValue, 'instance_id'),
        sha1_values=scalar_values(SHA1_VALUES_SCHEMA, Sha1Value, 'sha1')
                    + tag_values(SHA1_TAG_VALUES_SCHEMA, Sha1Value, 'sha1'),
        file_values=scalar_values(FILE_VALUES_SCHEMA, FileValue, 'file_id'),
    )
    return structural, commit


def _remove_db(path: Path) -> None:
    for suffix in ('', '-wal', '-shm'):
        p = Path(str(path) + suffix)
        if p.exists():
            p.unlink()


def convert_project(folder: str | Path) -> Path:
    """Rebuild ``data.db`` in the current layout. Returns the backup path.

    The caller must make sure the project is not loaded.
    """
    folder = Path(folder)
    data_path = folder / DATA_DB
    status = check_project(folder)
    if status.status != STATUS_OUTDATED:
        raise ValueError(f"{folder} does not need a conversion ({status.status})")

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_path = folder / f"{DATA_DB}.backup-{stamp}"
    tmp_path = folder / f"{DATA_DB}.converting"
    _remove_db(tmp_path)

    # 1. complete, self-contained copy of the old DB (WAL included)
    src = _open_readonly(data_path)
    try:
        dst = sqlite3.connect(str(backup_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
        structural, commit = _read_old(src)
    except Exception:
        _remove_db(backup_path)
        raise
    finally:
        src.close()

    # 2. fresh DB in the current layout
    writer = DataWriter(str(tmp_path))
    try:
        writer.start()
        writer.add_structural(
            file_sources=structural['file_sources'], folders=structural['folders'],
            files=structural['files'], instances=structural['instances'],
        )
        if structural['tag_lists']:
            with writer.transaction() as tx:
                TAG_LISTS_SCHEMA.upsert(tx, structural['tag_lists'])
        written = writer.apply_commit('conversion', commit)
        if written is not None:
            writer.compact(written.id)
    except Exception:
        writer.close()
        _remove_db(tmp_path)
        _remove_db(backup_path)
        raise
    writer.close()

    # 3. swap: the backup already holds everything the old files did
    _remove_db(data_path)
    os.replace(tmp_path, data_path)
    _remove_db(tmp_path)
    logger.info("converted %s (backup: %s)", data_path, backup_path.name)
    return backup_path
