from panoptic.core.databases.data.helper import EntitySchema
from panoptic.core.databases.db_description import DbDescription
from panoptic.core.databases.key_value_shema import KeyValueSchema
from panoptic.core.databases.project.models import IdRegistry, ProjectConfig, PluginData, TabData, UserDefaults

ID_REGISTRY_SHEMA = KeyValueSchema(IdRegistry, 'id_registry')
PROJECT_CONFIG_SHEMA = KeyValueSchema(ProjectConfig, 'project_config')
PLUGIN_DATA_SCHEMA = EntitySchema(PluginData, 'plugin_data')
TAB_DATA_SCHEMA = EntitySchema(TabData, 'tab_data')
USER_DEFAULTS_SCHEMA = EntitySchema(UserDefaults, 'user_defaults')

ALL_SCHEMAS = [
    ID_REGISTRY_SHEMA,
    PROJECT_CONFIG_SHEMA,
    PLUGIN_DATA_SCHEMA,
    TAB_DATA_SCHEMA,
    USER_DEFAULTS_SCHEMA,
]

# Build the tables dictionary dynamically
tables_config = {}
for s in ALL_SCHEMAS:
    tables_config[s.table] = s.create_table_sql()
    if s.trackable:
        tables_config[f"{s.table}_log"] = s.create_log_table_sql()

project_db_desc = DbDescription(
    version=1,
    tables=tables_config,
    migrations={}
)