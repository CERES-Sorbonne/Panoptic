from panoptic.core.databases.entity_schema import EntitySchema
from panoptic.core.databases.db_description import DbDescription
from panoptic.core.databases.key_value_shema import KeyValueSchema
from panoptic.core.databases.panoptic.models import PanopticConfig, User, ProjectKey, PluginKey, LegacyMigration

PANOPTIC_CONFIG_SCHEMA = KeyValueSchema(PanopticConfig, 'panoptic_config')
USERS_SCHEMA           = EntitySchema(User,            'users')
PROJECTS_SCHEMA        = EntitySchema(ProjectKey,         'projects')
PLUGINS_SCHEMA         = EntitySchema(PluginKey,          'plugins')
LEGACY_MIGRATIONS_SCHEMA = EntitySchema(LegacyMigration, 'legacy_migrations')

ALL_SCHEMAS = [
    PANOPTIC_CONFIG_SCHEMA,
    USERS_SCHEMA,
    PROJECTS_SCHEMA,
    PLUGINS_SCHEMA,
    LEGACY_MIGRATIONS_SCHEMA,
]

tables_config = {}
for s in ALL_SCHEMAS:
    tables_config[s.table] = s.create_table_sql()



def _migrate_1_to_2(db):
    """v1 -> v2: add `legacy_migrations` (old-project migration bookkeeping).

    `SQLiteWriter.start()` also creates any table missing from `tables`, so this
    is belt-and-braces; it is written explicitly so the version bump has a real
    migration entry and the upgrade is not an accident of table creation order.
    """
    db.conn.executescript(LEGACY_MIGRATIONS_SCHEMA.create_table_sql())


panoptic_db_desc = DbDescription(
    version=2,
    tables=tables_config,
    migrations={1: _migrate_1_to_2}
)