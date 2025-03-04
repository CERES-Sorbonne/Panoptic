software_db_version = 6

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
        mode TEXT DEFAULT 'id',
        property_group_id INTEGER
    );
    """
    return query


def create_instances_table():
    query = """
    CREATE TABLE instances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        folder_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        extension TEXT NOT NULL,
        sha1 TEXT NOT NULL,
        url TEXT NOT NULL,
        height INTEGER NOT NULL,
        width INTEGER NOT NULL,
        ahash TEXT NOT NULL,
        
        FOREIGN KEY (folder_id) REFERENCES folders (id) ON DELETE CASCADE
    );
    
    CREATE INDEX idx_image_filepath ON instances (folder_id, name, extension);
    CREATE INDEX idx_image_sha1 ON instances (sha1);
    CREATE INDEX idx_folder_id ON instances(folder_id);
    
    """
    return query


def create_instance_property_values_table():
    query = """
    CREATE TABLE instance_property_values (
        property_id INTEGER NOT NULL,
        instance_id INTEGER NOT NULL,
        value JSON,
        
        PRIMARY KEY (property_id, instance_id),
        FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE,
        FOREIGN KEY (instance_id) REFERENCES instances (id) ON DELETE CASCADE
    );
    
    CREATE INDEX idx_instance_values_instance_id ON instance_property_values(instance_id);
    """
    return query


def create_image_property_values_table():
    query = """
    CREATE TABLE image_property_values (
        property_id INTEGER NOT NULL,
        sha1 TEXT INTEGER NOT NULL,
        value JSON,
        PRIMARY KEY (property_id, sha1),
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
    
    CREATE INDEX idx_vectors_sha1 ON vectors(sha1);
    """
    return query


def create_plugin_defaults_table():
    query = f"""
    CREATE TABLE plugin_defaults (
        name TEXT,
        base JSON,
        functions JSON,
        
        PRIMARY KEY (name)
    );
    """
    return query


def create_actions_table():
    query = """
    CREATE TABLE action_params (
        name TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """
    return query


def create_ui_data():
    query = """
    CREATE TABLE ui_data (
        key TEXT PRIMARY KEY,
        value JSON
    );
    """
    return query


def create_plugin_data():
    query = """
    CREATE TABLE plugin_data (
        key TEXT PRIMARY KEY,
        value JSON
    );
    """
    return query


def create_project_params():
    query = """
    CREATE TABLE project (
        key TEXT PRIMARY KEY,
        value JSON
    );
    """
    return query


# tables2 = {
#     'folders': create_folders_table(),
#     'tabs': create_tabs_table(),
#     'properties': create_properties_table(),
#     'images': create_images_table(),
#     'property_values': create_property_values_table(),
#     'tags': create_tags_table(),
#     'panoptic': create_panoptic_table(),
#     'vectors': create_vectors_table(),
#     'plugin_defaults': create_plugin_defaults_table(),
#     'action_params': create_actions_table()
# }

def create_images_table():
    query = """
    CREATE TABLE images (
        sha1 TEXT PRIMARY KEY,
        small BLOB,
        medium BLOB,
        large BLOB
    );
    """
    return query


def create_property_group_table():
    query = """
    CREATE TABLE property_group (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    );
    """
    return query


def create_id_counter_table():
    query = """
    CREATE TABLE id_counter (
        name TEXT PRIMARY KEY,
        next INTEGER NOT NULL
    );
    INSERT INTO id_counter VALUES ('instance', '1');
    INSERT INTO id_counter VALUES ('property', '1');
    INSERT INTO id_counter VALUES ('tag', '1');
    INSERT INTO id_counter VALUES ('property_group', '1');
    """
    return query


tables = {
    'panoptic': create_panoptic_table(),
    'folders': create_folders_table(),
    'images': create_images_table(),
    'instances': create_instances_table(),
    'properties': create_properties_table(),
    'image_property_values': create_image_property_values_table(),
    'instance_property_values': create_instance_property_values_table(),
    'tags': create_tags_table(),
    'vectors': create_vectors_table(),
    'ui_data': create_ui_data(),
    'plugin_data': create_plugin_data(),
    'project': create_project_params(),
    'property_group': create_property_group_table(),
    'id_counter': create_id_counter_table()
}
