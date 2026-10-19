//! Models + table descriptions of `data.db` (port of `data/models.py` + `data/create.py`).
//!
//! Field names and order are exactly the Python msgspec structs'. The structs serialize with
//! serde as JSON *objects*; [`crate::as_array`] gives the positional `array_like` form some
//! Python routes emit (see `DB_FORMAT.md` § API serialization).

use indexmap::IndexMap;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::impl_entity;
use crate::pytime::PyDateTime;
use crate::schema::{ColDef, TableDef};

// ---------------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------------

const fn c(name: &'static str, ty: &'static str) -> ColDef {
    ColDef::new(name, ty)
}

pub static COMMITS: TableDef = TableDef {
    name: "commits",
    cols: &[
        c("id", "INTEGER").pk(),
        c("group_id", "INTEGER"),
        c("source", "TEXT").not_null(),
        c("timestamp", "TIMESTAMP").not_null(),
        c("active", "INTEGER").not_null(),
        c("author", "TEXT"),
        c("redoable", "INTEGER"),
    ],
    logged: false,
    sequenced: false,
};

pub static FILE_SOURCES: TableDef = TableDef {
    name: "file_sources",
    cols: &[
        c("id", "INTEGER").pk(),
        c("dtype", "TEXT").not_null(),
        c("name", "TEXT"),
        c("root_url", "TEXT"),
        c("metadata", "JSON"),
        c("sync_status", "JSON"),
    ],
    logged: false,
    sequenced: true,
};

pub static FOLDERS: TableDef = TableDef {
    name: "folders",
    cols: &[
        c("id", "INTEGER").pk(),
        c("source_id", "INTEGER"),
        c("path", "TEXT"),
        c("name", "TEXT"),
        c("parent", "INTEGER"),
    ],
    logged: false,
    sequenced: true,
};

pub static FILES: TableDef = TableDef {
    name: "files",
    cols: &[
        c("id", "INTEGER").pk(),
        c("name", "TEXT"),
        c("folder_id", "INTEGER"),
        c("sha1", "TEXT").indexed(),
        c("width", "INTEGER"),
        c("height", "INTEGER"),
        c("format", "TEXT"),
        c("created_at", "TIMESTAMP"),
    ],
    logged: false,
    sequenced: true,
};

pub static INSTANCES: TableDef = TableDef {
    name: "instances",
    cols: &[c("id", "INTEGER").pk(), c("file_id", "INTEGER"), c("sha1", "TEXT").indexed()],
    logged: false,
    sequenced: true,
};

pub static PROPERTIES: TableDef = TableDef {
    name: "properties",
    cols: &[
        c("id", "INTEGER").pk(),
        c("dtype", "TEXT"),
        c("mode", "TEXT"),
        c("name", "TEXT"),
        c("access", "TEXT"),
        c("tag_list_id", "INTEGER"),
        c("system_key", "TEXT"),
        c("property_group_id", "INTEGER"),
    ],
    logged: true,
    sequenced: true,
};

pub static PROPERTY_GROUPS: TableDef = TableDef {
    name: "property_groups",
    cols: &[c("id", "INTEGER").pk(), c("name", "TEXT")],
    logged: true,
    sequenced: true,
};

pub static TAG_LISTS: TableDef = TableDef {
    name: "tag_lists",
    cols: &[c("id", "INTEGER").pk(), c("name", "TEXT")],
    logged: false,
    sequenced: false,
};

pub static TAGS: TableDef = TableDef {
    name: "tags",
    cols: &[
        c("id", "INTEGER").pk(),
        c("list_id", "INTEGER"),
        c("parents", "JSON"),
        c("value", "TEXT"),
        c("color", "INTEGER"),
    ],
    logged: true,
    sequenced: true,
};

pub static INSTANCE_VALUES: TableDef = TableDef {
    name: "instance_values",
    cols: &[c("property_id", "INTEGER").pk(), c("instance_id", "INTEGER").pk(), c("value", "JSON")],
    logged: true,
    sequenced: true,
};

