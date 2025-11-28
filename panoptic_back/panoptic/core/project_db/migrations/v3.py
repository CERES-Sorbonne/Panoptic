v3_sql = """
PRAGMA foreign_keys = OFF;

CREATE TABLE instances_old AS
SELECT * FROM instances;

DROP TABLE instances;

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

INSERT INTO instances (id, folder_id, name, extension, sha1, url, height, width, ahash)
SELECT id, folder_id, name, extension, sha1, url, height, width, ahash
FROM instances_old;

PRAGMA foreign_keys = ON;
"""