from panoptic.core.databases.db_description import DbDescription
from panoptic.core.databases.entity_schema import EntitySchema, PropertyValueSchema, OP_DELETE
from panoptic.core.databases.data.models import Commit, FileSource, Folder, File, Instance, Property, PropertyGroup, TagList, Tag, InstanceValue, \
    Sha1Value, FileValue, InstanceTagValue, Sha1TagValue

COMMITS_SCHEMA = EntitySchema(Commit, table="commits")
# Structural entities: sequenced (delta-synced) but not logged (no undo).
FILE_SOURCES_SCHEMA = EntitySchema(FileSource, table="file_sources", sequenced=True)
FOLDERS_SCHEMA = EntitySchema(Folder, table="folders", sequenced=True)
FILES_SCHEMA = EntitySchema(File, table="files", sequenced=True)
INSTANCES_SCHEMA = EntitySchema(Instance, table="instances", sequenced=True)
PROPERTIES_SCHEMA = EntitySchema(Property, table="properties")
PROPERTY_GROUPS_SCHEMA = EntitySchema(PropertyGroup, table="property_groups")
TAG_LISTS_SCHEMA = EntitySchema(TagList, table="tag_lists")
TAGS_SCHEMA = EntitySchema(Tag, table="tags")
INSTANCE_VALUES_SCHEMA = PropertyValueSchema(InstanceValue, table="instance_values")
SHA1_VALUES_SCHEMA = PropertyValueSchema(Sha1Value, table="sha1_values")
FILE_VALUES_SCHEMA = PropertyValueSchema(FileValue, table="file_values")
INSTANCE_TAG_VALUES_SCHEMA = EntitySchema(InstanceTagValue, table="instance_tag_values")
SHA1_TAG_VALUES_SCHEMA = EntitySchema(Sha1TagValue, table="sha1_tag_values")

sequence_table = (
    "CREATE TABLE IF NOT EXISTS sequence (id INTEGER);"
    "INSERT INTO sequence (id) VALUES (1);"
)

ALL_SCHEMAS = [
    COMMITS_SCHEMA,
    FILE_SOURCES_SCHEMA,
    FOLDERS_SCHEMA,
    FILES_SCHEMA,
    INSTANCES_SCHEMA,
    PROPERTIES_SCHEMA,
    PROPERTY_GROUPS_SCHEMA,
    TAG_LISTS_SCHEMA,
    TAGS_SCHEMA,
    INSTANCE_VALUES_SCHEMA,
    SHA1_VALUES_SCHEMA,
    FILE_VALUES_SCHEMA,
    INSTANCE_TAG_VALUES_SCHEMA,
    SHA1_TAG_VALUES_SCHEMA,
]

# Build the tables dictionary dynamically
tables_config = {}
for s in ALL_SCHEMAS:
    tables_config[s.table] = s.create_table_sql()
    if s.trackable:
        tables_config[f"{s.table}_log"] = s.create_log_table_sql()

tables_config['sequence'] = sequence_table


def _migrate_v1_to_v2(writer):
    """Add file_values and file_values_log tables (introduced in v2)."""
    writer.conn.executescript(FILE_VALUES_SCHEMA.create_table_sql())
    writer.conn.executescript(FILE_VALUES_SCHEMA.create_log_table_sql())


def _migrate_v2_to_v3(writer):
    """Consolidated migration from v2 (first deployed version):
    - add system_key to properties
    - add width/height/format/created_at to files
    - fix file name to basename only
    - backfill new columns from old file_values
    - remove old mode='file' metadata properties
    """
    import json as _json
    import os as _os

    # system_key on properties
    if writer._table_exists('properties'):
        writer.conn.execute("ALTER TABLE properties ADD COLUMN system_key TEXT")
    if writer._table_exists('properties_log'):
        writer.conn.execute("ALTER TABLE properties_log ADD COLUMN system_key TEXT")

    # new file columns
    if writer._table_exists('files'):
        for col_def in ('width INTEGER', 'height INTEGER', 'format TEXT', 'created_at TIMESTAMP'):
            writer.conn.execute(f"ALTER TABLE files ADD COLUMN {col_def}")
    if writer._table_exists('files_log'):
        for col_def in ('width INTEGER', 'height INTEGER', 'format TEXT', 'created_at TIMESTAMP'):
            writer.conn.execute(f"ALTER TABLE files_log ADD COLUMN {col_def}")

    if not writer._table_exists('files'):
        return

    # Fix name: strip folder path prefix so only the filename remains
    rows = writer.conn.execute(
        "SELECT f.id, f.name, fo.path FROM files f "
        "LEFT JOIN folders fo ON fo.id = f.folder_id"
    ).fetchall()
    name_updates = []
    for file_id, name, folder_path in rows:
        if not name:
            continue
        if folder_path and name.startswith(folder_path):
            basename = name[len(folder_path):].lstrip('/\\')
        else:
            basename = _os.path.basename(name)
        if basename != name:
            name_updates.append((basename, file_id))
    if name_updates:
        writer.conn.executemany("UPDATE files SET name = ? WHERE id = ?", name_updates)

    if not writer._table_exists('file_values') or not writer._table_exists('properties'):
        return

    # Backfill width, height, format from old file_values
    prop_rows = writer.conn.execute(
        "SELECT id, name FROM properties WHERE mode = 'file' AND name IN ('width', 'height', 'extension')"
    ).fetchall()
    col_map = {'width': 'width', 'height': 'height', 'extension': 'format'}
    for prop_id, prop_name in prop_rows:
        col = col_map[prop_name]
        fv_rows = writer.conn.execute(
            "SELECT file_id, value FROM file_values WHERE property_id = ?", (prop_id,)
        ).fetchall()
        updates = []
        for file_id, raw in fv_rows:
            try:
                val = _json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                if val is not None:
                    updates.append((val, file_id))
            except Exception:
                pass
        if updates:
            writer.conn.executemany(f"UPDATE files SET {col} = ? WHERE id = ?", updates)

    # Remove all mode='file' metadata properties and their values
    old_ids = [r[0] for r in writer.conn.execute(
        "SELECT id FROM properties WHERE mode = 'file'"
    ).fetchall()]
    if old_ids:
        ph = ','.join('?' * len(old_ids))
        writer.conn.execute(f"DELETE FROM file_values WHERE property_id IN ({ph})", old_ids)
        if writer._table_exists('file_values_log'):
            writer.conn.execute(f"DELETE FROM file_values_log WHERE property_id IN ({ph})", old_ids)
        writer.conn.execute(f"DELETE FROM properties WHERE id IN ({ph})", old_ids)
        if writer._table_exists('properties_log'):
            writer.conn.execute(f"DELETE FROM properties_log WHERE id IN ({ph})", old_ids)


