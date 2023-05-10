INSERT INTO properties (name, type) VALUES ("categorie", "tag");
INSERT INTO properties (name, type) VALUES ("themes", "multi_tags");
INSERT INTO properties (name, type) VALUES ("description", "string");
INSERT INTO properties (name, type) VALUES ("creation_date", "date");

INSERT INTO images (sha1, height, width, name, extension, paths, url)
VALUES ('8157a2d13cee861c7a1bc3a01f4bfb8e300bc994', 1200, 800, '8157a2d13cee861c7a1bc3a01f4bfb8e300bc994', 'jpg', '["C:\\Users\\Orion\\Pictures\\ImagesPanoptic\\8157a2d13cee861c7a1bc3a01f4bfb8e300bc994.jpg"]', '/images/C:/Users/Orion/Pictures/ImagesPanoptic/8157a2d13cee861c7a1bc3a01f4bfb8e300bc994.jpg');
INSERT INTO images (sha1, height, width, name, extension, paths, url)
VALUES ('0b8274fdf497c1b616f39086ac2d19872bfa51f9', 1200, 800, '0b8274fdf497c1b616f39086ac2d19872bfa51f9', 'jpg', '["C:\\Users\\Orion\\Pictures\\ImagesPanoptic\\0b8274fdf497c1b616f39086ac2d19872bfa51f9.jpg"]', '/images/C:/Users/Orion/Pictures/ImagesPanoptic/0b8274fdf497c1b616f39086ac2d19872bfa51f9.jpg');
INSERT INTO images (sha1, height, width, name, extension, paths, url)
VALUES ('1abced957962d9ffeddbe6d21cf1ebbe0fc44669', 1200, 800, '1abced957962d9ffeddbe6d21cf1ebbe0fc44669', 'jpg', '["C:\\Users\\Orion\\Pictures\\ImagesPanoptic\\1abced957962d9ffeddbe6d21cf1ebbe0fc44669.jpg"]', '/images/C:/Users/Orion/Pictures/ImagesPanoptic/1abced957962d9ffeddbe6d21cf1ebbe0fc44669.jpg');

INSERT INTO tags (property_id, value, parents) VALUES (1, 'GJ', '[0]');
INSERT INTO tags (property_id, value, parents) VALUES (1, 'Personnalités', '[1]');
INSERT INTO tags (property_id, value, parents) VALUES (1, 'Violences', '[0]');
INSERT INTO tags (property_id, value, parents) VALUES (1, 'Blessés', '[3]');
INSERT INTO tags (property_id, value, parents) VALUES (1, 'Jerome Rodrigues', '[2, 4]');
INSERT INTO tags (property_id, value, parents) VALUES (2, 'poulet', '[0]');
INSERT INTO tags (property_id, value, parents) VALUES (2, 'jambon', '[0]');

INSERT INTO images_properties (sha1, property_id, value)
VALUES ('8157a2d13cee861c7a1bc3a01f4bfb8e300bc994', 1, '1');
INSERT INTO images_properties (sha1, property_id, value)
VALUES ('8157a2d13cee861c7a1bc3a01f4bfb8e300bc994', 4,  '20/03/2022');
INSERT INTO images_properties (sha1, property_id, value)
VALUES ('0b8274fdf497c1b616f39086ac2d19872bfa51f9', 2, '[1, 2]');
INSERT INTO images_properties (sha1, property_id, value)
VALUES ('1abced957962d9ffeddbe6d21cf1ebbe0fc44669', 1, '6');
INSERT INTO images_properties (sha1, property_id, value)
VALUES ('0b8274fdf497c1b616f39086ac2d19872bfa51f9', 3, 'Une longue description dune image');

