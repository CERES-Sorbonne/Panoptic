-- project -- CREATE TABLE SQL copied verbatim from the target's own create.py
-- (~/panoptic @ rework-front, via analysis/target_schema.sql, task 0.1).
-- Regenerate with: python3 -m migrator.schema.regenerate
-- Do not hand-edit: migrator/schema/check.py hashes the upstream sources.

-- [project.db] id_registry
CREATE TABLE IF NOT EXISTS id_registry (
    key   TEXT PRIMARY KEY,
    value JSON
);

-- [project.db] project_config
CREATE TABLE IF NOT EXISTS project_config (
    key   TEXT PRIMARY KEY,
    value JSON
);

-- [project.db] project_flags
CREATE TABLE IF NOT EXISTS project_flags (
    key   TEXT PRIMARY KEY,
    value JSON
);

-- [project.db] plugin_data
CREATE TABLE IF NOT EXISTS plugin_data (
    plugin_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    data JSON NOT NULL,
    PRIMARY KEY (plugin_id, key)
);

-- [project.db] tab_data
CREATE TABLE IF NOT EXISTS tab_data (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL,
    state JSON NOT NULL,
    selection JSON
);

-- [project.db] user_defaults
CREATE TABLE IF NOT EXISTS user_defaults (
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    data JSON NOT NULL,
    PRIMARY KEY (user_id, key)
);
