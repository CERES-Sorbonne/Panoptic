//! The versioning core (port of `data/resolver.py`): fold the *enabled* partial-diff ops of an
//! entity into its current row, or `None` when it is not alive.
//!
//! Entities are handled generically ([`GenericRow`]: the data columns of the result table as
//! JSON values) so one implementation serves the eight logged entity kinds.

use std::collections::{BTreeMap, BTreeSet};

use rusqlite::Row;
use rusqlite::types::Value as SqlValue;
use serde::Serialize;
use serde_json::{Map, Value};

use super::models::*;
use crate::error::{DbError, Result};
use crate::pyjson::{self, py_eq};
use crate::schema::{OP_CREATE, OP_DELETE, TableDef, json_to_sql, plain_to_sql, sql_to_json, sql_to_plain};

/// The logged entity kinds (`LOGGED_ENTITY_META`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum EntityType {
    Property,
    Group,
    Tag,
    InstanceValue,
    Sha1Value,
    FileValue,
    InstanceTagValue,
    Sha1TagValue,
}

pub struct EntitySpec {
    pub entity_type: EntityType,
    pub name: &'static str,
    pub table: &'static TableDef,
    pub pk_fields: &'static [&'static str],
    /// Scalar fields folded as last-writer-wins registers.
    pub data_fields: &'static [&'static str],
    /// Fields folded as OR-sets (JSON lists of ints).
    pub set_fields: &'static [&'static str],
    /// Junction rows: existence only, no payload.
    pub presence_only: bool,
}

static SPECS: [EntitySpec; 8] = [
    EntitySpec {
        entity_type: EntityType::Property,
        name: "property",
        table: &PROPERTIES,
        pk_fields: &["id"],
        data_fields: &["dtype", "mode", "name", "access", "tag_list_id", "system_key", "property_group_id"],
        set_fields: &[],
        presence_only: false,
    },
    EntitySpec {
        entity_type: EntityType::Group,
        name: "group",
        table: &PROPERTY_GROUPS,
        pk_fields: &["id"],
        data_fields: &["name"],
        set_fields: &[],
        presence_only: false,
    },
    EntitySpec {
        entity_type: EntityType::Tag,
        name: "tag",
        table: &TAGS,
        pk_fields: &["id"],
        data_fields: &["list_id", "value", "color"],
        set_fields: &["parents"],
        presence_only: false,
    },
    EntitySpec {
        entity_type: EntityType::InstanceValue,
        name: "instance_value",
        table: &INSTANCE_VALUES,
        pk_fields: &["property_id", "instance_id"],
        data_fields: &["value"],
        set_fields: &[],
        presence_only: false,
    },
    EntitySpec {
        entity_type: EntityType::Sha1Value,
        name: "sha1_value",
        table: &SHA1_VALUES,
        pk_fields: &["property_id", "sha1"],
        data_fields: &["value"],
        set_fields: &[],
        presence_only: false,
    },
    EntitySpec {
        entity_type: EntityType::FileValue,
        name: "file_value",
        table: &FILE_VALUES,
        pk_fields: &["property_id", "file_id"],
        data_fields: &["value"],
        set_fields: &[],
        presence_only: false,
    },
    EntitySpec {
        entity_type: EntityType::InstanceTagValue,
        name: "instance_tag_value",
        table: &INSTANCE_TAG_VALUES,
        pk_fields: &["instance_id", "property_id", "tag_id"],
        data_fields: &[],
        set_fields: &[],
        presence_only: true,
    },
    EntitySpec {
        entity_type: EntityType::Sha1TagValue,
        name: "sha1_tag_value",
        table: &SHA1_TAG_VALUES,
        pk_fields: &["sha1", "property_id", "tag_id"],
        data_fields: &[],
        set_fields: &[],
        presence_only: true,
    },
];

impl EntityType {
    pub const ALL: [EntityType; 8] = [
        EntityType::Property,
        EntityType::Group,
        EntityType::Tag,
        EntityType::InstanceValue,
        EntityType::Sha1Value,
        EntityType::FileValue,
        EntityType::InstanceTagValue,
        EntityType::Sha1TagValue,
    ];

    pub fn spec(self) -> &'static EntitySpec {
        &SPECS[self as usize]
    }

    /// The `entity_log.entity_type` string.
    pub fn as_str(self) -> &'static str {
        self.spec().name
    }

    pub fn parse(s: &str) -> Option<EntityType> {
        SPECS.iter().find(|sp| sp.name == s).map(|sp| sp.entity_type)
    }

    /// The anchor pk field of a tag junction (`instance_id` / `sha1`).
    pub fn tag_anchor(self) -> Option<&'static str> {
        match self {
            EntityType::InstanceTagValue => Some("instance_id"),
            EntityType::Sha1TagValue => Some("sha1"),
            _ => None,
        }
    }
}

// ---------------------------------------------------------------------------
// Keys
// ---------------------------------------------------------------------------

