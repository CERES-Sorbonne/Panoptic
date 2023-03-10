CREATE TABLE datamodel (
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

CREATE TABLE images_data (
    sha1 TEXT NOT NULL,
    data_id INTEGER NOT NULL,
    value JSON,
    PRIMARY KEY (sha1, data_id),
    FOREIGN KEY (sha1) REFERENCES images (sha1) ON DELETE CASCADE,
    FOREIGN KEY (data_id) REFERENCES datamodel (id) ON DELETE CASCADE
);

CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    value TEXT NOT NULL,
    parents JSON
);