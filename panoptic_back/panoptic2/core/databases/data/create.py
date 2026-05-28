from panoptic2.core.databases.db_description import DbDescription
from panoptic2.core.databases.entity_schema import EntitySchema, PropertyValueSchema
from panoptic2.core.databases.data.models import Commit, FileSource, Folder, File, Instance, Property, TagList, Tag, InstanceValue, \
    Sha1Value, FileValue

COMMITS_SCHEMA = EntitySchema(Commit, table="commits")
FILE_SOURCES_SCHEMA = EntitySchema(FileSource, table="file_sources")
FOLDERS_SCHEMA = EntitySchema(Folder, table="folders")
FILES_SCHEMA = EntitySchema(File, table="files")
INSTANCES_SCHEMA = EntitySchema(Instance, table="instances")
PROPERTIES_SCHEMA = EntitySchema(Property, table="properties")
TAG_LISTS_SCHEMA = EntitySchema(TagList, table="tag_lists")
TAGS_SCHEMA = EntitySchema(Tag, table="tags")
INSTANCE_VALUES_SCHEMA = PropertyValueSchema(InstanceValue, table="instance_values")
SHA1_VALUES_SCHEMA = PropertyValueSchema(Sha1Value, table="sha1_values")
FILE_VALUES_SCHEMA = PropertyValueSchema(FileValue, table="file_values")

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
    TAG_LISTS_SCHEMA,
    TAGS_SCHEMA,
    INSTANCE_VALUES_SCHEMA,
    SHA1_VALUES_SCHEMA,
    FILE_VALUES_SCHEMA,
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


datastore_desc = DbDescription(
    version=3,
    tables=tables_config,
    migrations={1: _migrate_v1_to_v2, 2: _migrate_v2_to_v3},
)