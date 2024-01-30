software_db_version = 1

DB_VERSION = 'db_version'


def create_folders_table():
    query = """
    CREATE TABLE folders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE,
        name TEXT,
        parent INTEGER,
        FOREIGN KEY (parent) REFERENCES folders (id) ON DELETE CASCADE
    );
    """
    return query


def create_tabs_table():
    query = """
    CREATE TABLE tabs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        data JSON
    );
    """
    return query


def create_properties_table():
    query = """
    CREATE TABLE properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        type TEXT,
        mode TEXT DEFAULT 'id'
    );
    """
    return query


def create_images_table():
    query = """
    CREATE TABLE images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        folder_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        extension TEXT NOT NULL,
        sha1 TEXT NOT NULL,
        url TEXT NOT NULL,
        height INTEGER NOT NULL,
        width INTEGER NOT NULL,
        ahash TEXT NOT NULL
    );
    CREATE INDEX idx_image_filepath ON images (folder_id, name, extension);
    CREATE INDEX idx_image_sha1 ON images (sha1);
    """
    return query


def create_computed_values_table():
    query = """
    CREATE TABLE computed_values (
        sha1 TEXT PRIMARY KEY,
        ahash TEXT,
        vector ARRAY
    );
    """
    return query


def create_property_values_table():
    query = """
    CREATE TABLE property_values (
        property_id INTEGER NOT NULL,
        image_id INTEGER NOT NULL,
        sha1 TEXT INTEGER NOT NULL,
        value JSON,
        PRIMARY KEY (property_id, image_id, sha1),
        FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE
    );
    """
    return query


def create_tags_table():
    query = """
    CREATE TABLE tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER NOT NULL,
        value TEXT NOT NULL,
        parents JSON,
        color TEXT,
        FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE
    );
    """
    return query


def create_panoptic_table():
    query = f"""
    CREATE TABLE panoptic (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    INSERT INTO panoptic (key, value)
    VALUES ('{DB_VERSION}', '{software_db_version}');
    """
    return query


def create_vectors_table():
    query = f"""
    CREATE TABLE vectors (
        source TEXT,
        type TEXT,
        sha1 TEXT,
        data ARRAY,
        
        PRIMARY KEY (source, type, sha1)
    );
    """
    return query


tables = {
    'folders': create_folders_table(),
    'tabs': create_tabs_table(),
    'properties': create_properties_table(),
    'images': create_images_table(),
    'computed_values': create_computed_values_table(),
    'property_values': create_property_values_table(),
    'tags': create_tags_table(),
    'panoptic': create_panoptic_table(),
    'vectors': create_vectors_table()
}
