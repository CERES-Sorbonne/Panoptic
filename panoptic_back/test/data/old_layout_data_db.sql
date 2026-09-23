PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE _version (
                key TEXT PRIMARY KEY NOT NULL,
                value INTEGER NOT NULL
            );
INSERT INTO _version VALUES('db_version',9);
CREATE TABLE file_values (
    property_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    value JSON,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER,
    PRIMARY KEY (property_id, file_id)
);
INSERT INTO file_values VALUES(15,1,'"fv"',NULL,0,2);
CREATE TABLE file_values_log (
    property_id INTEGER,
    file_id INTEGER,
    value JSON,
    commit_id  INTEGER NOT NULL,
    operation  INTEGER NOT NULL,
    PRIMARY KEY (property_id, file_id, commit_id)
);
INSERT INTO file_values_log VALUES(15,1,'"fv"',1,0);
CREATE TABLE instance_tag_values (
    instance_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER,
    PRIMARY KEY (instance_id, property_id, tag_id)
);
INSERT INTO instance_tag_values VALUES(1,12,100,1,1,2);
INSERT INTO instance_tag_values VALUES(1,12,101,1,1,2);
INSERT INTO instance_tag_values VALUES(2,12,101,1,1,2);
INSERT INTO instance_tag_values VALUES(2,12,103,2,-1,3);
CREATE TABLE instance_tag_values_log (
    instance_id INTEGER,
    property_id INTEGER,
    tag_id INTEGER,
    commit_id  INTEGER NOT NULL,
    operation  INTEGER NOT NULL,
    PRIMARY KEY (instance_id, property_id, tag_id, commit_id)
);
INSERT INTO instance_tag_values_log VALUES(1,12,100,1,1);
INSERT INTO instance_tag_values_log VALUES(1,12,101,1,1);
INSERT INTO instance_tag_values_log VALUES(2,12,101,1,1);
INSERT INTO instance_tag_values_log VALUES(2,12,103,1,1);
INSERT INTO instance_tag_values_log VALUES(2,12,103,2,-1);
CREATE TABLE sha1_tag_values (
    sha1 TEXT NOT NULL,
    property_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER,
    PRIMARY KEY (sha1, property_id, tag_id)
);
INSERT INTO sha1_tag_values VALUES('A',13,102,1,1,2);
CREATE TABLE sha1_tag_values_log (
    sha1 TEXT,
    property_id INTEGER,
    tag_id INTEGER,
    commit_id  INTEGER NOT NULL,
    operation  INTEGER NOT NULL,
    PRIMARY KEY (sha1, property_id, tag_id, commit_id)
);
INSERT INTO sha1_tag_values_log VALUES('A',13,102,1,1);
CREATE TABLE property_groups (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER
);
INSERT INTO property_groups VALUES(1,'grp',1,1,2);
CREATE TABLE property_groups_log (
    id INTEGER,
    name TEXT,
    commit_id  INTEGER NOT NULL,
    operation  INTEGER NOT NULL,
    PRIMARY KEY (id, commit_id)
);
INSERT INTO property_groups_log VALUES(1,'grp',1,1);
CREATE TABLE commits (
    id INTEGER PRIMARY KEY NOT NULL,
    group_id INTEGER,
    source TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    active INTEGER NOT NULL
);
INSERT INTO commits VALUES(1,1,'t','2026-09-21 20:28:07.238834',1);
INSERT INTO commits VALUES(2,2,'t','2026-09-21 20:28:07.239469',1);
INSERT INTO commits VALUES(3,3,'t','2026-09-21 20:28:07.239886',0);
CREATE TABLE file_sources (
    id INTEGER PRIMARY KEY NOT NULL,
    dtype TEXT NOT NULL,
    name TEXT,
    root_url TEXT,
    metadata JSON,
    sync_status JSON,
    sequence  INTEGER
);
INSERT INTO file_sources VALUES(1,'local','local_filesystem',NULL,'{"a": 1}','{"status": "ok"}',1);
CREATE TABLE folders (
    id INTEGER PRIMARY KEY NOT NULL,
    source_id INTEGER,
    path TEXT,
    name TEXT,
    parent INTEGER,
    sequence  INTEGER
);
INSERT INTO folders VALUES(1,1,'/imgs','imgs',NULL,1);
CREATE TABLE files (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT,
    folder_id INTEGER,
    sha1 TEXT,
    width INTEGER,
    height INTEGER,
    format TEXT,
    created_at TIMESTAMP,
    sequence  INTEGER
);
INSERT INTO files VALUES(1,'a.jpg',1,'A',10,20,'jpg',NULL,1);
INSERT INTO files VALUES(2,'b.jpg',1,'B',NULL,NULL,NULL,NULL,1);
CREATE TABLE instances (
    id INTEGER PRIMARY KEY NOT NULL,
    file_id INTEGER,
    sha1 TEXT,
    sequence  INTEGER
);
INSERT INTO instances VALUES(1,1,'A',1);
INSERT INTO instances VALUES(2,2,'B',1);
CREATE TABLE properties (
    id INTEGER PRIMARY KEY NOT NULL,
    dtype TEXT,
    mode TEXT,
    name TEXT,
    access TEXT,
    tag_list_id INTEGER,
    system_key TEXT,
    property_group_id INTEGER,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER
);
INSERT INTO properties VALUES(10,'text','id','note','write',10,NULL,1,1,1,2);
INSERT INTO properties VALUES(11,'number','id','score','write',11,NULL,NULL,1,1,2);
INSERT INTO properties VALUES(12,'multi_tags','id','kw','write',12,NULL,NULL,1,1,2);
INSERT INTO properties VALUES(13,'tag','sha1','cat','write',13,NULL,NULL,1,1,2);
INSERT INTO properties VALUES(14,'text','id','gone','write',14,NULL,NULL,2,-1,3);
INSERT INTO properties VALUES(15,'text','file','fnote','write',15,NULL,NULL,1,1,2);
CREATE TABLE properties_log (
    id INTEGER,
    dtype TEXT,
    mode TEXT,
    name TEXT,
    access TEXT,
    tag_list_id INTEGER,
    system_key TEXT,
    property_group_id INTEGER,
    commit_id  INTEGER NOT NULL,
    operation  INTEGER NOT NULL,
    PRIMARY KEY (id, commit_id)
);
INSERT INTO properties_log VALUES(10,'text','id','note','write',10,NULL,1,1,1);
INSERT INTO properties_log VALUES(11,'number','id','score','write',11,NULL,NULL,1,1);
INSERT INTO properties_log VALUES(12,'multi_tags','id','kw','write',12,NULL,NULL,1,1);
INSERT INTO properties_log VALUES(13,'tag','sha1','cat','write',13,NULL,NULL,1,1);
INSERT INTO properties_log VALUES(14,'text','id','gone','write',14,NULL,NULL,1,1);
INSERT INTO properties_log VALUES(15,'text','file','fnote','write',15,NULL,NULL,1,1);
INSERT INTO properties_log VALUES(14,'text','id','gone','write',14,NULL,NULL,2,-1);
CREATE TABLE tag_lists (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT
);
CREATE TABLE tags (
    id INTEGER PRIMARY KEY NOT NULL,
    list_id INTEGER,
    parents JSON,
    value TEXT,
    color INTEGER,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER
);
INSERT INTO tags VALUES(100,12,'[]','sky',1,1,1,2);
INSERT INTO tags VALUES(101,12,'[100]','blue',2,1,1,2);
INSERT INTO tags VALUES(102,13,'[]','cat',3,1,1,2);
INSERT INTO tags VALUES(103,12,'[]','deadtag',3,2,-1,3);
CREATE TABLE tags_log (
    id INTEGER,
    list_id INTEGER,
    parents JSON,
    value TEXT,
    color INTEGER,
    commit_id  INTEGER NOT NULL,
    operation  INTEGER NOT NULL,
    PRIMARY KEY (id, commit_id)
);
INSERT INTO tags_log VALUES(100,12,'[]','sky',1,1,1);
INSERT INTO tags_log VALUES(101,12,'[100]','blue',2,1,1);
INSERT INTO tags_log VALUES(102,13,'[]','cat',3,1,1);
INSERT INTO tags_log VALUES(103,12,'[]','deadtag',3,1,1);
INSERT INTO tags_log VALUES(103,12,'[]','deadtag',3,2,-1);
CREATE TABLE instance_values (
    property_id INTEGER NOT NULL,
    instance_id INTEGER NOT NULL,
    value JSON,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER,
    PRIMARY KEY (property_id, instance_id)
);
INSERT INTO instance_values VALUES(11,1,3.5,NULL,0,2);
INSERT INTO instance_values VALUES(11,2,7,NULL,0,2);
INSERT INTO instance_values VALUES(14,1,'"x"',2,-1,3);
INSERT INTO instance_values VALUES(10,1,'"hello"',1,0,5);
CREATE TABLE instance_values_log (
    property_id INTEGER,
    instance_id INTEGER,
    value JSON,
    commit_id  INTEGER NOT NULL,
    operation  INTEGER NOT NULL,
    PRIMARY KEY (property_id, instance_id, commit_id)
);
INSERT INTO instance_values_log VALUES(10,1,'"hello"',1,0);
INSERT INTO instance_values_log VALUES(11,1,3.5,1,0);
INSERT INTO instance_values_log VALUES(11,2,7,1,0);
INSERT INTO instance_values_log VALUES(14,1,'"x"',1,0);
INSERT INTO instance_values_log VALUES(14,1,'"x"',2,-1);
INSERT INTO instance_values_log VALUES(10,1,'"undone"',3,0);
CREATE TABLE sha1_values (
    property_id INTEGER NOT NULL,
    sha1 TEXT NOT NULL,
    value JSON,
    commit_id INTEGER,
    operation INTEGER,
    sequence  INTEGER,
    PRIMARY KEY (property_id, sha1)
);
CREATE TABLE sha1_values_log (
    property_id INTEGER,
    sha1 TEXT,
    value JSON,
    commit_id  INTEGER NOT NULL,
    operation  INTEGER NOT NULL,
    PRIMARY KEY (property_id, sha1, commit_id)
);
CREATE TABLE sequence (id INTEGER);
INSERT INTO sequence VALUES(6);
CREATE INDEX idx_file_values_sequence ON file_values (sequence);
CREATE INDEX idx_file_values_operation ON file_values (operation);
CREATE INDEX idx_file_values_log_commit ON file_values_log (commit_id);
CREATE INDEX idx_file_values_log_entity ON file_values_log (property_id, file_id, commit_id);
CREATE INDEX idx_instance_tag_values_sequence ON instance_tag_values (sequence);
CREATE INDEX idx_instance_tag_values_operation ON instance_tag_values (operation);
CREATE INDEX idx_instance_tag_values_tag_id ON instance_tag_values (tag_id);
CREATE INDEX idx_instance_tag_values_log_commit ON instance_tag_values_log (commit_id);
CREATE INDEX idx_instance_tag_values_log_entity ON instance_tag_values_log (instance_id, property_id, tag_id, commit_id);
CREATE INDEX idx_sha1_tag_values_sequence ON sha1_tag_values (sequence);
CREATE INDEX idx_sha1_tag_values_operation ON sha1_tag_values (operation);
CREATE INDEX idx_sha1_tag_values_tag_id ON sha1_tag_values (tag_id);
CREATE INDEX idx_sha1_tag_values_log_commit ON sha1_tag_values_log (commit_id);
CREATE INDEX idx_sha1_tag_values_log_entity ON sha1_tag_values_log (sha1, property_id, tag_id, commit_id);
CREATE INDEX idx_property_groups_sequence ON property_groups (sequence);
CREATE INDEX idx_property_groups_operation ON property_groups (operation);
CREATE INDEX idx_property_groups_log_commit ON property_groups_log (commit_id);
CREATE INDEX idx_property_groups_log_entity ON property_groups_log (id, commit_id);
CREATE INDEX idx_file_sources_sequence ON file_sources (sequence);
CREATE INDEX idx_folders_sequence ON folders (sequence);
CREATE INDEX idx_files_sequence ON files (sequence);
CREATE INDEX idx_files_sha1 ON files (sha1);
CREATE INDEX idx_instances_sequence ON instances (sequence);
CREATE INDEX idx_instances_sha1 ON instances (sha1);
CREATE INDEX idx_properties_sequence ON properties (sequence);
CREATE INDEX idx_properties_operation ON properties (operation);
CREATE INDEX idx_properties_log_commit ON properties_log (commit_id);
CREATE INDEX idx_properties_log_entity ON properties_log (id, commit_id);
CREATE INDEX idx_tags_sequence ON tags (sequence);
CREATE INDEX idx_tags_operation ON tags (operation);
CREATE INDEX idx_tags_log_commit ON tags_log (commit_id);
CREATE INDEX idx_tags_log_entity ON tags_log (id, commit_id);
CREATE INDEX idx_instance_values_sequence ON instance_values (sequence);
CREATE INDEX idx_instance_values_operation ON instance_values (operation);
CREATE INDEX idx_instance_values_log_commit ON instance_values_log (commit_id);
CREATE INDEX idx_instance_values_log_entity ON instance_values_log (property_id, instance_id, commit_id);
CREATE INDEX idx_sha1_values_sequence ON sha1_values (sequence);
CREATE INDEX idx_sha1_values_operation ON sha1_values (operation);
CREATE INDEX idx_sha1_values_log_commit ON sha1_values_log (commit_id);
CREATE INDEX idx_sha1_values_log_entity ON sha1_values_log (property_id, sha1, commit_id);
COMMIT;
