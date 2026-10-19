//! Table descriptions + the generic, chunked SQL helpers every database uses.
//!
//! This is the Rust counterpart of `entity_schema.py`. A [`TableDef`] describes one table
//! exactly as the Python `EntitySchema` derives it from its msgspec struct, so the DDL text is
//! identical. [`Entity`] maps a typed model to/from a row; [`Filter`] reproduces the Python
//! `**filters` convention (scalar → `col = ?`, list → `col IN (…)`, the largest list chunked to
//! stay under 900 bound variables).

use rusqlite::types::{Value as SqlValue, ValueRef};
use rusqlite::{Connection, Row, params_from_iter};
use serde::Serialize;
use serde::de::DeserializeOwned;
use serde_json::Value;

use crate::error::{DbError, Result};
use crate::pyjson;
use crate::pytime::PyDateTime;

/// Python's `_SQLITE_MAX_VARS`: bound variables per statement.
pub const MAX_VARS: usize = 900;

pub const OP_CREATE: i64 = 1;
pub const OP_UPDATE: i64 = 0;
pub const OP_DELETE: i64 = -1;

// ---------------------------------------------------------------------------
// Table description
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IndexKind {
    None,
    Plain,
    Unique,
}

/// One data column (the tracking columns `commit_id` / `operation` / `sequence` are implied by
/// [`TableDef::logged`] / [`TableDef::sequenced`]).
#[derive(Debug, Clone, Copy)]
pub struct ColDef {
    pub name: &'static str,
    /// Declared type: INTEGER, TEXT, REAL, BLOB, TIMESTAMP, JSON or ARRAY.
    pub sql_type: &'static str,
    pub pk: bool,
    pub nullable: bool,
    pub index: IndexKind,
}

impl ColDef {
    /// A nullable, non-key column.
    pub const fn new(name: &'static str, sql_type: &'static str) -> Self {
        ColDef { name, sql_type, pk: false, nullable: true, index: IndexKind::None }
    }
    pub const fn pk(mut self) -> Self {
        self.pk = true;
        self.nullable = false;
        self
    }
    /// Primary key declared `Optional[...]` in Python (nullable in the DDL).
    pub const fn pk_nullable(mut self) -> Self {
        self.pk = true;
        self.nullable = true;
        self
    }
    pub const fn not_null(mut self) -> Self {
        self.nullable = false;
        self
    }
    pub const fn indexed(mut self) -> Self {
        self.index = IndexKind::Plain;
        self
    }
    pub const fn unique(mut self) -> Self {
        self.index = IndexKind::Unique;
        self
    }
}

#[derive(Debug)]
pub struct TableDef {
    pub name: &'static str,
    pub cols: &'static [ColDef],
    /// Has `commit_id` / `operation` columns (Python: "trackable").
    pub logged: bool,
    /// Has a `sequence` column + index (delta sync). Logged implies sequenced.
    pub sequenced: bool,
}

