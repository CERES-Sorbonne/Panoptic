-- data.db v3 (opti/01 §3), for drawDB import.
-- Plain SQLite: STRICT, WITHOUT ROWID and indexes left out.
-- FOREIGN KEY clauses only give drawDB its links; the real schema has none.
-- value is ANY (native INTEGER | REAL | TEXT) in the real schema; BLOB here for the parser.
-- Tables are ordered so each comes after the ones it references (drawDB drops
-- forward references). One cycle: folders.status_scan_id → scans is left out.

CREATE TABLE commits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  group_id INTEGER,
  source TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  active INTEGER NOT NULL,
  redoable INTEGER NOT NULL,
  undoable INTEGER NOT NULL,
  author TEXT
);

CREATE TABLE tag_lists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  sequence INTEGER NOT NULL
);

CREATE TABLE property_groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  sequence INTEGER NOT NULL
);

CREATE TABLE properties (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dtype TEXT,
  mode TEXT,
  name TEXT,
  access TEXT,
  tag_list_id INTEGER,
  system_key TEXT,
  property_group_id INTEGER,
  namespace_id INTEGER,
  sequence INTEGER NOT NULL,
  FOREIGN KEY (tag_list_id) REFERENCES tag_lists(id),
  FOREIGN KEY (property_group_id) REFERENCES property_groups(id),
  FOREIGN KEY (namespace_id) REFERENCES properties(id)
);

CREATE TABLE tags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  list_id INTEGER,
  parents TEXT,
  value TEXT,
  color INTEGER,
  sequence INTEGER NOT NULL,
  FOREIGN KEY (list_id) REFERENCES tag_lists(id)
);

CREATE TABLE images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  hash BLOB NOT NULL UNIQUE,
  size INTEGER NOT NULL,
  sequence INTEGER NOT NULL
);

CREATE TABLE subimages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  image_id INTEGER NOT NULL,
  namespace_id INTEGER NOT NULL,
  x0 REAL NOT NULL,
  y0 REAL NOT NULL,
  x1 REAL NOT NULL,
  y1 REAL NOT NULL,
  sequence INTEGER NOT NULL,
  FOREIGN KEY (image_id) REFERENCES images(id),
  FOREIGN KEY (namespace_id) REFERENCES properties(id)
);

CREATE TABLE file_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dtype TEXT NOT NULL,
  name TEXT,
  root_url TEXT NOT NULL,
  excludes TEXT,
  metadata TEXT,
  sequence INTEGER NOT NULL
);

CREATE TABLE folders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  parent INTEGER,
  name TEXT NOT NULL,
  status INTEGER NOT NULL,
  status_scan_id INTEGER,
  sequence INTEGER NOT NULL,
  FOREIGN KEY (source_id) REFERENCES file_sources(id),
  FOREIGN KEY (parent) REFERENCES folders(id)
);

CREATE TABLE scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  folder_id INTEGER,
  mode INTEGER NOT NULL,
  started_at INTEGER NOT NULL,
  finished_at INTEGER,
  new_count INTEGER,
  missing_count INTEGER,
  changed_count INTEGER,
  back_count INTEGER,
  sequence INTEGER NOT NULL,
  FOREIGN KEY (source_id) REFERENCES file_sources(id),
  FOREIGN KEY (folder_id) REFERENCES folders(id)
);

CREATE TABLE files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  folder_id INTEGER NOT NULL,
  image_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  size INTEGER NOT NULL,
  mtime INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  status INTEGER NOT NULL,
  status_scan_id INTEGER,
  added_scan_id INTEGER,
  sequence INTEGER NOT NULL,
  FOREIGN KEY (folder_id) REFERENCES folders(id),
  FOREIGN KEY (image_id) REFERENCES images(id),
  FOREIGN KEY (status_scan_id) REFERENCES scans(id),
  FOREIGN KEY (added_scan_id) REFERENCES scans(id)
);

CREATE TABLE instances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL UNIQUE,
  image_id INTEGER,
  file_id INTEGER,
  sequence INTEGER NOT NULL,
  FOREIGN KEY (image_id) REFERENCES images(id),
  FOREIGN KEY (file_id) REFERENCES files(id)
);