pub static SHA1_VALUES: TableDef = TableDef {
    name: "sha1_values",
    cols: &[c("property_id", "INTEGER").pk(), c("sha1", "TEXT").pk(), c("value", "JSON")],
    logged: true,
    sequenced: true,
};

pub static FILE_VALUES: TableDef = TableDef {
    name: "file_values",
    cols: &[c("property_id", "INTEGER").pk(), c("file_id", "INTEGER").pk(), c("value", "JSON")],
    logged: true,
    sequenced: true,
};

pub static INSTANCE_TAG_VALUES: TableDef = TableDef {
    name: "instance_tag_values",
    cols: &[
        c("instance_id", "INTEGER").pk(),
        c("property_id", "INTEGER").pk(),
        c("tag_id", "INTEGER").pk().indexed(),
    ],
    logged: true,
    sequenced: true,
};

pub static SHA1_TAG_VALUES: TableDef = TableDef {
    name: "sha1_tag_values",
    cols: &[
        c("sha1", "TEXT").pk(),
        c("property_id", "INTEGER").pk(),
        c("tag_id", "INTEGER").pk().indexed(),
    ],
    logged: true,
    sequenced: true,
};

/// Every result/structural table, in Python's `ALL_SCHEMAS` order.
pub static ALL_TABLES: [&TableDef; 14] = [
    &COMMITS,
    &FILE_SOURCES,
    &FOLDERS,
    &FILES,
    &INSTANCES,
    &PROPERTIES,
    &PROPERTY_GROUPS,
    &TAG_LISTS,
    &TAGS,
    &INSTANCE_VALUES,
    &SHA1_VALUES,
    &FILE_VALUES,
    &INSTANCE_TAG_VALUES,
    &SHA1_TAG_VALUES,
];

/// Creation script of the generic version log (verbatim from Python).
pub const ENTITY_LOG_SQL: &str = "CREATE TABLE IF NOT EXISTS entity_log (  entity_type TEXT NOT NULL,  entity_key  TEXT NOT NULL,  commit_id   INTEGER NOT NULL,  op          INTEGER NOT NULL,  changes     TEXT,  sequence    INTEGER,  PRIMARY KEY (entity_type, entity_key, commit_id));CREATE INDEX IF NOT EXISTS idx_entity_log_commit ON entity_log (commit_id);CREATE INDEX IF NOT EXISTS idx_entity_log_entity ON entity_log (entity_type, entity_key, commit_id);";

/// Creation script of the sequence counter (verbatim from Python).
pub const SEQUENCE_SQL: &str = "CREATE TABLE IF NOT EXISTS sequence (id INTEGER);INSERT INTO sequence (id) VALUES (1);";

/// Synthetic, always-enabled commit holding the folded baseline ops (compaction / genesis).
pub const GENESIS_COMMIT_ID: i64 = 0;

/// Current `data.db` schema version.
pub const DATA_DB_VERSION: i64 = 2;

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------

