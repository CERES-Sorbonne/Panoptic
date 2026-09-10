-- data -- CREATE TABLE SQL copied verbatim from the target's own create.py
-- (~/panoptic @ rework-front, via analysis/target_schema.sql, task 0.1).
-- Regenerate with: python3 -m migrator.schema.regenerate
-- Do not hand-edit: migrator/schema/check.py hashes the upstream sources.

-- [data DB] commits
CREATE TABLE IF NOT EXISTS commits (
    id INTEGER PRIMARY KEY NOT NULL,
    group_id INTEGER,
    source TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    active INTEGER NOT NULL,
    author TEXT
);

-- [data DB] file_sources
CREATE TABLE IF NOT EXISTS file_sources (
    id INTEGER PRIMARY KEY NOT NULL,
    dtype TEXT NOT NULL,
    name TEXT,
    root_url TEXT,
    metadata JSON,
    sync_status JSON,
    sequence  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_file_sources_sequence ON file_sources (sequence);

-- [data DB] folders
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY NOT NULL,
    source_id INTEGER,
    path TEXT,
    name TEXT,
    parent INTEGER,
    sequence  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_folders_sequence ON folders (sequence);

-- [data DB] files
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT,
    folder_id INTEGER,
    sha1 TEXT,
    width INTEGER,
    height INTEGER,
    format TEXT,
    created_at TIMESTAMP,
    sequence  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_files_sequence ON files (sequence);
CREATE INDEX IF NOT EXISTS idx_files_sha1 ON files (sha1);

-- [data DB] instances
CREATE TABLE IF NOT EXISTS instances (
    id INTEGER PRIMARY KEY NOT NULL,
    file_id INTEGER,
    sha1 TEXT,
    sequence  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_instances_sequence ON instances (sequence);
CREATE INDEX IF NOT EXISTS idx_instances_sha1 ON instances (sha1);

-- [data DB] properties
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY NOT NULL,
    dtype TEXT,
    mode TEXT,
    name TEXT,
    access TEXT,
    tag_list_id INTEGER,
    system_key TEXT,
    property_group_id INTEGER,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_properties_sequence ON properties (sequence);
CREATE INDEX IF NOT EXISTS idx_properties_operation ON properties (operation);

-- [data DB] property_groups
CREATE TABLE IF NOT EXISTS property_groups (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_property_groups_sequence ON property_groups (sequence);
CREATE INDEX IF NOT EXISTS idx_property_groups_operation ON property_groups (operation);

-- [data DB] tag_lists
CREATE TABLE IF NOT EXISTS tag_lists (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT
);

-- [data DB] tags
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY NOT NULL,
    list_id INTEGER,
    parents JSON,
    value TEXT,
    color INTEGER,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tags_sequence ON tags (sequence);
CREATE INDEX IF NOT EXISTS idx_tags_operation ON tags (operation);

-- [data DB] instance_values
CREATE TABLE IF NOT EXISTS instance_values (
    property_id INTEGER NOT NULL,
    instance_id INTEGER NOT NULL,
    value JSON,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER,
    PRIMARY KEY (property_id, instance_id)
);
CREATE INDEX IF NOT EXISTS idx_instance_values_sequence ON instance_values (sequence);
CREATE INDEX IF NOT EXISTS idx_instance_values_operation ON instance_values (operation);

-- [data DB] sha1_values
CREATE TABLE IF NOT EXISTS sha1_values (
    property_id INTEGER NOT NULL,
    sha1 TEXT NOT NULL,
    value JSON,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER,
    PRIMARY KEY (property_id, sha1)
);
CREATE INDEX IF NOT EXISTS idx_sha1_values_sequence ON sha1_values (sequence);
CREATE INDEX IF NOT EXISTS idx_sha1_values_operation ON sha1_values (operation);

-- [data DB] file_values
CREATE TABLE IF NOT EXISTS file_values (
    property_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    value JSON,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER,
    PRIMARY KEY (property_id, file_id)
);
CREATE INDEX IF NOT EXISTS idx_file_values_sequence ON file_values (sequence);
CREATE INDEX IF NOT EXISTS idx_file_values_operation ON file_values (operation);

-- [data DB] instance_tag_values
CREATE TABLE IF NOT EXISTS instance_tag_values (
    instance_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER,
    PRIMARY KEY (instance_id, property_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_instance_tag_values_sequence ON instance_tag_values (sequence);
CREATE INDEX IF NOT EXISTS idx_instance_tag_values_operation ON instance_tag_values (operation);
CREATE INDEX IF NOT EXISTS idx_instance_tag_values_tag_id ON instance_tag_values (tag_id);

-- [data DB] sha1_tag_values
CREATE TABLE IF NOT EXISTS sha1_tag_values (
    sha1 TEXT NOT NULL,
    property_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER,
    PRIMARY KEY (sha1, property_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_sha1_tag_values_sequence ON sha1_tag_values (sequence);
CREATE INDEX IF NOT EXISTS idx_sha1_tag_values_operation ON sha1_tag_values (operation);
CREATE INDEX IF NOT EXISTS idx_sha1_tag_values_tag_id ON sha1_tag_values (tag_id);

-- [data DB] entity_log
CREATE TABLE IF NOT EXISTS entity_log (  entity_type TEXT NOT NULL,  entity_key  TEXT NOT NULL,  commit_id   INTEGER NOT NULL,  op          INTEGER NOT NULL,  changes     TEXT,  sequence    INTEGER,  PRIMARY KEY (entity_type, entity_key, commit_id));CREATE INDEX IF NOT EXISTS idx_entity_log_commit ON entity_log (commit_id);CREATE INDEX IF NOT EXISTS idx_entity_log_entity ON entity_log (entity_type, entity_key, commit_id);

-- [data DB] sequence
CREATE TABLE IF NOT EXISTS sequence (id INTEGER);INSERT INTO sequence (id) VALUES (1);
