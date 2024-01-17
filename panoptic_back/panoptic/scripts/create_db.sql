CREATE TABLE folders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE,
    name TEXT,
    parent INTEGER,
    FOREIGN KEY (parent) REFERENCES folders (id) ON DELETE CASCADE
);

CREATE TABLE tabs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    data JSON
);

CREATE TABLE properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    type TEXT,
    mode TEXT DEFAULT 'id'
);

CREATE TABLE images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    extension TEXT NOT NULL,

    sha1 TEXT NOT NULL,
    url TEXT NOT NULL,
    height INTEGER NOT NULL,
    width INTEGER NOT NULL
);

CREATE INDEX idx_image_filepath ON images (folder_id, name, extension);
CREATE INDEX idx_image_sha1 ON images (sha1);


CREATE TABLE computed_values (
    sha1 TEXT PRIMARY KEY,
    ahash TEXT,
    vector ARRAY
);

CREATE TABLE property_values (
    property_id INTEGER NOT NULL,
    image_id INTEGER NOT NULL,
    sha1 TEXT INTEGER NOT NULL,
    value JSON,

    -- only image_id or sha1 should be used for a property value.
    -- instead of NULL use -1 for image_id and '' for sha1
    PRIMARY KEY (property_id, image_id, sha1),
    FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE
);


CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    value TEXT NOT NULL,
    parents JSON,
    color TEXT,
    FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE
);

CREATE TABLE panoptic (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);