def _migrate_v3_to_v4(writer):
    """Add instance_tag_values and sha1_tag_values tables (introduced in v4)."""
    writer.conn.executescript(INSTANCE_TAG_VALUES_SCHEMA.create_table_sql())
    writer.conn.executescript(INSTANCE_TAG_VALUES_SCHEMA.create_log_table_sql())
    writer.conn.executescript(SHA1_TAG_VALUES_SCHEMA.create_table_sql())
    writer.conn.executescript(SHA1_TAG_VALUES_SCHEMA.create_log_table_sql())


def _migrate_v4_to_v5(writer):
    """Add property_groups table and property_group_id column on properties (introduced in v5)."""
    writer.conn.executescript(PROPERTY_GROUPS_SCHEMA.create_table_sql())
    writer.conn.executescript(PROPERTY_GROUPS_SCHEMA.create_log_table_sql())
    if writer._table_exists('properties'):
        writer.conn.execute("ALTER TABLE properties ADD COLUMN property_group_id INTEGER")
    if writer._table_exists('properties_log'):
        writer.conn.execute("ALTER TABLE properties_log ADD COLUMN property_group_id INTEGER")


_STRUCTURAL_SCHEMAS = (FILE_SOURCES_SCHEMA, FOLDERS_SCHEMA, FILES_SCHEMA, INSTANCES_SCHEMA)


def _make_structural_unlogged(writer):
    """Idempotent: make the structural tables sequenced-but-not-logged.

    They must not carry commit_id/operation columns and must have no _log table (imports
    are never undone). Done by a deterministic table REBUILD — copy the surviving columns
    into a freshly-created table — rather than ALTER ... DROP COLUMN, which can fail
    silently on some DBs and leave the table half-migrated (breaking row decoding).
    """
    for schema in _STRUCTURAL_SCHEMAS:
        t = schema.table
        if writer._table_exists(t):
            cols = [r[1] for r in writer.conn.execute(f"PRAGMA table_info({t})")]
            if 'commit_id' in cols or 'operation' in cols:
                target = [c.name for c in schema.columns]
                if 'sequence' in cols:
                    target.append('sequence')
                copy = [c for c in target if c in cols]
                csv = ', '.join(copy)
                writer.conn.execute(f"DROP TABLE IF EXISTS {t}_old")
                writer.conn.execute(f"ALTER TABLE {t} RENAME TO {t}_old")
                writer.conn.executescript(schema.create_table_sql())
                writer.conn.execute(f"INSERT INTO {t} ({csv}) SELECT {csv} FROM {t}_old")
                writer.conn.execute(f"DROP TABLE {t}_old")
            else:
                # Already clean — just make sure the new indexes (e.g. sha1) exist.
                writer.conn.executescript(schema.create_table_sql())
        writer.conn.execute(f"DROP TABLE IF EXISTS {t}_log")


def _migrate_v5_to_v6(writer):
    """Structural entities become sequenced-but-not-logged (see _make_structural_unlogged)."""
    _make_structural_unlogged(writer)


def _migrate_v6_to_v7(writer):
    """Repair pass: the first v5->v6 migration used ALTER ... DROP COLUMN wrapped in a
    swallowed try/except, which could bump the version to 6 while leaving structural tables
    still carrying commit_id/operation (breaking decoding). Re-run idempotently."""
    _make_structural_unlogged(writer)


datastore_desc = DbDescription(
    version=7,
    tables=tables_config,
    migrations={1: _migrate_v1_to_v2, 2: _migrate_v2_to_v3, 3: _migrate_v3_to_v4,
                4: _migrate_v4_to_v5, 5: _migrate_v5_to_v6, 6: _migrate_v6_to_v7},
)