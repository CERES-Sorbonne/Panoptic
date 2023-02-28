CREATE TABLE datamodel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    type TEXT
);

CREATE TABLE images (
    sha1 TEXT PRIMARY KEY,
    paths JSON
);

CREATE TABLE images_data (
    sha1 TEXT NOT NULL,
    data_id INTEGER NOT NULL,
    value JSON,
    PRIMARY KEY (sha1, data_id),
    FOREIGN KEY (sha1) REFERENCES images (sha1) ON DELETE CASCADE,
    FOREIGN KEY (data_id) REFERENCES data (id) ON DELETE CASCADE
);

INSERT INTO datamodel (name, type) VALUES ("name1", "type1");
INSERT INTO datamodel (name, type) VALUES ("name2", "type1");
INSERT INTO datamodel (name, type) VALUES ("name3", "type2");

INSERT INTO images (sha1, paths) VALUES ("sha1_1", '["path/to/image1.jpg"]');
INSERT INTO images (sha1, paths) VALUES ("sha1_2", '["path/to/image2.jpg"]');
INSERT INTO images (sha1, paths) VALUES ("sha1_3", '["path/to/image3.jpg", "path/to/other/folder/image4.jpg"]');

INSERT INTO images_data (sha1, data_id, value) VALUES ("sha1_1", 1, '{"key1": "value1"}');
INSERT INTO images_data (sha1, data_id, value) VALUES ("sha1_1", 2, '{"key2": "value2"}');
INSERT INTO images_data (sha1, data_id, value) VALUES ("sha1_2", 2, '{"key3": "value3"}');
INSERT INTO images_data (sha1, data_id, value) VALUES ("sha1_3", 3, '{"key4": "value4"}');