CREATE TABLE parameters(
    folders JSON,
    tabs JSON
);

CREATE TABLE properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    type TEXT
);

CREATE TABLE images (
    sha1 TEXT PRIMARY KEY,
    height INTEGER,
    width INTEGER,
    name TEXT,
    extension TEXT,
    paths JSON,
    url TEXT
);

CREATE TABLE images_properties (
    sha1 TEXT NOT NULL,
    property_id INTEGER NOT NULL,
    value JSON,
    PRIMARY KEY (sha1, property_id),
    FOREIGN KEY (sha1) REFERENCES images (sha1) ON DELETE CASCADE,
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

INSERT INTO parameters (folders, tabs)
VALUES ('[]', '[]')