CREATE TABLE pending_changes (
  id INTEGER PRIMARY KEY,
  scan_id INTEGER NOT NULL,
  file_id INTEGER NOT NULL,
  old_image_id INTEGER NOT NULL,
  decision INTEGER,
  sequence INTEGER NOT NULL,
  FOREIGN KEY (scan_id) REFERENCES scans(id),
  FOREIGN KEY (file_id) REFERENCES files(id),
  FOREIGN KEY (old_image_id) REFERENCES images(id)
);

CREATE TABLE entity_log (
  table_id INTEGER NOT NULL,
  k1 INTEGER NOT NULL,
  k2 INTEGER NOT NULL DEFAULT 0,
  k3 INTEGER NOT NULL DEFAULT 0,
  commit_id INTEGER NOT NULL,
  op INTEGER NOT NULL,
  value ANY,
  changes TEXT,
  PRIMARY KEY (table_id, k1, k2, k3, commit_id),
  FOREIGN KEY (commit_id) REFERENCES commits(id)
);

CREATE TABLE image_values (
  property_id INTEGER NOT NULL,
  image_id INTEGER NOT NULL,
  value BLOB NOT NULL,
  sequence INTEGER NOT NULL,
  PRIMARY KEY (property_id, image_id),
  FOREIGN KEY (property_id) REFERENCES properties(id),
  FOREIGN KEY (image_id) REFERENCES images(id)
);

CREATE TABLE instance_values (
  property_id INTEGER NOT NULL,
  instance_id INTEGER NOT NULL,
  value BLOB NOT NULL,
  sequence INTEGER NOT NULL,
  PRIMARY KEY (property_id, instance_id),
  FOREIGN KEY (property_id) REFERENCES properties(id),
  FOREIGN KEY (instance_id) REFERENCES instances(id)
);

CREATE TABLE image_tag_values (
  property_id INTEGER NOT NULL,
  image_id INTEGER NOT NULL,
  tag_id INTEGER NOT NULL,
  sequence INTEGER NOT NULL,
  PRIMARY KEY (property_id, image_id, tag_id),
  FOREIGN KEY (property_id) REFERENCES properties(id),
  FOREIGN KEY (image_id) REFERENCES images(id),
  FOREIGN KEY (tag_id) REFERENCES tags(id)
);

CREATE TABLE instance_tag_values (
  property_id INTEGER NOT NULL,
  instance_id INTEGER NOT NULL,
  tag_id INTEGER NOT NULL,
  sequence INTEGER NOT NULL,
  PRIMARY KEY (property_id, instance_id, tag_id),
  FOREIGN KEY (property_id) REFERENCES properties(id),
  FOREIGN KEY (instance_id) REFERENCES instances(id),
  FOREIGN KEY (tag_id) REFERENCES tags(id)
);

CREATE TABLE subimage_values (
  property_id INTEGER NOT NULL,
  subimage_id INTEGER NOT NULL,
  value BLOB NOT NULL,
  sequence INTEGER NOT NULL,
  PRIMARY KEY (property_id, subimage_id),
  FOREIGN KEY (property_id) REFERENCES properties(id),
  FOREIGN KEY (subimage_id) REFERENCES subimages(id)
);

CREATE TABLE subimage_tag_values (
  property_id INTEGER NOT NULL,
  subimage_id INTEGER NOT NULL,
  tag_id INTEGER NOT NULL,
  sequence INTEGER NOT NULL,
  PRIMARY KEY (property_id, subimage_id, tag_id),
  FOREIGN KEY (property_id) REFERENCES properties(id),
  FOREIGN KEY (subimage_id) REFERENCES subimages(id),
  FOREIGN KEY (tag_id) REFERENCES tags(id)
);

CREATE TABLE sequence (
  rowid INTEGER PRIMARY KEY,  -- implicit SQLite rowid, shown for drawDB
  id INTEGER NOT NULL
);

CREATE TABLE tombstones (
  rowid INTEGER PRIMARY KEY,  -- implicit SQLite rowid, shown for drawDB
  table_id INTEGER NOT NULL,
  k1 INTEGER NOT NULL,
  k2 INTEGER NOT NULL DEFAULT 0,
  k3 INTEGER NOT NULL DEFAULT 0,
  sequence INTEGER NOT NULL
);
