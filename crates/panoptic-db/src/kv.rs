//! Flat key/value tables (`key TEXT PRIMARY KEY, value JSON`) — port of `key_value_shema.py`.
//!
//! One row per field of the Python struct; the value is `json.dumps(value)` text (or NULL for
//! `None`). Because the column is declared `JSON` (NUMERIC affinity), SQLite stores numeric text
//! such as `"1"` as the INTEGER 1 — readers must accept both a number and JSON text.

use rusqlite::{Connection, OptionalExtension};
use serde_json::{Map, Value};

use crate::error::{DbError, Result};
use crate::schema::{json_to_sql, sql_to_json};

#[derive(Debug, Clone, Copy)]
pub enum KvDefault {
    Null,
    Int(i64),
    Bool(bool),
}

impl KvDefault {
    pub fn to_value(self) -> Value {
        match self {
            KvDefault::Null => Value::Null,
            KvDefault::Int(i) => Value::from(i),
            KvDefault::Bool(b) => Value::Bool(b),
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct KvField {
    pub name: &'static str,
    pub default: KvDefault,
}

pub const fn kv(name: &'static str, default: KvDefault) -> KvField {
    KvField { name, default }
}

#[derive(Debug)]
pub struct KvTable {
    pub name: &'static str,
    pub fields: &'static [KvField],
}

impl KvTable {
    pub fn create_sql(&self) -> String {
        crate::schema::kv_create_sql(self.name)
    }

    fn field(&self, key: &str) -> Result<&KvField> {
        self.fields
            .iter()
            .find(|f| f.name == key)
            .ok_or_else(|| DbError::invalid(format!("{key:?} is not a field of {}", self.name)))
    }

    pub fn is_field(&self, key: &str) -> bool {
        self.fields.iter().any(|f| f.name == key)
    }

    /// `ensure_keys`: insert a row (with the default) for every missing field. Idempotent.
    pub fn ensure_keys(&self, conn: &Connection) -> Result<()> {
        let sql = format!("INSERT OR IGNORE INTO {} (key, value) VALUES (?, ?)", self.name);
        let mut stmt = conn.prepare_cached(&sql)?;
        for f in self.fields {
            stmt.execute(rusqlite::params![f.name, json_to_sql(&f.default.to_value())])?;
        }
        Ok(())
    }

    /// `get_key`: the decoded value of one key (`Null` when absent or NULL).
    pub fn get_key(&self, conn: &Connection, key: &str) -> Result<Value> {
        self.field(key)?;
        let sql = format!("SELECT value FROM {} WHERE key = ?", self.name);
        let v = conn
            .query_row(&sql, [key], |r| Ok(sql_to_json(r.get_ref(0)?)))
            .optional()?;
        match v {
            None => Ok(Value::Null),
            Some(Ok(v)) => Ok(v),
            Some(Err(e)) => Err(DbError::decode(self.name, key, e)),
        }
    }

    /// `get`: every field, NULL / missing fields falling back to the field default.
    pub fn get_all(&self, conn: &Connection) -> Result<Map<String, Value>> {
        let sql = format!("SELECT key, value FROM {}", self.name);
        let mut stmt = conn.prepare_cached(&sql)?;
        let mut rows = stmt.query([])?;
        let mut found: Map<String, Value> = Map::new();
        while let Some(r) = rows.next()? {
            let k: String = r.get(0)?;
            if self.is_field(&k) {
                let v = sql_to_json(r.get_ref(1)?).map_err(|e| DbError::decode(self.name, &k, e))?;
                found.insert(k, v);
            }
        }
        let mut out = Map::new();
        for f in self.fields {
            let v = match found.remove(f.name) {
                Some(v) if !v.is_null() => v,
                _ => f.default.to_value(),
            };
            out.insert(f.name.to_string(), v);
        }
        Ok(out)
    }

    /// `set_key`: upsert one key (`Null` stores SQL NULL).
    pub fn set_key(&self, conn: &Connection, key: &str, value: &Value) -> Result<()> {
        self.field(key)?;
        let sql = format!(
            "INSERT INTO {} (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            self.name
        );
        conn.prepare_cached(&sql)?.execute(rusqlite::params![key, json_to_sql(value)])?;
        Ok(())
    }

    /// `set`: upsert every field of `values` that belongs to the table (fields missing from
    /// `values` are written as NULL, like setting a struct whose attribute is None).
    pub fn set_all(&self, conn: &Connection, values: &Map<String, Value>) -> Result<()> {
        for f in self.fields {
            self.set_key(conn, f.name, values.get(f.name).unwrap_or(&Value::Null))?;
        }
        Ok(())
    }
}

/// Read a KV map field as `Option<String>`.
pub(crate) fn opt_str(m: &Map<String, Value>, k: &str) -> Option<String> {
    match m.get(k) {
        Some(Value::String(s)) => Some(s.clone()),
        Some(Value::Null) | None => None,
        Some(other) => Some(other.to_string()),
    }
}

pub(crate) fn as_bool(m: &Map<String, Value>, k: &str, default: bool) -> bool {
    match m.get(k) {
        Some(Value::Bool(b)) => *b,
        Some(Value::Number(n)) => n.as_f64().is_some_and(|f| f != 0.0),
        _ => default,
    }
}
