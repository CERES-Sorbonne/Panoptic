# Current target version for the Registry database
from panoptic.core.databases.db_description import DbDescription

CURRENT_REGISTRY_VERSION = 1

# List of keys to be initialized in the registry table
registry_keys = [
    'commits',
    'file_sources',
    'folders',
    'files',
    'instances',
    'properties',
    'tags',
    'maps',
    'vector_types',
]

def create_registry_table():
    """Returns the SQL for creating the registry table."""
    return """
        CREATE TABLE registry (
            key TEXT PRIMARY KEY NOT NULL,
            next_id INTEGER NOT NULL
        );
    """

# --- Migration Scripts ---

# --- Database Description ---

registry_desc = DbDescription(
    version=CURRENT_REGISTRY_VERSION,
    tables={
        'registry': create_registry_table()
    },
    migrations={
    }
)