fn default_redoable() -> Option<i64> {
    Some(1)
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Commit {
    pub id: i64,
    pub group_id: Option<i64>,
    pub source: String,
    pub timestamp: PyDateTime,
    /// Enabled bit: the commit's ops count in the resolved state iff `active == 1`.
    pub active: i64,
    #[serde(default)]
    pub author: Option<String>,
    /// Still on its author's redo stack (only meaningful while `active == 0`).
    #[serde(default = "default_redoable")]
    pub redoable: Option<i64>,
}
impl_entity!(Commit, COMMITS, plain, [id, group_id, source, timestamp, active, author, redoable]);

/// One partial-diff row of the generic version log (`entity_log`).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ChangeOp {
    pub entity_type: String,
    pub entity_key: String,
    pub commit: i64,
    pub op: i64,
    #[serde(default)]
    pub changes: Option<Value>,
    #[serde(default)]
    pub sequence: Option<i64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FileSource {
    pub id: i64,
    pub dtype: String,
    pub name: Option<String>,
    pub root_url: Option<String>,
    #[serde(default)]
    pub metadata: Option<Value>,
    #[serde(default)]
    pub sync_status: Option<Value>,
}
impl_entity!(FileSource, FILE_SOURCES, plain, [id, dtype, name, root_url, metadata as json, sync_status as json]);

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Folder {
    pub id: i64,
    pub source_id: Option<i64>,
    pub path: Option<String>,
    pub name: Option<String>,
    pub parent: Option<i64>,
}
impl_entity!(Folder, FOLDERS, plain, [id, source_id, path, name, parent]);

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct File {
    pub id: i64,
    pub name: Option<String>,
    pub folder_id: Option<i64>,
    pub sha1: Option<String>,
    #[serde(default)]
    pub width: Option<i64>,
    #[serde(default)]
    pub height: Option<i64>,
    #[serde(default)]
    pub format: Option<String>,
    #[serde(default)]
    pub created_at: Option<PyDateTime>,
}
impl_entity!(File, FILES, plain, [id, name, folder_id, sha1, width, height, format, created_at]);

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Instance {
    pub id: i64,
    pub file_id: Option<i64>,
    pub sha1: Option<String>,
}
impl_entity!(Instance, INSTANCES, plain, [id, file_id, sha1]);

#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct Property {
    pub id: i64,
    #[serde(default)]
    pub dtype: Option<String>,
    #[serde(default)]
    pub mode: Option<String>,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub access: Option<String>,
    #[serde(default)]
    pub tag_list_id: Option<i64>,
    #[serde(default)]
    pub system_key: Option<String>,
    #[serde(default)]
    pub property_group_id: Option<i64>,
    #[serde(default)]
    pub commit_id: Option<i64>,
    #[serde(default)]
    pub operation: Option<i64>,
}
impl_entity!(Property, PROPERTIES, tracked, [id, dtype, mode, name, access, tag_list_id, system_key, property_group_id]);

impl Property {
    /// Delete stub for a [`DataCommit`]: `Property(id=i, operation=OP_DELETE)`.
    pub fn delete(id: i64) -> Self {
        Property { id, operation: Some(crate::schema::OP_DELETE), ..Default::default() }
    }
}

#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct PropertyGroup {
    pub id: i64,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub commit_id: Option<i64>,
    #[serde(default)]
    pub operation: Option<i64>,
}
impl_entity!(PropertyGroup, PROPERTY_GROUPS, tracked, [id, name]);

impl PropertyGroup {
    pub fn delete(id: i64) -> Self {
        PropertyGroup { id, operation: Some(crate::schema::OP_DELETE), ..Default::default() }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TagList {
    pub id: i64,
    pub name: Option<String>,
}
impl_entity!(TagList, TAG_LISTS, plain, [id, name]);

#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct Tag {
    pub id: i64,
    #[serde(default)]
    pub list_id: Option<i64>,
    #[serde(default)]
    pub parents: Option<Vec<i64>>,
    #[serde(default)]
    pub value: Option<String>,
    #[serde(default)]
    pub color: Option<i64>,
    #[serde(default)]
    pub commit_id: Option<i64>,
    #[serde(default)]
    pub operation: Option<i64>,
}
impl_entity!(Tag, TAGS, tracked, [id, list_id, parents as json, value, color]);

impl Tag {
    pub fn delete(id: i64) -> Self {
        Tag { id, operation: Some(crate::schema::OP_DELETE), ..Default::default() }
    }
}

#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct InstanceValue {
    pub property_id: i64,
    pub instance_id: i64,
    #[serde(default)]
    pub value: Option<Value>,
    #[serde(default)]
    pub commit_id: Option<i64>,
    #[serde(default)]
    pub operation: Option<i64>,
}
impl_entity!(InstanceValue, INSTANCE_VALUES, tracked, [property_id, instance_id, value as json]);

