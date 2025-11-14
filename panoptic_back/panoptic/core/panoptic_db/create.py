
DB_VERSION = 'db_version'
panoptic_db_version = 1

def create_panoptic_table():
    query = f"""
    CREATE TABLE panoptic (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    INSERT INTO panoptic (key, value)
    VALUES ('{DB_VERSION}', '{panoptic_db_version}');
    """
    return query

def create_projects_table():
    query = f"""
    CREATE TABLE projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        path TEXT NOT NULL,
        description TEXT,
        ignored_plugins JSON
    )
    """
    return query

def create_plugins_table():
    query = f"""
    CREATE TABLE plugins (
        name TEXT PRIMARY KEY,
        path TEXT NOT NULL,
        type TEXT NOT NULL,
        source TEXT
    )
    """
    return query

panoptic_tables = {
    'panoptic': create_panoptic_table(),
    'projects': create_projects_table(),
    'plugins': create_plugins_table(),
}