from panoptic.core.databases.db_description import DbDescription

CURRENT_DATASTORE_VERSION = 1

def create_commits_table():
    return """
        CREATE TABLE commits (
            id INTEGER PRIMARY KEY NOT NULL,
            group_id INTEGER,
            source TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
    """

def create_file_sources_table():
    return """
        CREATE TABLE file_sources (
            id TEXT PRIMARY KEY NOT NULL,
            dtype TEXT,
            name TEXT,
            root_url TEXT,
            commit_id INTEGER
        );
    """

def create_folders_table():
    return """
        CREATE TABLE folders (
            id INTEGER PRIMARY KEY NOT NULL,
            source_id TEXT,
            path TEXT,
            name TEXT,
            parent INTEGER,
            commit_id INTEGER
        );
    """

def create_files_table():
    return """
        CREATE TABLE files (
            id INTEGER PRIMARY KEY NOT NULL,
            name TEXT,
            folder_id TEXT,
            sha1 TEXT,
            commit_id INTEGER
        );
    """

def create_instances_table():
    return """
        CREATE TABLE instances (
            id INTEGER PRIMARY KEY NOT NULL,
            file_id INTEGER,
            sha1 TEXT,
            commit_id INTEGER
        );
    """

def create_properties_table():
    return """
        CREATE TABLE properties (
            id INTEGER PRIMARY KEY NOT NULL,
            dtype TEXT,
            mode TEXT,
            name TEXT,
            commit_id INTEGER
        );
    """

def create_tags_table():
    return """
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY NOT NULL,
            property_id INTEGER,
            parents JSON,
            value TEXT,
            color INTEGER,
            commit_id INTEGER
        );
    """

def create_instance_values_table():
    return """
        CREATE TABLE instance_values (
            property_id INTEGER NOT NULL,
            instance_id INTEGER NOT NULL,
            value BLOB,
            commit_id INTEGER NOT NULL,
            PRIMARY KEY (property_id, instance_id)
        );
    """

def create_sha1_values_table():
    return """
        CREATE TABLE sha1_values (
            property_id INTEGER NOT NULL,
            sha1 TEXT NOT NULL,
            value BLOB,
            commit_id INTEGER NOT NULL,
            PRIMARY KEY (property_id, sha1)
        );
    """

def create_file_sources_history_table():
    return """
        CREATE TABLE file_sources_history (
            id TEXT NOT NULL,
            dtype TEXT,
            name TEXT,
            root_url TEXT,
            commit_id INTEGER NOT NULL,
            operation_type INTEGER,
            PRIMARY KEY (id, commit_id)
        );
        CREATE INDEX idx_file_sources_hist_commit ON file_sources_history (commit_id);
    """

def create_folders_history_table():
    return """
        CREATE TABLE folders_history (
            id INTEGER NOT NULL,
            source_id TEXT,
            path TEXT,
            name TEXT,
            parent INTEGER,
            commit_id INTEGER NOT NULL,
            operation_type INTEGER,
            PRIMARY KEY (id, commit_id)
        );
        CREATE INDEX idx_folders_hist_commit ON folders_history (commit_id);
    """

def create_files_history_table():
    return """
        CREATE TABLE files_history (
            id INTEGER NOT NULL,
            name TEXT,
            folder_id TEXT,
            sha1 TEXT,
            commit_id INTEGER NOT NULL,
            operation_type INTEGER,
            PRIMARY KEY (id, commit_id)
        );
        CREATE INDEX idx_files_hist_commit ON files_history (commit_id);
    """

def create_instances_history_table():
    return """
        CREATE TABLE instances_history (
            id INTEGER NOT NULL,
            file_id INTEGER,
            sha1 TEXT,
            commit_id INTEGER NOT NULL,
            operation_type INTEGER,
            PRIMARY KEY (id, commit_id)
        );
        CREATE INDEX idx_instances_hist_commit ON instances_history (commit_id);
    """

def create_properties_history_table():
    return """
        CREATE TABLE properties_history (
            id INTEGER NOT NULL,
            dtype TEXT,
            mode TEXT,
            name TEXT,
            commit_id INTEGER NOT NULL,
            operation_type INTEGER,
            PRIMARY KEY (id, commit_id)
        );
        CREATE INDEX idx_properties_hist_commit ON properties_history (commit_id);
    """

def create_tags_history_table():
    return """
        CREATE TABLE tags_history (
            id INTEGER NOT NULL,
            property_id INTEGER,
            parents JSON,
            value TEXT,
            color INTEGER,
            commit_id INTEGER NOT NULL,
            operation_type INTEGER,
            PRIMARY KEY (id, commit_id)
        );
        CREATE INDEX idx_tags_hist_commit ON tags_history (commit_id);
    """

def create_instance_values_history_table():
    return """
        CREATE TABLE instance_values_history (
            property_id INTEGER NOT NULL,
            instance_id INTEGER NOT NULL,
            value BLOB,
            commit_id INTEGER NOT NULL,
            operation_type INTEGER,
            PRIMARY KEY (property_id, instance_id, commit_id)
        );
        CREATE INDEX idx_inst_val_hist_commit ON instance_values_history (commit_id);
    """

def create_sha1_values_history_table():
    return """
        CREATE TABLE sha1_values_history (
            property_id INTEGER NOT NULL,
            sha1 TEXT NOT NULL,
            value BLOB,
            commit_id INTEGER NOT NULL,
            operation_type INTEGER,
            PRIMARY KEY (property_id, sha1, commit_id)
        );
        CREATE INDEX idx_sha1_val_hist_commit ON sha1_values_history (commit_id);
    """

datastore_desc = DbDescription(
    version=CURRENT_DATASTORE_VERSION,
    tables={
        'commits': create_commits_table(),
        'file_sources': create_file_sources_table(),
        'file_sources_history': create_file_sources_history_table(),
        'folders': create_folders_table(),
        'folders_history': create_folders_history_table(),
        'files': create_files_table(),
        'files_history': create_files_history_table(),
        'instances': create_instances_table(),
        'instances_history': create_instances_history_table(),
        'properties': create_properties_table(),
        'properties_history': create_properties_history_table(),
        'tags': create_tags_table(),
        'tags_history': create_tags_history_table(),
        'instance_values': create_instance_values_table(),
        'instance_values_history': create_instance_values_history_table(),
        'sha1_values': create_sha1_values_table(),
        'sha1_values_history': create_sha1_values_history_table(),
    },
    migrations={}
)