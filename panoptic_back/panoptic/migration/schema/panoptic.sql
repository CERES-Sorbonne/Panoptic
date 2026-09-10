-- panoptic -- CREATE TABLE SQL copied verbatim from the target's own create.py
-- (~/panoptic @ rework-front, via analysis/target_schema.sql, task 0.1).
-- Regenerate with: python3 -m migrator.schema.regenerate
-- Do not hand-edit: migrator/schema/check.py hashes the upstream sources.

-- [panoptic.db] panoptic_config
CREATE TABLE IF NOT EXISTS panoptic_config (
    key   TEXT PRIMARY KEY,
    value JSON
);

-- [panoptic.db] users
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    password_hash TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_name ON users (name);

-- [panoptic.db] projects
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY NOT NULL,
    path TEXT NOT NULL,
    name TEXT NOT NULL,
    excluded_plugins JSON NOT NULL
);

-- [panoptic.db] plugins
CREATE TABLE IF NOT EXISTS plugins (
    id TEXT PRIMARY KEY NOT NULL,
    install_path TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_path TEXT NOT NULL
);
