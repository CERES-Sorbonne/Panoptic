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

INSERT INTO datamodel (name, type) VALUES ("categorie", "tag");
INSERT INTO datamodel (name, type) VALUES ("themes", "multi_tags");
INSERT INTO datamodel (name, type) VALUES ("description", "string");

INSERT INTO images (sha1, height, width, name, extension, paths, url)
VALUES ('8157a2d13cee861c7a1bc3a01f4bfb8e300bc994', 1200, 800, '8157a2d13cee861c7a1bc3a01f4bfb8e300bc994', 'jpg', '["D:\\Alie\\Documents\\CollectesTwitter\\remigration\\media\\8157a2d13cee861c7a1bc3a01f4bfb8e300bc994.jpg"]', '/images/D:/Alie/Documents/CollectesTwitter/remigration/media/8157a2d13cee861c7a1bc3a01f4bfb8e300bc994.jpg');

INSERT INTO images (sha1, height, width, name, extension, paths, url)
VALUES ('0b8274fdf497c1b616f39086ac2d19872bfa51f9', 1200, 800, '0b8274fdf497c1b616f39086ac2d19872bfa51f9', 'jpg', '["D:\\Alie\\Documents\\CollectesTwitter\\remigration\\media\\0b8274fdf497c1b616f39086ac2d19872bfa51f9.jpg"]', '/images/D:/Alie/Documents/CollectesTwitter/remigration/media/0b8274fdf497c1b616f39086ac2d19872bfa51f9.jpg');

INSERT INTO images (sha1, height, width, name, extension, paths, url)
VALUES ('1abced957962d9ffeddbe6d21cf1ebbe0fc44669', 1200, 800, '1abced957962d9ffeddbe6d21cf1ebbe0fc44669', 'jpg', '["D:\\Alie\\Documents\\CollectesTwitter\\remigration\\media\\1abced957962d9ffeddbe6d21cf1ebbe0fc44669.jpg"]', '/images/D:/Alie/Documents/CollectesTwitter/remigration/media/1abced957962d9ffeddbe6d21cf1ebbe0fc44669.jpg');

INSERT INTO images_data (sha1, data_id, value)
VALUES ('8157a2d13cee861c7a1bc3a01f4bfb8e300bc994', 1, '"poulet"');

INSERT INTO images_data (sha1, data_id, value)
VALUES ('7b02cf11f4a7a0dcd8201e7a4a8d01dc19b9d4d4', 2, '["toto", "tata"]');

INSERT INTO images_data (sha1, data_id, value)
VALUES ('7b02cf11f4a7a0dcd8201e7a4a8d01dc19b9d4d4', 3, '"Une longue description dune image"');