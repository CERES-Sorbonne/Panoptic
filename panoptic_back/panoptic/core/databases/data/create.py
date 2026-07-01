"""create.py
~~~~~~~~~~~~
Schema for the *data* database under the target versioning architecture
(notes/versioning_architecture.md).

Two kinds of table:

* **Result tables** (``properties`` / ``property_groups`` / ``tags`` and the value / junction
  tables) hold the *current resolved state* as fully-typed rows. Reads hit them directly — no
  folding at read time. Each carries ``operation`` (alive vs. tombstone) and ``sequence``
  (delta-sync). They no longer have per-entity ``_log`` tables.
* **One generic log** — ``entity_log`` — stores partial-diff :class:`ChangeOp` rows (only the
  fields a commit changed) for *every* logged entity kind, keyed by a JSON pk tuple. It is the
  single source of truth for undo/redo, folded by ``resolver.resolve``.

Structural tables (``file_sources`` / ``folders`` / ``files`` / ``instances``) remain
sequenced-but-not-logged: imported, hard-deleted, never undone.
"""
from panoptic.core.databases.db_description import DbDescription
from panoptic.core.databases.entity_schema import EntitySchema, PropertyValueSchema
from panoptic.core.databases.data.models import (
    Commit, FileSource, Folder, File, Instance, Property, PropertyGroup, TagList, Tag,
    InstanceValue, Sha1Value, FileValue, InstanceTagValue, Sha1TagValue,
)

COMMITS_SCHEMA = EntitySchema(Commit, table="commits")
# Structural entities: sequenced (delta-synced) but not logged (no undo).
FILE_SOURCES_SCHEMA = EntitySchema(FileSource, table="file_sources", sequenced=True)
FOLDERS_SCHEMA = EntitySchema(Folder, table="folders", sequenced=True)
FILES_SCHEMA = EntitySchema(File, table="files", sequenced=True)
INSTANCES_SCHEMA = EntitySchema(Instance, table="instances", sequenced=True)
# Result tables for logged entities. They keep operation/commit_id/sequence columns (the
# structs are "trackable") but we DO NOT create or use their per-entity `_log` tables — the
# generic `entity_log` is the single journal. `.trackable` still gives us the operation
# column used to mark tombstones and to filter deleted rows on read (get(state=1)).
PROPERTIES_SCHEMA = EntitySchema(Property, table="properties")
PROPERTY_GROUPS_SCHEMA = EntitySchema(PropertyGroup, table="property_groups")
TAG_LISTS_SCHEMA = EntitySchema(TagList, table="tag_lists")
TAGS_SCHEMA = EntitySchema(Tag, table="tags")
INSTANCE_VALUES_SCHEMA = PropertyValueSchema(InstanceValue, table="instance_values")
SHA1_VALUES_SCHEMA = PropertyValueSchema(Sha1Value, table="sha1_values")
FILE_VALUES_SCHEMA = PropertyValueSchema(FileValue, table="file_values")
INSTANCE_TAG_VALUES_SCHEMA = EntitySchema(InstanceTagValue, table="instance_tag_values")
SHA1_TAG_VALUES_SCHEMA = EntitySchema(Sha1TagValue, table="sha1_tag_values")

# ---------------------------------------------------------------------------
# Logged-entity metadata (shared with resolver.py and the genesis migration).
# (entity_type, schema, pk_fields, data_fields, set_fields, presence_only)
# ---------------------------------------------------------------------------
LOGGED_ENTITY_META = [
    ('property', PROPERTIES_SCHEMA, ('id',),
     ('dtype', 'mode', 'name', 'access', 'tag_list_id', 'system_key', 'property_group_id'),
     (), False),
    ('group', PROPERTY_GROUPS_SCHEMA, ('id',), ('name',), (), False),
    ('tag', TAGS_SCHEMA, ('id',), ('list_id', 'value', 'color'), ('parents',), False),
    ('instance_value', INSTANCE_VALUES_SCHEMA, ('property_id', 'instance_id'), ('value',), (), False),
    ('sha1_value', SHA1_VALUES_SCHEMA, ('property_id', 'sha1'), ('value',), (), False),
    ('file_value', FILE_VALUES_SCHEMA, ('property_id', 'file_id'), ('value',), (), False),
    ('instance_tag_value', INSTANCE_TAG_VALUES_SCHEMA, ('instance_id', 'property_id', 'tag_id'), (), (), True),
    ('sha1_tag_value', SHA1_TAG_VALUES_SCHEMA, ('sha1', 'property_id', 'tag_id'), (), (), True),
]

# Synthetic frozen commit that holds the folded baseline (genesis) ops. It is always enabled
# and never surfaced as undoable history. Log compaction rewrites the settled prefix into it.
GENESIS_COMMIT_ID = 0

ENTITY_LOG_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS entity_log ("
    "  entity_type TEXT NOT NULL,"
    "  entity_key  TEXT NOT NULL,"
    "  commit_id   INTEGER NOT NULL,"
    "  op          INTEGER NOT NULL,"
    "  changes     TEXT,"
    "  sequence    INTEGER,"
    "  PRIMARY KEY (entity_type, entity_key, commit_id)"
    ");"
    "CREATE INDEX IF NOT EXISTS idx_entity_log_commit ON entity_log (commit_id);"
    "CREATE INDEX IF NOT EXISTS idx_entity_log_entity ON entity_log (entity_type, entity_key, commit_id);"
)

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

# Only result/current-state tables are created here. No per-entity `_log` tables: the generic
# `entity_log` (below) is the single journal.
tables_config = {s.table: s.create_table_sql() for s in ALL_SCHEMAS}
tables_config['entity_log'] = ENTITY_LOG_SCHEMA
tables_config['sequence'] = sequence_table


# No migrations: the data DB is created fresh at the current schema version.
datastore_desc = DbDescription(version=1, tables=tables_config, migrations={})