/// `encode_key(pk)`: `json.dumps(list(pk), separators=(',', ':'))`, e.g. `[10,"abc"]`.
pub fn encode_key(pk: &[Value]) -> String {
    pyjson::dumps_compact(&Value::Array(pk.to_vec()))
}

pub fn decode_key(key: &str) -> Result<Vec<Value>> {
    match serde_json::from_str::<Value>(key)? {
        Value::Array(a) => Ok(a),
        other => Err(DbError::invalid(format!("entity key is not a list: {other}"))),
    }
}

/// A JSON pk component bound as SQL (ints stay ints, strings stay strings).
pub fn key_part_sql(v: &Value) -> SqlValue {
    plain_to_sql(v)
}

// ---------------------------------------------------------------------------
// Generic rows
// ---------------------------------------------------------------------------

/// The data columns of a result row (aligned with `spec.table.cols`) + tracking fields.
#[derive(Debug, Clone, PartialEq)]
pub struct GenericRow {
    pub values: Vec<Value>,
    pub commit_id: Option<i64>,
    pub operation: Option<i64>,
}

impl GenericRow {
    pub fn get<'a>(&'a self, spec: &EntitySpec, field: &str) -> &'a Value {
        static NULL: Value = Value::Null;
        spec.table.cols.iter().position(|c| c.name == field).map(|i| &self.values[i]).unwrap_or(&NULL)
    }

    pub fn pk(&self, spec: &EntitySpec) -> Vec<Value> {
        spec.pk_fields.iter().map(|f| self.get(spec, f).clone()).collect()
    }

    pub fn key(&self, spec: &EntitySpec) -> String {
        encode_key(&self.pk(spec))
    }

    /// Build from a typed model (serde field names = column names).
    pub fn from_model<T: Serialize>(spec: &EntitySpec, obj: &T) -> Result<GenericRow> {
        let v = serde_json::to_value(obj)?;
        let Value::Object(m) = v else {
            return Err(DbError::invalid("model did not serialize to an object"));
        };
        Ok(GenericRow {
            values: spec.table.cols.iter().map(|c| m.get(c.name).cloned().unwrap_or(Value::Null)).collect(),
            commit_id: m.get("commit_id").and_then(Value::as_i64),
            operation: m.get("operation").and_then(Value::as_i64),
        })
    }

    /// Decode from a row selected with `spec.table.select_list()`.
    pub fn from_row(spec: &EntitySpec, row: &Row<'_>) -> Result<GenericRow> {
        let t = spec.table;
        let mut values = Vec::with_capacity(t.cols.len());
        for (i, c) in t.cols.iter().enumerate() {
            let r = row.get_ref(i)?;
            let v = if c.sql_type == "JSON" {
                let v = sql_to_json(r).map_err(|e| DbError::decode(t.name, c.name, e))?;
                v
            } else {
                sql_to_plain(r)
            };
            values.push(v);
        }
        let n = t.cols.len();
        Ok(GenericRow { values, commit_id: row.get(n)?, operation: row.get(n + 1)? })
    }

    /// Values for [`crate::schema::upsert_raw`].
    pub fn to_sql(&self, spec: &EntitySpec) -> Vec<SqlValue> {
        let mut out: Vec<SqlValue> = spec
            .table
            .cols
            .iter()
            .zip(&self.values)
            .map(|(c, v)| if c.sql_type == "JSON" { json_to_sql(v) } else { plain_to_sql(v) })
            .collect();
        out.push(SqlValue::from(self.commit_id));
        out.push(SqlValue::from(self.operation));
        out
    }
}

// ---------------------------------------------------------------------------
// Diff (write path)
// ---------------------------------------------------------------------------

fn int_set(v: &Value) -> Result<BTreeSet<i64>> {
    let mut out = BTreeSet::new();
    match v {
        Value::Null => {}
        Value::Array(a) => {
            for x in a {
                out.insert(as_int(x)?);
            }
        }
        other => return Err(DbError::invalid(format!("expected a list of ids, got {other}"))),
    }
    Ok(out)
}

pub(crate) fn as_int(x: &Value) -> Result<i64> {
    match x {
        Value::Number(n) => n
            .as_i64()
            .or_else(|| n.as_f64().filter(|f| f.fract() == 0.0).map(|f| f as i64))
            .ok_or_else(|| DbError::invalid(format!("expected an integer id, got {n}"))),
        Value::Bool(b) => Ok(*b as i64),
        other => Err(DbError::invalid(format!("expected an integer id, got {other}"))),
    }
}

fn ints(set: impl IntoIterator<Item = i64>) -> Value {
    Value::Array(set.into_iter().map(Value::from).collect())
}

