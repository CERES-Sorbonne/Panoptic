from panoptic.core.databases.data.helper import Col, EntitySchema
from panoptic.core.databases.db_description import DbDescription

COMMITS_SCHEMA = EntitySchema(
    table="commits",
    trackable=False,
    columns=[
        Col("id", "INTEGER", primary_key=True, nullable=False),
        Col("group_id", "INTEGER"),
        Col("source", "TEXT", nullable=False),
        Col("timestamp", "TEXT", nullable=False),
    ]
)

FILE_SOURCES_SCHEMA = EntitySchema(
    table="file_sources",
    columns=[
        Col("id", "TEXT", primary_key=True, nullable=False),
        Col("dtype", "TEXT"),
        Col("name", "TEXT"),
        Col("root_url", "TEXT"),
    ]
)

FOLDERS_SCHEMA = EntitySchema(
    table="folders",
    columns=[
        Col("id", "INTEGER", primary_key=True, nullable=False),
        Col("source_id", "TEXT"),
        Col("path", "TEXT"),
        Col("name", "TEXT"),
        Col("parent", "INTEGER"),
    ]
)

FILES_SCHEMA = EntitySchema(
    table="files",
    columns=[
        Col("id", "INTEGER", primary_key=True, nullable=False),
        Col("name", "TEXT"),
        Col("folder_id", "INTEGER"),
        Col("sha1", "TEXT"),
    ]
)

INSTANCES_SCHEMA = EntitySchema(
    table="instances",
    columns=[
        Col("id", "INTEGER", primary_key=True, nullable=False),
        Col("file_id", "INTEGER"),
        Col("sha1", "TEXT"),
    ]
)

PROPERTIES_SCHEMA = EntitySchema(
    table="properties",
    columns=[
        Col("id", "INTEGER", primary_key=True, nullable=False),
        Col("dtype", "TEXT"),
        Col("mode", "TEXT"),
        Col("name", "TEXT"),
        Col("access", "TEXT"),
        Col("tag_list_id", "INTEGER"),
    ]
)

TAG_LISTS_SHEMA = EntitySchema(
    table="tag_lists",
    trackable=False,
    columns=[
        Col("id", "INTEGER", primary_key=True, nullable=False),
        Col("name", "TEXT"),
    ]
)

TAGS_SCHEMA = EntitySchema(
    table="tags",
    columns=[
        Col("id", "INTEGER", primary_key=True, nullable=False),
        Col("list_id", "INTEGER"),
        Col("parents", "JSON"),
        Col("value", "TEXT"),
        Col("color", "INTEGER"),
    ]
)

INSTANCE_VALUES_SCHEMA = EntitySchema(
    table="instance_values",
    columns=[
        Col("property_id", "INTEGER", primary_key=True, nullable=False),
        Col("instance_id", "INTEGER", primary_key=True, nullable=False),
        Col("value", "JSON"),
    ]
)

SHA1_VALUES_SCHEMA = EntitySchema(
    table="sha1_values",
    columns=[
        Col("property_id", "INTEGER", primary_key=True, nullable=False),
        Col("sha1", "TEXT", primary_key=True, nullable=False),
        Col("value", "JSON"),
    ]
)

ALL_SCHEMAS = [
    COMMITS_SCHEMA,
    FILE_SOURCES_SCHEMA,
    FOLDERS_SCHEMA,
    FILES_SCHEMA,
    INSTANCES_SCHEMA,
    PROPERTIES_SCHEMA,
    TAG_LISTS_SHEMA,
    TAGS_SCHEMA,
    INSTANCE_VALUES_SCHEMA,
    SHA1_VALUES_SCHEMA,
]

# Build the tables dictionary dynamically
tables_config = {}
for s in ALL_SCHEMAS:
    tables_config[s.table] = s.create_table_sql()
    if s.trackable:
        tables_config[f"{s.table}_reverts"] = s.create_revert_table_sql()

datastore_desc = DbDescription(
    version=1,
    tables=tables_config,
    migrations={}
)