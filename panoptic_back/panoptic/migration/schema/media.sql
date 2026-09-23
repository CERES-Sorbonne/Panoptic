-- media -- CREATE TABLE SQL copied verbatim from the target's own create.py
-- (~/panoptic @ rework-front, via analysis/target_schema.sql, task 0.1).
-- Regenerate with: python3 -m migrator.schema.regenerate
-- Do not hand-edit: migrator/schema/check.py hashes the upstream sources.

-- [media DB] vector_types
CREATE TABLE IF NOT EXISTS vector_types (
    id INTEGER PRIMARY KEY NOT NULL,
    source TEXT NOT NULL,
    params JSON NOT NULL
);

-- [media DB] vectors
CREATE TABLE IF NOT EXISTS vectors (
    type_id INTEGER NOT NULL,
    sha1 TEXT NOT NULL,
    data ARRAY NOT NULL,
    PRIMARY KEY (type_id, sha1)
);

-- [media DB] image_types
CREATE TABLE IF NOT EXISTS image_types (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    format TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    auto_gen INTEGER NOT NULL
);

-- [media DB] images
CREATE TABLE IF NOT EXISTS images (
    type_id INTEGER NOT NULL,
    sha1 TEXT NOT NULL,
    data BLOB NOT NULL,
    PRIMARY KEY (type_id, sha1)
);

-- [media DB] image_atlas
CREATE TABLE IF NOT EXISTS image_atlas (
    id INTEGER PRIMARY KEY NOT NULL,
    atlas_nb INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    cell_width INTEGER NOT NULL,
    cell_height INTEGER NOT NULL,
    sha1_mapping JSON NOT NULL
);

-- [media DB] maps
CREATE TABLE IF NOT EXISTS maps (
    id INTEGER PRIMARY KEY NOT NULL,
    source TEXT NOT NULL,
    name TEXT NOT NULL,
    key TEXT NOT NULL,
    count INTEGER NOT NULL,
    data JSON
);