impl TableDef {
    pub fn pk_names(&self) -> Vec<&'static str> {
        self.cols.iter().filter(|c| c.pk).map(|c| c.name).collect()
    }

    pub fn has_column(&self, name: &str) -> bool {
        self.cols.iter().any(|c| c.name == name)
            || (self.logged && (name == "commit_id" || name == "operation"))
            || (self.sequenced && name == "sequence")
    }

    /// Columns read into a model: data columns, then `commit_id, operation` when logged.
    pub fn model_columns(&self) -> Vec<&'static str> {
        let mut v: Vec<&'static str> = self.cols.iter().map(|c| c.name).collect();
        if self.logged {
            v.push("commit_id");
            v.push("operation");
        }
        v
    }

    pub fn select_list(&self) -> String {
        self.model_columns().join(", ")
    }

    /// Number of values a model pushes ([`Entity::push_values`]).
    pub fn model_width(&self) -> usize {
        self.cols.len() + if self.logged { 2 } else { 0 }
    }

    /// `EntitySchema.create_table_sql()` — byte-identical DDL.
    pub fn create_sql(&self) -> String {
        let pks = self.pk_names();
        let composite = pks.len() > 1;
        let mut defs: Vec<String> = Vec::new();
        for c in self.cols {
            let null = if c.nullable { "" } else { " NOT NULL" };
            let pk = if c.pk && !composite { " PRIMARY KEY" } else { "" };
            defs.push(format!("    {} {}{}{}", c.name, c.sql_type, pk, null));
        }
        if self.logged {
            defs.push("    commit_id INTEGER".into());
            defs.push("    operation INTEGER".into());
        }
        if self.sequenced {
            defs.push("    sequence  INTEGER".into());
        }
        if composite {
            defs.push(format!("    PRIMARY KEY ({})", pks.join(", ")));
        }
        let mut idx: Vec<String> = Vec::new();
        if self.sequenced {
            idx.push(format!(
                "CREATE INDEX IF NOT EXISTS idx_{t}_sequence ON {t} (sequence);",
                t = self.name
            ));
        }
        if self.logged {
            idx.push(format!(
                "CREATE INDEX IF NOT EXISTS idx_{t}_operation ON {t} (operation);",
                t = self.name
            ));
        }
        for c in self.cols {
            match c.index {
                IndexKind::None => {}
                IndexKind::Plain | IndexKind::Unique => {
                    let unique = if c.index == IndexKind::Unique { "UNIQUE " } else { "" };
                    idx.push(format!(
                        "CREATE {unique}INDEX IF NOT EXISTS idx_{t}_{c} ON {t} ({c});",
                        t = self.name,
                        c = c.name
                    ));
                }
            }
        }
        format!(
            "CREATE TABLE IF NOT EXISTS {} (\n{}\n);\n{}",
            self.name,
            defs.join(",\n"),
            idx.join("\n")
        )
    }
}

/// `KeyValueSchema.create_table_sql()`.
pub fn kv_create_sql(table: &str) -> String {
    format!("CREATE TABLE IF NOT EXISTS {table} (\n    key   TEXT PRIMARY KEY,\n    value JSON\n);")
}

// ---------------------------------------------------------------------------
// Value conversions
// ---------------------------------------------------------------------------

/// Anything usable as a filter value / bound parameter.
pub trait IntoSql {
    fn into_sql(self) -> SqlValue;
}

impl IntoSql for SqlValue {
    fn into_sql(self) -> SqlValue {
        self
    }
}
impl IntoSql for i64 {
    fn into_sql(self) -> SqlValue {
        SqlValue::Integer(self)
    }
}
impl IntoSql for &i64 {
    fn into_sql(self) -> SqlValue {
        SqlValue::Integer(*self)
    }
}
impl IntoSql for i32 {
    fn into_sql(self) -> SqlValue {
        SqlValue::Integer(self as i64)
    }
}
impl IntoSql for bool {
    fn into_sql(self) -> SqlValue {
        SqlValue::Integer(self as i64)
    }
}
impl IntoSql for &str {
    fn into_sql(self) -> SqlValue {
        SqlValue::Text(self.to_string())
    }
}
impl IntoSql for String {
    fn into_sql(self) -> SqlValue {
        SqlValue::Text(self)
    }
}
impl IntoSql for &String {
    fn into_sql(self) -> SqlValue {
        SqlValue::Text(self.clone())
    }
}
impl<T: IntoSql> IntoSql for Option<T> {
    fn into_sql(self) -> SqlValue {
        match self {
            Some(v) => v.into_sql(),
            None => SqlValue::Null,
        }
    }
}

/// Decode a JSON column value the way the Python schema does: TEXT/BLOB is parsed, an
/// INTEGER/REAL (the column's NUMERIC affinity turned `"42"` into 42) is taken as is.
pub fn sql_to_json(v: ValueRef<'_>) -> std::result::Result<Value, String> {
    Ok(match v {
        ValueRef::Null => Value::Null,
        ValueRef::Integer(i) => Value::from(i),
        ValueRef::Real(f) => serde_json::Number::from_f64(f).map(Value::Number).unwrap_or(Value::Null),
        ValueRef::Text(t) | ValueRef::Blob(t) => {
            let s = std::str::from_utf8(t).map_err(|e| e.to_string())?;
            pyjson::loads(s).map_err(|e| format!("{e} in {s:?}"))?
        }
    })
}

