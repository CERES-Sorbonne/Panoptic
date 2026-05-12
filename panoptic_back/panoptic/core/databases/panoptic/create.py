from panoptic.core.databases.entity_schema import EntitySchema
from panoptic.core.databases.db_description import DbDescription
from panoptic.core.databases.key_value_shema import KeyValueSchema
from panoptic.core.databases.panoptic.models import PanopticConfig, User, ProjectKey, PluginKey

PANOPTIC_CONFIG_SCHEMA = KeyValueSchema(PanopticConfig, 'panoptic_config')
USERS_SCHEMA           = EntitySchema(User,            'users')
PROJECTS_SCHEMA        = EntitySchema(ProjectKey,         'projects')
PLUGINS_SCHEMA         = EntitySchema(PluginKey,          'plugins')

ALL_SCHEMAS = [
    PANOPTIC_CONFIG_SCHEMA,
    USERS_SCHEMA,
    PROJECTS_SCHEMA,
    PLUGINS_SCHEMA,
]

tables_config = {}
for s in ALL_SCHEMAS:
    tables_config[s.table] = s.create_table_sql()

panoptic_db_desc = DbDescription(
    version=1,
    tables=tables_config,
    migrations={}
)