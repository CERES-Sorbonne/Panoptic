from panoptic.core.databases.data.helper import Col, EntitySchema, PropertyValueSchema
from panoptic.core.databases.db_description import DbDescription
from panoptic.models.data import Commit, FileSource, Folder, File, Instance, Property, TagList, Tag, InstanceValue, \
    Sha1Value

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
]

# Build the tables dictionary dynamically
tables_config = {}
for s in ALL_SCHEMAS:
    tables_config[s.table] = s.create_table_sql()
    if s.trackable:
        tables_config[f"{s.table}_log"] = s.create_log_table_sql()

tables_config['sequence'] = sequence_table

datastore_desc = DbDescription(
    version=1,
    tables=tables_config,
    migrations={}
)