/// Encode a JSON column value: `None`/`null` → NULL, anything else → `json.dumps(value)` text.
pub fn json_to_sql(v: &Value) -> SqlValue {
    if v.is_null() { SqlValue::Null } else { SqlValue::Text(pyjson::dumps(v)) }
}

/// A plain scalar SQL value as a JSON value (TEXT stays a string, it is not parsed).
pub fn sql_to_plain(v: ValueRef<'_>) -> Value {
    match v {
        ValueRef::Null => Value::Null,
        ValueRef::Integer(i) => Value::from(i),
        ValueRef::Real(f) => serde_json::Number::from_f64(f).map(Value::Number).unwrap_or(Value::Null),
        ValueRef::Text(t) => Value::String(String::from_utf8_lossy(t).into_owned()),
        ValueRef::Blob(b) => Value::Array(b.iter().map(|x| Value::from(*x)).collect()),
    }
}

/// A JSON value bound as a plain (non-JSON) column, the way Python's sqlite3 binds the
/// equivalent Python object (bool → 0/1).
pub fn plain_to_sql(v: &Value) -> SqlValue {
    match v {
        Value::Null => SqlValue::Null,
        Value::Bool(b) => SqlValue::Integer(*b as i64),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                SqlValue::Integer(i)
            } else if let Some(f) = n.as_f64() {
                SqlValue::Real(f)
            } else {
                SqlValue::Null
            }
        }
        Value::String(s) => SqlValue::Text(s.clone()),
        other => SqlValue::Text(pyjson::dumps(other)),
    }
}