/// `diff_changes(spec, current, incoming)`: the minimal `changes` dict taking `current` to
/// `incoming` (every non-None field on create; only differing fields on update; set fields as
/// `{"add": [...], "remove": [...]}`).
pub fn diff_changes(spec: &EntitySpec, current: Option<&GenericRow>, incoming: &GenericRow) -> Result<Map<String, Value>> {
    let mut changes = Map::new();
    for f in spec.data_fields {
        let nv = incoming.get(spec, f);
        match current {
            None => {
                if !nv.is_null() {
                    changes.insert(f.to_string(), nv.clone());
                }
            }
            Some(cur) => {
                if !py_eq(nv, cur.get(spec, f)) {
                    changes.insert(f.to_string(), nv.clone());
                }
            }
        }
    }
    for f in spec.set_fields {
        let new = int_set(incoming.get(spec, f))?;
        let old = match current {
            Some(cur) => int_set(cur.get(spec, f))?,
            None => BTreeSet::new(),
        };
        let add: Vec<i64> = new.difference(&old).copied().collect();
        let rem: Vec<i64> = old.difference(&new).copied().collect();
        if !add.is_empty() || !rem.is_empty() {
            let mut m = Map::new();
            m.insert("add".into(), ints(add));
            m.insert("remove".into(), ints(rem));
            changes.insert(f.to_string(), Value::Object(m));
        }
    }
    Ok(changes)
}

// ---------------------------------------------------------------------------
// Resolve (read / undo path)
// ---------------------------------------------------------------------------

/// One enabled op of a key, as read from `entity_log`.
#[derive(Debug, Clone, PartialEq)]
pub struct LogOp {
    pub commit: i64,
    pub op: i64,
    pub changes: Option<Value>,
}

/// `resolve(spec, key, ops)`: fold enabled ops (ascending commit order) into a row, or `None`
/// if dead. Existence is causal: an UPDATE on a non-alive entity is ignored.
pub fn resolve(spec: &EntitySpec, key: &str, ops: &[LogOp]) -> Result<Option<GenericRow>> {
    let mut alive = false;
    let mut last_commit: Option<i64> = None;
    let mut scalars: Map<String, Value> = Map::new();
    let mut sets: BTreeMap<&str, BTreeMap<i64, bool>> = spec.set_fields.iter().map(|f| (*f, BTreeMap::new())).collect();

    for op in ops {
        last_commit = Some(op.commit);
        if op.op == OP_DELETE {
            alive = false;
            continue;
        }
        if op.op == OP_CREATE {
            alive = true;
        } else if !alive {
            continue;
        }
        if let Some(Value::Object(ch)) = &op.changes {
            for (k, v) in ch {
                if let Some(m) = sets.get_mut(k.as_str()) {
                    if let Value::Object(delta) = v {
                        if let Some(Value::Array(rem)) = delta.get("remove") {
                            for x in rem {
                                m.insert(as_int(x)?, false);
                            }
                        }
                        if let Some(Value::Array(add)) = delta.get("add") {
                            for x in add {
                                m.insert(as_int(x)?, true);
                            }
                        }
                    }
                } else {
                    scalars.insert(k.clone(), v.clone());
                }
            }
        }
    }

    if !alive {
        return Ok(None);
    }
    let pk = decode_key(key)?;
    let mut values = Vec::with_capacity(spec.table.cols.len());
    for c in spec.table.cols {
        let v = if let Some(i) = spec.pk_fields.iter().position(|f| *f == c.name) {
            pk.get(i).cloned().unwrap_or(Value::Null)
        } else if spec.data_fields.contains(&c.name) {
            scalars.get(c.name).cloned().unwrap_or(Value::Null)
        } else if let Some(m) = sets.get(c.name) {
            ints(m.iter().filter(|(_, present)| **present).map(|(k, _)| *k))
        } else {
            Value::Null
        };
        values.push(v);
    }
    Ok(Some(GenericRow { values, commit_id: last_commit, operation: Some(OP_CREATE) }))
}

/// `_same_state(spec, a, b)`.
pub fn same_state(spec: &EntitySpec, a: &GenericRow, b: &GenericRow) -> Result<bool> {
    if a.operation != b.operation {
        return Ok(false);
    }
    for f in spec.data_fields {
        if !py_eq(a.get(spec, f), b.get(spec, f)) {
            return Ok(false);
        }
    }
    for f in spec.set_fields {
        if int_set(a.get(spec, f))? != int_set(b.get(spec, f))? {
            return Ok(false);
        }
    }
    Ok(true)
}

/// `_snapshot_changes(spec, resolved)`: the full-snapshot `changes` of a genesis op.
pub fn snapshot_changes(spec: &EntitySpec, resolved: &GenericRow) -> Result<Option<Map<String, Value>>> {
    if spec.presence_only {
        return Ok(None);
    }
    let mut changes = Map::new();
    for f in spec.data_fields {
        let v = resolved.get(spec, f);
        if !v.is_null() {
            changes.insert(f.to_string(), v.clone());
        }
    }
    for f in spec.set_fields {
        let vals = int_set(resolved.get(spec, f))?;
        if !vals.is_empty() {
            let mut m = Map::new();
            m.insert("add".into(), ints(vals));
            m.insert("remove".into(), Value::Array(vec![]));
            changes.insert(f.to_string(), Value::Object(m));
        }
    }
    Ok(Some(changes))
}