#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct Sha1Value {
    pub property_id: i64,
    pub sha1: String,
    #[serde(default)]
    pub value: Option<Value>,
    #[serde(default)]
    pub commit_id: Option<i64>,
    #[serde(default)]
    pub operation: Option<i64>,
}
impl_entity!(Sha1Value, SHA1_VALUES, tracked, [property_id, sha1, value as json]);

#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct FileValue {
    pub property_id: i64,
    pub file_id: i64,
    #[serde(default)]
    pub value: Option<Value>,
    #[serde(default)]
    pub commit_id: Option<i64>,
    #[serde(default)]
    pub operation: Option<i64>,
}
impl_entity!(FileValue, FILE_VALUES, tracked, [property_id, file_id, value as json]);

#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct InstanceTagValue {
    pub instance_id: i64,
    pub property_id: i64,
    pub tag_id: i64,
    #[serde(default)]
    pub commit_id: Option<i64>,
    #[serde(default)]
    pub operation: Option<i64>,
}
impl_entity!(InstanceTagValue, INSTANCE_TAG_VALUES, tracked, [instance_id, property_id, tag_id]);

#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct Sha1TagValue {
    pub sha1: String,
    pub property_id: i64,
    pub tag_id: i64,
    #[serde(default)]
    pub commit_id: Option<i64>,
    #[serde(default)]
    pub operation: Option<i64>,
}
impl_entity!(Sha1TagValue, SHA1_TAG_VALUES, tracked, [sha1, property_id, tag_id]);

/// Unified commit for the *logged* (revertable) entities. Each entity carries its own
/// `operation` (CREATE / UPDATE / DELETE); `None` means upsert.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct DataCommit {
    pub properties: Vec<Property>,
    pub property_groups: Vec<PropertyGroup>,
    pub tags: Vec<Tag>,
    pub instance_values: Vec<InstanceValue>,
    pub sha1_values: Vec<Sha1Value>,
    pub file_values: Vec<FileValue>,
}

impl DataCommit {
    pub fn is_empty(&self) -> bool {
        self.properties.is_empty()
            && self.property_groups.is_empty()
            && self.tags.is_empty()
            && self.instance_values.is_empty()
            && self.sha1_values.is_empty()
            && self.file_values.is_empty()
    }
}

/// Backwards-compat shim (`UpsertCommit`): structural + logged upserts keyed by id.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct UpsertCommit {
    pub file_sources: IndexMap<i64, FileSource>,
    pub folders: IndexMap<i64, Folder>,
    pub files: IndexMap<i64, File>,
    pub instances: IndexMap<i64, Instance>,
    pub properties: IndexMap<i64, Property>,
    pub tags: IndexMap<i64, Tag>,
    pub property_groups: IndexMap<i64, PropertyGroup>,
    pub instance_values: IndexMap<i64, Vec<InstanceValue>>,
    pub sha1_values: IndexMap<i64, Vec<Sha1Value>>,
    pub file_values: IndexMap<i64, Vec<FileValue>>,
}

/// Backwards-compat shim (`DeleteCommit`).
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct DeleteCommit {
    pub file_sources: Vec<i64>,
    pub folders: Vec<i64>,
    pub files: Vec<i64>,
    pub instances: Vec<i64>,
    pub properties: Vec<i64>,
    pub tags: Vec<i64>,
    pub property_groups: Vec<i64>,
}

/// Structural rows written by [`crate::data::DataWriter::add_structural`].
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Structural {
    pub file_sources: Vec<FileSource>,
    pub folders: Vec<Folder>,
    pub files: Vec<File>,
    pub instances: Vec<Instance>,
}

/// What a structural delete garbage-collected (sha1s without instances, files without
/// instances). Sorted (Python returns them in set order).
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct OrphanReport {
    pub orphan_sha1s: Vec<String>,
    pub orphan_file_ids: Vec<i64>,
}