/// Field codec for the non-JSON column kinds.
pub trait SqlField: Sized {
    fn to_sql_value(&self) -> SqlValue;
    fn from_sql_ref(v: ValueRef<'_>) -> std::result::Result<Self, String>;
}

impl SqlField for i64 {
    fn to_sql_value(&self) -> SqlValue {
        SqlValue::Integer(*self)
    }
    fn from_sql_ref(v: ValueRef<'_>) -> std::result::Result<Self, String> {
        match v {
            ValueRef::Integer(i) => Ok(i),
            ValueRef::Real(f) if f.fract() == 0.0 => Ok(f as i64),
            ValueRef::Text(t) => std::str::from_utf8(t)
                .ok()
                .and_then(|s| s.trim().parse().ok())
                .ok_or_else(|| "expected an integer".to_string()),
            ValueRef::Null => Err("unexpected NULL".into()),
            _ => Err("expected an integer".into()),
        }
    }
}

impl SqlField for String {
    fn to_sql_value(&self) -> SqlValue {
        SqlValue::Text(self.clone())
    }
    fn from_sql_ref(v: ValueRef<'_>) -> std::result::Result<Self, String> {
        match v {
            ValueRef::Text(t) | ValueRef::Blob(t) => Ok(String::from_utf8_lossy(t).into_owned()),
            ValueRef::Integer(i) => Ok(i.to_string()),
            ValueRef::Real(f) => Ok(pyjson::float_repr(f)),
            ValueRef::Null => Err("unexpected NULL".into()),
        }
    }
}

impl SqlField for bool {
    fn to_sql_value(&self) -> SqlValue {
        SqlValue::Integer(*self as i64)
    }
    fn from_sql_ref(v: ValueRef<'_>) -> std::result::Result<Self, String> {
        match v {
            ValueRef::Integer(i) => Ok(i != 0),
            ValueRef::Real(f) => Ok(f != 0.0),
            ValueRef::Null => Err("unexpected NULL".into()),
            _ => Err("expected a boolean".into()),
        }
    }
}

impl SqlField for PyDateTime {
    fn to_sql_value(&self) -> SqlValue {
        SqlValue::Text(self.to_db_string())
    }
    fn from_sql_ref(v: ValueRef<'_>) -> std::result::Result<Self, String> {
        match v {
            ValueRef::Text(t) | ValueRef::Blob(t) => {
                let s = std::str::from_utf8(t).map_err(|e| e.to_string())?;
                PyDateTime::parse(s).ok_or_else(|| format!("bad timestamp {s:?}"))
            }
            ValueRef::Null => Err("unexpected NULL".into()),
            _ => Err("expected a timestamp".into()),
        }
    }
}

impl SqlField for Vec<u8> {
    fn to_sql_value(&self) -> SqlValue {
        SqlValue::Blob(self.clone())
    }
    fn from_sql_ref(v: ValueRef<'_>) -> std::result::Result<Self, String> {
        match v {
            ValueRef::Blob(b) | ValueRef::Text(b) => Ok(b.to_vec()),
            ValueRef::Null => Err("unexpected NULL".into()),
            _ => Err("expected a blob".into()),
        }
    }
}

impl<T: SqlField> SqlField for Option<T> {
    fn to_sql_value(&self) -> SqlValue {
        match self {
            Some(v) => v.to_sql_value(),
            None => SqlValue::Null,
        }
    }
    fn from_sql_ref(v: ValueRef<'_>) -> std::result::Result<Self, String> {
        match v {
            ValueRef::Null => Ok(None),
            other => T::from_sql_ref(other).map(Some),
        }
    }
}

/// Encode a JSON-typed field (`dict`, `list`, `Any`): see [`json_to_sql`].
pub fn json_field_to_sql<T: Serialize>(v: &T) -> SqlValue {
    match serde_json::to_value(v) {
        Ok(v) => json_to_sql(&v),
        Err(_) => SqlValue::Null,
    }
}

pub fn json_field_from_sql<T: DeserializeOwned>(v: ValueRef<'_>) -> std::result::Result<T, String> {
    let j = sql_to_json(v)?;
    serde_json::from_value(j).map_err(|e| e.to_string())
}

/// `numpy.ndarray(float32).tobytes()` — little-endian packed f32, no header.
pub fn f32s_to_sql(v: &[f32]) -> SqlValue {
    let mut out = Vec::with_capacity(v.len() * 4);
    for x in v {
        out.extend_from_slice(&x.to_le_bytes());
    }
    SqlValue::Blob(out)
}

/// `numpy.frombuffer(blob, dtype=float32)`.
pub fn f32s_from_sql(v: ValueRef<'_>) -> std::result::Result<Vec<f32>, String> {
    match v {
        ValueRef::Blob(b) | ValueRef::Text(b) => {
            if b.len() % 4 != 0 {
                return Err(format!("float32 array blob of {} bytes", b.len()));
            }
            Ok(b.chunks_exact(4).map(|c| f32::from_le_bytes([c[0], c[1], c[2], c[3]])).collect())
        }
        ValueRef::Null => Err("unexpected NULL".into()),
        _ => Err("expected a float32 array blob".into()),
    }
}

// ---------------------------------------------------------------------------
// Entity trait + implementation macro
// ---------------------------------------------------------------------------

/// A typed row of a table (msgspec struct counterpart).
pub trait Entity: Sized {
    fn table() -> &'static TableDef;
    /// Decode from a row whose columns are [`TableDef::model_columns`], in order.
    fn from_row(row: &Row<'_>) -> Result<Self>;
    /// Push the values of [`TableDef::model_columns`], in order.
    fn push_values(&self, out: &mut Vec<SqlValue>);
}

#[doc(hidden)]
#[macro_export]
macro_rules! __enc {
    ($v:expr) => {
        $crate::schema::SqlField::to_sql_value(&$v)
    };
    ($v:expr, json) => {
        $crate::schema::json_field_to_sql(&$v)
    };
    ($v:expr, array) => {
        $crate::schema::f32s_to_sql(&$v)
    };
}

#[doc(hidden)]
#[macro_export]
macro_rules! __dec {
    ($row:expr, $i:expr, $t:expr, $name:expr) => {
        $crate::schema::SqlField::from_sql_ref($row.get_ref($i)?)
            .map_err(|e| $crate::error::DbError::decode($t, $name, e))?
    };
    ($row:expr, $i:expr, $t:expr, $name:expr, json) => {
        $crate::schema::json_field_from_sql($row.get_ref($i)?)
            .map_err(|e| $crate::error::DbError::decode($t, $name, e))?
    };
    ($row:expr, $i:expr, $t:expr, $name:expr, array) => {
        $crate::schema::f32s_from_sql($row.get_ref($i)?)
            .map_err(|e| $crate::error::DbError::decode($t, $name, e))?
    };
}

/// Implement [`Entity`] for a struct. Fields are listed in column order; `as json` / `as array`
/// mark JSON and float32-array columns. `tracked` appends `commit_id, operation`.
#[doc(hidden)]
#[macro_export]
macro_rules! impl_entity {
    ($ty:ident, $table:expr, tracked, [$($f:ident $(as $kind:ident)?),* $(,)?]) => {
        impl $crate::schema::Entity for $ty {
            fn table() -> &'static $crate::schema::TableDef { &$table }
            #[allow(unused_assignments)]
            fn from_row(row: &rusqlite::Row<'_>) -> $crate::error::Result<Self> {
                let t = $table.name;
                let mut i = 0usize;
                $( let $f = $crate::__dec!(row, i, t, stringify!($f) $(, $kind)?); i += 1; )*
                let commit_id = $crate::__dec!(row, i, t, "commit_id"); i += 1;
                let operation = $crate::__dec!(row, i, t, "operation");
                Ok($ty { $($f,)* commit_id, operation })
            }
            fn push_values(&self, out: &mut Vec<rusqlite::types::Value>) {
                $( out.push($crate::__enc!(self.$f $(, $kind)?)); )*
                out.push($crate::schema::SqlField::to_sql_value(&self.commit_id));
                out.push($crate::schema::SqlField::to_sql_value(&self.operation));
            }
        }
    };
    ($ty:ident, $table:expr, plain, [$($f:ident $(as $kind:ident)?),* $(,)?]) => {
        impl $crate::schema::Entity for $ty {
            fn table() -> &'static $crate::schema::TableDef { &$table }
            #[allow(unused_assignments)]
            fn from_row(row: &rusqlite::Row<'_>) -> $crate::error::Result<Self> {
                let t = $table.name;
                let mut i = 0usize;
                $( let $f = $crate::__dec!(row, i, t, stringify!($f) $(, $kind)?); i += 1; )*
                Ok($ty { $($f,)* })
            }
            fn push_values(&self, out: &mut Vec<rusqlite::types::Value>) {
                $( out.push($crate::__enc!(self.$f $(, $kind)?)); )*
            }
        }
    };
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub enum FilterVal {
    Eq(SqlValue),
    In(Vec<SqlValue>),
}

/// Python `**filters`: scalar → `col = ?`, list → `col IN (…)`, all AND-ed.
#[derive(Debug, Clone, Default)]
pub struct Filter {
    items: Vec<(String, FilterVal)>,
}

impl Filter {
    pub fn new() -> Self {
        Self::default()
    }

    /// `col = value` (replaces an earlier filter on the same column, like a dict key).
    pub fn eq(mut self, col: &str, v: impl IntoSql) -> Self {
        self.set(col, FilterVal::Eq(v.into_sql()));
        self
    }

    /// `col IN (values…)`. An empty list matches nothing.
    pub fn is_in<I, V>(mut self, col: &str, vals: I) -> Self
    where
        I: IntoIterator<Item = V>,
        V: IntoSql,
    {
        self.set(col, FilterVal::In(vals.into_iter().map(IntoSql::into_sql).collect()));
        self
    }

    fn set(&mut self, col: &str, v: FilterVal) {
        if let Some(slot) = self.items.iter_mut().find(|(c, _)| c == col) {
            slot.1 = v;
        } else {
            self.items.push((col.to_string(), v));
        }
    }

    pub fn has(&self, col: &str) -> bool {
        self.items.iter().any(|(c, _)| c == col)
    }

    pub fn is_empty(&self) -> bool {
        self.items.is_empty()
    }

    pub fn items(&self) -> &[(String, FilterVal)] {
        &self.items
    }
}

/// Which rows of a logged table `get` returns.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum State {
    /// `operation IN (1, 0)` — the default (Python `state=1`).
    #[default]
    Alive,
    /// `operation = -1` — tombstones only (Python `state=-1`).
    Deleted,
    /// No operation filter (Python `state=0`).
    Any,
}

struct ParsedFilter<'a> {
    big: Option<(&'a str, &'a [SqlValue])>,
    fixed_clause: String,
    fixed_params: Vec<SqlValue>,
}

/// `_col_ref`: keep `operation = alive` off the operation index (see Python docstring).
fn col_ref(col: &str, vals: &[SqlValue]) -> String {
    if col == "operation" && !vals.iter().any(|v| matches!(v, SqlValue::Integer(OP_DELETE))) {
        "+operation".to_string()
    } else {
        col.to_string()
    }
}

fn parse_filter<'a>(table: &TableDef, f: &'a Filter) -> Result<ParsedFilter<'a>> {
    for (c, _) in &f.items {
        if !table.has_column(c) {
            return Err(DbError::invalid(format!("unknown column {c:?} for table {}", table.name)));
        }
    }
    let lists: Vec<(&str, &[SqlValue])> = f
        .items
        .iter()
        .filter_map(|(c, v)| match v {
            FilterVal::In(vals) => Some((c.as_str(), vals.as_slice())),
            _ => None,
        })
        .collect();
    // Python: max(lists, key=len) → the first longest list
    let mut big_idx: Option<usize> = None;
    for (i, (_, vals)) in lists.iter().enumerate() {
        if big_idx.is_none_or(|b| vals.len() > lists[b].1.len()) {
            big_idx = Some(i);
        }
    }
    let mut parts: Vec<String> = Vec::new();
    let mut params: Vec<SqlValue> = Vec::new();
    for (i, (c, vals)) in lists.iter().enumerate() {
        if Some(i) == big_idx {
            continue;
        }
        let ph = vec!["?"; vals.len()].join(", ");
        parts.push(format!("{} IN ({})", col_ref(c, vals), ph));
        params.extend(vals.iter().cloned());
    }
    for (c, v) in &f.items {
        if let FilterVal::Eq(v) = v {
            parts.push(format!("{} = ?", col_ref(c, std::slice::from_ref(v))));
            params.push(v.clone());
        }
    }
    Ok(ParsedFilter {
        big: big_idx.map(|i| lists[i]),
        fixed_clause: parts.join(" AND "),
        fixed_params: params,
    })
}

/// `_execute_chunked`: run `{action} FROM {table} WHERE …`, chunking the largest list filter.
/// `on_row` is called for every row of every chunk (pass `None` for DELETE).
pub fn execute_chunked(
    conn: &Connection,
    table: &TableDef,
    action: &str,
    filter: &Filter,
    mut on_row: Option<&mut dyn FnMut(&Row<'_>) -> Result<()>>,
) -> Result<()> {
    let pf = parse_filter(table, filter)?;
    let mut run = |sql: &str, params: Vec<SqlValue>| -> Result<()> {
        let mut stmt = conn.prepare_cached(sql)?;
        match on_row.as_mut() {
            Some(cb) => {
                let mut rows = stmt.query(params_from_iter(params.iter()))?;
                while let Some(r) = rows.next()? {
                    cb(r)?;
                }
            }
            None => {
                stmt.execute(params_from_iter(params.iter()))?;
            }
        }
        Ok(())
    };
    match pf.big {
        None => {
            let mut sql = format!("{action} FROM {}", table.name);
            if !pf.fixed_clause.is_empty() {
                sql.push_str(" WHERE ");
                sql.push_str(&pf.fixed_clause);
            }
            run(&sql, pf.fixed_params.clone())?;
        }
        Some((col, vals)) => {
            let room = MAX_VARS as isize - pf.fixed_params.len() as isize;
            if room < 1 {
                return Err(DbError::invalid(format!(
                    "fixed filter variables ({}) leave no room for chunked IN on {col:?}",
                    pf.fixed_params.len()
                )));
            }
            for chunk in vals.chunks(room as usize) {
                let ph = vec!["?"; chunk.len()].join(", ");
                let mut sql = format!("{action} FROM {} WHERE {} IN ({ph})", table.name, col_ref(col, chunk));
                if !pf.fixed_clause.is_empty() {
                    sql.push_str(" AND ");
                    sql.push_str(&pf.fixed_clause);
                }
                let mut params = chunk.to_vec();
                params.extend(pf.fixed_params.iter().cloned());
                run(&sql, params)?;
            }
        }
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Generic typed operations
// ---------------------------------------------------------------------------

fn state_filter(table: &TableDef, filter: &Filter, state: State) -> Filter {
    let mut f = filter.clone();
    if table.logged && !f.has("operation") {
        match state {
            State::Alive => f = f.is_in("operation", [OP_CREATE, OP_UPDATE]),
            State::Deleted => f = f.eq("operation", OP_DELETE),
            State::Any => {}
        }
    }
    f
}

/// `EntitySchema.get(tx, state, **filters)`.
pub fn get<T: Entity>(conn: &Connection, filter: &Filter, state: State) -> Result<Vec<T>> {
    let table = T::table();
    let f = state_filter(table, filter, state);
    let mut out = Vec::new();
    let action = format!("SELECT {}", table.select_list());
    execute_chunked(conn, table, &action, &f, Some(&mut |r: &Row<'_>| {
        out.push(T::from_row(r)?);
        Ok(())
    }))?;
    Ok(out)
}

/// `EntitySchema.select(tx, columns, **filters)` — raw values of the given columns.
pub fn select(conn: &Connection, table: &TableDef, columns: &[&str], filter: &Filter) -> Result<Vec<Vec<SqlValue>>> {
    for c in columns {
        if !table.has_column(c) {
            return Err(DbError::invalid(format!("unknown column {c:?} for table {}", table.name)));
        }
    }
    let mut out = Vec::new();
    let action = format!("SELECT {}", columns.join(", "));
    let n = columns.len();
    execute_chunked(conn, table, &action, filter, Some(&mut |r: &Row<'_>| {
        let mut row = Vec::with_capacity(n);
        for i in 0..n {
            row.push(r.get::<_, SqlValue>(i)?);
        }
        out.push(row);
        Ok(())
    }))?;
    Ok(out)
}

/// `EntitySchema.delete(tx, **filters)`. At least one filter is required.
pub fn delete(conn: &Connection, table: &TableDef, filter: &Filter) -> Result<()> {
    if filter.is_empty() {
        return Err(DbError::invalid("delete() requires at least one filter"));
    }
    execute_chunked(conn, table, "DELETE", filter, None)
}

/// `EntitySchema.get_by_pk(tx, pk_list)` — any operation. Each key is the pk tuple.
pub fn get_by_pk<T: Entity>(conn: &Connection, pks: &[Vec<SqlValue>]) -> Result<Vec<T>> {
    let table = T::table();
    let mut out = Vec::new();
    select_by_pk(conn, table, &table.select_list(), pks, |r| {
        out.push(T::from_row(r)?);
        Ok(())
    })?;
    Ok(out)
}

/// Rows whose primary key is in `pks`, chunked (`(pk…) IN (VALUES (…), …)`).
pub fn select_by_pk(
    conn: &Connection,
    table: &TableDef,
    columns: &str,
    pks: &[Vec<SqlValue>],
    mut on_row: impl FnMut(&Row<'_>) -> Result<()>,
) -> Result<()> {
    if pks.is_empty() {
        return Ok(());
    }
    let names = table.pk_names();
    let n = names.len();
    let chunk_rows = (MAX_VARS / n).max(1);
    for chunk in pks.chunks(chunk_rows) {
        let sql = if n == 1 {
            format!("SELECT {columns} FROM {} WHERE {} IN ({})", table.name, names[0], vec!["?"; chunk.len()].join(", "))
        } else {
            let tuple = format!("({})", vec!["?"; n].join(","));
            format!(
                "SELECT {columns} FROM {} WHERE ({}) IN (VALUES {})",
                table.name,
                names.join(", "),
                vec![tuple.as_str(); chunk.len()].join(", ")
            )
        };
        let mut params: Vec<&SqlValue> = Vec::with_capacity(chunk.len() * n);
        for pk in chunk {
            if pk.len() != n {
                return Err(DbError::invalid(format!("primary key of {} has {n} columns", table.name)));
            }
            params.extend(pk.iter());
        }
        let mut stmt = conn.prepare_cached(&sql)?;
        let mut rows = stmt.query(params_from_iter(params))?;
        while let Some(r) = rows.next()? {
            on_row(r)?;
        }
    }
    Ok(())
}

/// `EntitySchema.delete_by_pk(tx, pk_list)`.
pub fn delete_by_pk(conn: &Connection, table: &TableDef, pks: &[Vec<SqlValue>]) -> Result<()> {
    if pks.is_empty() {
        return Ok(());
    }
    let names = table.pk_names();
    let n = names.len();
    let chunk_rows = (MAX_VARS / n).max(1);
    for chunk in pks.chunks(chunk_rows) {
        let sql = if n == 1 {
            format!("DELETE FROM {} WHERE {} IN ({})", table.name, names[0], vec!["?"; chunk.len()].join(", "))
        } else {
            let tuple = format!("({})", vec!["?"; n].join(","));
            format!(
                "DELETE FROM {} WHERE ({}) IN (VALUES {})",
                table.name,
                names.join(", "),
                vec![tuple.as_str(); chunk.len()].join(", ")
            )
        };
        let params: Vec<&SqlValue> = chunk.iter().flat_map(|pk| pk.iter()).collect();
        conn.prepare_cached(&sql)?.execute(params_from_iter(params))?;
    }
    Ok(())
}

/// `INSERT OR REPLACE` of raw model rows (each [`TableDef::model_width`] values), stamping
/// `sequence` on sequenced tables. Chunked to stay under [`MAX_VARS`] variables.
pub fn upsert_raw(conn: &Connection, table: &TableDef, rows: &[Vec<SqlValue>], sequence: Option<i64>) -> Result<()> {
    if rows.is_empty() {
        return Ok(());
    }
    let mut cols = table.model_columns();
    if table.sequenced {
        cols.push("sequence");
    }
    let per_row = cols.len();
    let chunk_rows = (MAX_VARS / per_row).max(1);
    let tuple = format!("({})", vec!["?"; per_row].join(", "));
    let seq = SqlValue::from(sequence);
    for chunk in rows.chunks(chunk_rows) {
        let sql = format!(
            "INSERT OR REPLACE INTO {} ({}) VALUES {}",
            table.name,
            cols.join(", "),
            vec![tuple.as_str(); chunk.len()].join(", ")
        );
        let mut params: Vec<&SqlValue> = Vec::with_capacity(chunk.len() * per_row);
        for r in chunk {
            if r.len() != table.model_width() {
                return Err(DbError::invalid(format!("row width {} for table {}", r.len(), table.name)));
            }
            params.extend(r.iter());
            if table.sequenced {
                params.push(&seq);
            }
        }
        conn.prepare_cached(&sql)?.execute(params_from_iter(params))?;
    }
    Ok(())
}

/// `EntitySchema.upsert(tx, objs, sequence)`.
pub fn upsert<T: Entity>(conn: &Connection, objs: &[T], sequence: Option<i64>) -> Result<()> {
    let table = T::table();
    let rows: Vec<Vec<SqlValue>> = objs
        .iter()
        .map(|o| {
            let mut v = Vec::with_capacity(table.model_width());
            o.push_values(&mut v);
            v
        })
        .collect();
    upsert_raw(conn, table, &rows, sequence)
}

/// `EntitySchema.get_since(tx, sequence)` — every row (tombstones included) with
/// `sequence > since`.
pub fn get_since<T: Entity>(conn: &Connection, since: i64) -> Result<Vec<T>> {
    let table = T::table();
    if !table.sequenced {
        return Err(DbError::invalid(format!("table {} is not sequenced", table.name)));
    }
    let sql = format!("SELECT {} FROM {} WHERE sequence > ?", table.select_list(), table.name);
    let mut stmt = conn.prepare_cached(&sql)?;
    let mut rows = stmt.query([since])?;
    let mut out = Vec::new();
    while let Some(r) = rows.next()? {
        out.push(T::from_row(r)?);
    }
    Ok(out)
}

pub(crate) fn table_exists(conn: &Connection, name: &str) -> Result<bool> {
    let mut stmt = conn.prepare_cached("SELECT name FROM sqlite_master WHERE type='table' AND name=?")?;
    Ok(stmt.exists([name])?)
}

pub(crate) fn column_names(conn: &Connection, table: &str) -> Result<Vec<String>> {
    let mut stmt = conn.prepare(&format!("PRAGMA table_info({table})"))?;
    let rows = stmt.query_map([], |r| r.get::<_, String>(1))?;
    Ok(rows.collect::<rusqlite::Result<Vec<_>>>()?)
}
