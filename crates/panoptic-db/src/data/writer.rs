//! `data.db` writer (port of `data/data_writer.py`).
//!
//! Logged entities (properties / groups / tags / values / tag junctions) are journaled as
//! partial-diff ops in `entity_log` and materialized into typed result tables by folding the
//! *enabled* ops ([`resolve`]). Undo / redo flip a commit's `active` bit and re-resolve the
//! entities it touched. Structural entities (file sources / folders / files / instances) are
//! sequenced but not logged: written by [`DataWriter::add_structural`], hard-deleted, never
//! undone.

use std::collections::{BTreeSet, HashMap};
use std::path::Path;

use indexmap::{IndexMap, IndexSet};
use rusqlite::types::Value as SqlValue;
use rusqlite::{Connection, OptionalExtension, Row, params_from_iter};
use serde_json::{Map, Value};

use super::models::*;
use super::resolver::{
    EntitySpec, EntityType, GenericRow, LogOp, as_int, decode_key, diff_changes, encode_key, key_part_sql, resolve,
    same_state, snapshot_changes,
};
use crate::conn::{DbDescription, WriterConn};
use crate::error::{DbError, Result};
use crate::pyjson;
use crate::pytime::PyDateTime;
use crate::schema::{
    self, Entity, Filter, MAX_VARS, OP_CREATE, OP_DELETE, State, column_names, execute_chunked, table_exists,
};

pub(crate) const TAG_DTYPE: &str = "tag";
pub(crate) const MULTI_TAGS_DTYPE: &str = "multi_tags";

pub(crate) fn is_tag_dtype(d: Option<&str>) -> bool {
    matches!(d, Some(TAG_DTYPE) | Some(MULTI_TAGS_DTYPE))
}

/// `datastore_desc`: tables + the v1 → v2 migration (`commits.redoable`).
pub fn data_db_description() -> DbDescription {
    let mut tables: Vec<(&'static str, String)> = ALL_TABLES.iter().map(|t| (t.name, t.create_sql())).collect();
    tables.push(("entity_log", ENTITY_LOG_SQL.to_string()));
    tables.push(("sequence", SEQUENCE_SQL.to_string()));
    DbDescription { name: "data.db", version: DATA_DB_VERSION, tables, migrations: vec![(1, migrate_v1_add_commit_redoable)] }
}

/// v1 → v2: `commits.redoable` (existing commits start redoable). A brand-new DB has no
/// `commits` table yet (migrations run before table creation) and gets it from the DDL.
fn migrate_v1_add_commit_redoable(conn: &Connection) -> Result<()> {
    if !table_exists(conn, COMMITS.name)? {
        return Ok(());
    }
    if column_names(conn, COMMITS.name)?.iter().any(|c| c == "redoable") {
        return Ok(());
    }
    conn.execute_batch("ALTER TABLE commits ADD COLUMN redoable INTEGER; UPDATE commits SET redoable = 1;")?;
    Ok(())
}

/// A pending op of the commit being built.
#[derive(Debug, Clone)]
struct PendingOp {
    et: EntityType,
    key: String,
    op: i64,
    changes: Option<Map<String, Value>>,
}

type OpMap = IndexMap<(EntityType, String), PendingOp>;

fn add(ops: &mut OpMap, op: Option<PendingOp>) {
    if let Some(op) = op {
        ops.insert((op.et, op.key.clone()), op);
    }
}

/// The writer of one `data.db`. `Send + Sync`; every method runs one `BEGIN IMMEDIATE`
/// transaction on the single writer connection.
pub struct DataWriter {
    conn: WriterConn,
}

impl DataWriter {
    /// Open (create / migrate) the database — `DataWriter(path).start()`.
    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        Ok(DataWriter { conn: WriterConn::open(path, &data_db_description())? })
    }

    pub fn path(&self) -> &Path {
        self.conn.path()
    }

    /// Run arbitrary work in a write transaction (escape hatch for callers that need it).
    pub fn transaction<T>(&self, f: impl FnOnce(&Connection) -> Result<T>) -> Result<T> {
        self.conn.tx(|tx| f(tx))
    }

    /// Read through the writer connection (sees uncommitted state of nobody else).
    pub fn read<T>(&self, f: impl FnOnce(&Connection) -> Result<T>) -> Result<T> {
        self.conn.read(f)
    }

    pub fn checkpoint(&self) -> Result<()> {
        self.conn.checkpoint()
    }

    // ==================================================================
    // Logged commit
    // ==================================================================

    /// Unified create / update / delete of the logged entities. Returns `None` (and writes
    /// nothing, consumes no sequence) when the payload changes nothing.
    pub fn apply_commit(
        &self,
        source: &str,
        data: &DataCommit,
        group_id: Option<i64>,
        author: Option<&str>,
    ) -> Result<Option<Commit>> {
        self.conn.tx(|tx| apply_commit_tx(tx, source, data, group_id, author))
    }

    /// Disable `author`'s most recent enabled commit (`author` None = authorless commits).
    pub fn undo(&self, author: Option<&str>) -> Result<Option<Commit>> {
        self.conn.tx(|tx| {
            let id: Option<i64> = tx
                .query_row(
                    "SELECT id FROM commits WHERE active = 1 AND author IS ? AND id > ? ORDER BY id DESC LIMIT 1",
                    rusqlite::params![author, GENESIS_COMMIT_ID],
                    |r| r.get(0),
                )
                .optional()?;
            match id {
                Some(id) => set_commit_active_tx(tx, id, false),
                None => Ok(None),
            }
        })
    }

    /// Re-enable `author`'s oldest commit still on the redo stack.
    pub fn redo(&self, author: Option<&str>) -> Result<Option<Commit>> {
        self.conn.tx(|tx| {
            let id: Option<i64> = tx
                .query_row(
                    "SELECT id FROM commits WHERE active = 0 AND redoable = 1 AND author IS ? AND id > ? ORDER BY id ASC LIMIT 1",
                    rusqlite::params![author, GENESIS_COMMIT_ID],
                    |r| r.get(0),
                )
                .optional()?;
            match id {
                Some(id) => set_commit_active_tx(tx, id, true),
                None => Ok(None),
            }
        })
    }

    /// Toggle any commit's enabled bit and re-resolve what it touched. Commit 0 (genesis) is
    /// never toggled.
    pub fn set_commit_active(&self, commit_id: i64, active: bool) -> Result<Option<Commit>> {
        if commit_id == GENESIS_COMMIT_ID {
            return Ok(None);
        }
        self.conn.tx(|tx| set_commit_active_tx(tx, commit_id, active))
    }

    /// Fold every commit `0 < id <= horizon` into the frozen genesis baseline.
    pub fn compact(&self, horizon_commit_id: i64) -> Result<()> {
        self.conn.tx(|tx| compact_tx(tx, horizon_commit_id))
    }

    /// Backwards-compat shim (`apply_upsert_commit`).
    pub fn apply_upsert_commit(
        &self,
        source: &str,
        data: &UpsertCommit,
        group_id: Option<i64>,
        author: Option<&str>,
    ) -> Result<Option<Commit>> {
        if !data.file_sources.is_empty() || !data.folders.is_empty() || !data.files.is_empty() || !data.instances.is_empty() {
            self.add_structural(&Structural {
                file_sources: data.file_sources.values().cloned().collect(),
                folders: data.folders.values().cloned().collect(),
                files: data.files.values().cloned().collect(),
                instances: data.instances.values().cloned().collect(),
            })?;
        }
        let commit = DataCommit {
            properties: data.properties.values().cloned().collect(),
            property_groups: data.property_groups.values().cloned().collect(),
            tags: data.tags.values().cloned().collect(),
            instance_values: data.instance_values.values().flatten().cloned().collect(),
            sha1_values: data.sha1_values.values().flatten().cloned().collect(),
            file_values: data.file_values.values().flatten().cloned().collect(),
        };
        if commit.is_empty() {
            return Ok(None);
        }
        self.apply_commit(source, &commit, group_id, author)
    }

    /// Backwards-compat shim (`apply_delete_commit`).
    pub fn apply_delete_commit(
        &self,
        source: &str,
        data: &DeleteCommit,
        group_id: Option<i64>,
        author: Option<&str>,
    ) -> Result<Option<Commit>> {
        if !data.instances.is_empty() {
            self.delete_instances(&data.instances)?;
        }
        if !data.files.is_empty() {
            self.delete_files(&data.files)?;
        }
        if !data.folders.is_empty() {
            self.delete_folders(&data.folders)?;
        }
        if !data.file_sources.is_empty() {
            self.delete_file_sources(&data.file_sources)?;
        }
        let commit = DataCommit {
            properties: data.properties.iter().map(|i| Property::delete(*i)).collect(),
            property_groups: data.property_groups.iter().map(|i| PropertyGroup::delete(*i)).collect(),
            tags: data.tags.iter().map(|i| Tag::delete(*i)).collect(),
            ..Default::default()
        };
        if commit.is_empty() {
            return Ok(None);
        }
        self.apply_commit(source, &commit, group_id, author)
    }

    // ==================================================================
    // Structural write API
    // ==================================================================

    /// Upsert structural rows (one sequence for the whole call, consumed even when empty).
    pub fn add_structural(&self, s: &Structural) -> Result<()> {
        self.conn.tx(|tx| {
            let seq = next_sequence(tx)?;
            if !s.file_sources.is_empty() {
                schema::upsert(tx, &s.file_sources, Some(seq))?;
            }
            if !s.folders.is_empty() {
                schema::upsert(tx, &s.folders, Some(seq))?;
            }
            if !s.files.is_empty() {
                schema::upsert(tx, &s.files, Some(seq))?;
            }
            if !s.instances.is_empty() {
                schema::upsert(tx, &s.instances, Some(seq))?;
            }
            Ok(())
        })
    }

    /// `tag_lists` rows (not sequenced, not logged; only the project conversion writes them).
    pub fn upsert_tag_lists(&self, lists: &[TagList]) -> Result<()> {
        self.conn.tx(|tx| schema::upsert(tx, lists, None))
    }

    /// The id of the `local` file source, creating it with `fs_id` when missing.
    pub fn get_or_create_local_file_source(&self, fs_id: i64) -> Result<i64> {
        let existing: Vec<FileSource> = self.conn.read(|c| schema::get(c, &Filter::new().eq("dtype", "local"), State::Any))?;
        if let Some(fs) = existing.first() {
            return Ok(fs.id);
        }
        self.add_structural(&Structural {
            file_sources: vec![FileSource {
                id: fs_id,
                dtype: "local".into(),
                name: Some("local_filesystem".into()),
                root_url: None,
                metadata: None,
                sync_status: None,
            }],
            ..Default::default()
        })?;
        Ok(fs_id)
    }

    pub fn delete_instances(&self, ids: &[i64]) -> Result<OrphanReport> {
        self.conn.tx(|tx| delete_instances_tx(tx, ids))
    }

    pub fn delete_files(&self, ids: &[i64]) -> Result<OrphanReport> {
        self.conn.tx(|tx| delete_files_tx(tx, ids))
    }

    pub fn delete_folders(&self, ids: &[i64]) -> Result<OrphanReport> {
        self.conn.tx(|tx| delete_folders_tx(tx, ids))
    }

    /// Deletes the sources' folders (recursively). The `local` source row itself is permanent.
    pub fn delete_file_sources(&self, ids: &[i64]) -> Result<OrphanReport> {
        self.conn.tx(|tx| {
            if ids.is_empty() {
                return Ok(OrphanReport::default());
            }
            let local: BTreeSet<i64> = schema::select(tx, &FILE_SOURCES, &["id"], &Filter::new().eq("dtype", "local"))?
                .into_iter()
                .filter_map(|r| int_of(&r[0]))
                .collect();
            let folders: Vec<i64> = schema::select(tx, &FOLDERS, &["id"], &Filter::new().is_in("source_id", ids.iter().copied()))?
                .into_iter()
                .filter_map(|r| int_of(&r[0]))
                .collect();
            let report = delete_folders_tx(tx, &folders)?;
            let deletable: Vec<Vec<SqlValue>> =
                ids.iter().filter(|i| !local.contains(i)).map(|i| vec![SqlValue::Integer(*i)]).collect();
            schema::delete_by_pk(tx, &FILE_SOURCES, &deletable)?;
            Ok(report)
        })
    }
}

// ======================================================================
// Sequence
// ======================================================================

/// `_exec_get_sequence`: atomically bump the counter and return the value to stamp (the
/// pre-increment value). The `sequence` table therefore always holds *next* sequence.
pub fn next_sequence(conn: &Connection) -> Result<i64> {
    let r: Option<i64> = conn.query_row("UPDATE sequence SET id = id + 1 RETURNING id;", [], |r| r.get(0)).optional()?;
    match r {
        Some(id) => Ok(id - 1),
        None => {
            conn.execute("INSERT INTO sequence (id) VALUES (1)", [])?;
            Ok(1)
        }
    }
}

fn int_of(v: &SqlValue) -> Option<i64> {
    match v {
        SqlValue::Integer(i) => Some(*i),
        _ => None,
    }
}

// ======================================================================
// Generic access to result tables
// ======================================================================

fn generic_get(conn: &Connection, spec: &EntitySpec, filter: &Filter, state: State) -> Result<Vec<GenericRow>> {
    let table = spec.table;
    let mut f = filter.clone();
    if !f.has("operation") {
        match state {
            State::Alive => f = f.is_in("operation", [schema::OP_CREATE, schema::OP_UPDATE]),
            State::Deleted => f = f.eq("operation", OP_DELETE),
            State::Any => {}
        }
    }
    let mut out = Vec::new();
    let action = format!("SELECT {}", table.select_list());
    execute_chunked(conn, table, &action, &f, Some(&mut |r: &Row<'_>| {
        out.push(GenericRow::from_row(spec, r)?);
        Ok(())
    }))?;
    Ok(out)
}

fn key_to_pk_sql(key: &str) -> Result<Vec<SqlValue>> {
    Ok(decode_key(key)?.iter().map(key_part_sql).collect())
}

/// Result rows (tombstones included) of `keys`, by key.
fn current_rows(conn: &Connection, spec: &EntitySpec, keys: &[String]) -> Result<HashMap<String, GenericRow>> {
    let pks: Vec<Vec<SqlValue>> = keys.iter().map(|k| key_to_pk_sql(k)).collect::<Result<_>>()?;
    let mut out = HashMap::with_capacity(keys.len());
    schema::select_by_pk(conn, spec.table, &spec.table.select_list(), &pks, |r| {
        let row = GenericRow::from_row(spec, r)?;
        out.insert(row.key(spec), row);
        Ok(())
    })?;
    Ok(out)
}

fn alive_row(conn: &Connection, spec: &EntitySpec, key: &str) -> Result<Option<GenericRow>> {
    let mut rows = current_rows(conn, spec, &[key.to_string()])?;
    Ok(rows.remove(key).filter(|r| r.operation != Some(OP_DELETE)))
}

fn parse_changes(et: EntityType, text: Option<String>) -> Result<Option<Value>> {
    match text {
        None => Ok(None),
        Some(t) => pyjson::loads(&t).map(Some).map_err(|e| DbError::decode("entity_log", et.as_str(), e.to_string())),
    }
}

/// `_enabled_ops`: enabled ops of one key (commit 0 always enabled), ascending commit id.
fn enabled_ops(conn: &Connection, et: EntityType, key: &str, up_to: Option<i64>) -> Result<Vec<LogOp>> {
    let mut sql = String::from(
        "SELECT el.op, el.changes, el.commit_id FROM entity_log el LEFT JOIN commits c ON c.id = el.commit_id \
         WHERE el.entity_type = ? AND el.entity_key = ? AND (el.commit_id = 0 OR c.active = 1)",
    );
    let mut params: Vec<SqlValue> = vec![SqlValue::Text(et.as_str().into()), SqlValue::Text(key.into())];
    if let Some(h) = up_to {
        sql.push_str(" AND el.commit_id <= ?");
        params.push(SqlValue::Integer(h));
    }
    sql.push_str(" ORDER BY el.commit_id");
    let mut stmt = conn.prepare_cached(&sql)?;
    let mut rows = stmt.query(params_from_iter(params.iter()))?;
    let mut out = Vec::new();
    while let Some(r) = rows.next()? {
        out.push(LogOp { op: r.get(0)?, changes: parse_changes(et, r.get(1)?)?, commit: r.get(2)? });
    }
    Ok(out)
}

/// `_enabled_ops_many`.
fn enabled_ops_many(conn: &Connection, et: EntityType, keys: &[String]) -> Result<HashMap<String, Vec<LogOp>>> {
    let mut out: HashMap<String, Vec<LogOp>> = HashMap::new();
    for chunk in keys.chunks(MAX_VARS) {
        let sql = format!(
            "SELECT el.entity_key, el.op, el.changes, el.commit_id FROM entity_log el LEFT JOIN commits c ON c.id = el.commit_id \
             WHERE el.entity_type = ? AND el.entity_key IN ({}) AND (el.commit_id = 0 OR c.active = 1) ORDER BY el.commit_id",
            vec!["?"; chunk.len()].join(", ")
        );
        let mut params: Vec<&str> = Vec::with_capacity(chunk.len() + 1);
        params.push(et.as_str());
        params.extend(chunk.iter().map(String::as_str));
        let mut stmt = conn.prepare_cached(&sql)?;
        let mut rows = stmt.query(params_from_iter(params))?;
        while let Some(r) = rows.next()? {
            let key: String = r.get(0)?;
            let op = LogOp { op: r.get(1)?, changes: parse_changes(et, r.get(2)?)?, commit: r.get(3)? };
            out.entry(key).or_default().push(op);
        }
    }
    Ok(out)
}

fn touched_by_commit(conn: &Connection, commit_id: i64) -> Result<Vec<(EntityType, String)>> {
    let mut stmt = conn.prepare_cached("SELECT DISTINCT entity_type, entity_key FROM entity_log WHERE commit_id = ?")?;
    let mut rows = stmt.query([commit_id])?;
    let mut out = Vec::new();
    while let Some(r) = rows.next()? {
        let et: String = r.get(0)?;
        let et = EntityType::parse(&et).ok_or_else(|| DbError::invalid(format!("unknown entity_type {et:?} in entity_log")))?;
        out.push((et, r.get(1)?));
    }
    Ok(out)
}

// ======================================================================
// Commit construction
// ======================================================================

fn apply_commit_tx(
    tx: &Connection,
    source: &str,
    data: &DataCommit,
    group_id: Option<i64>,
    author: Option<&str>,
) -> Result<Option<Commit>> {
    let commit_id: i64 = tx.query_row("SELECT COALESCE(MAX(id), 0) FROM commits", [], |r| r.get(0))? + 1;
    let now = PyDateTime::now();
    let group_id = group_id.unwrap_or(commit_id);

    let ops = build_ops(tx, data)?;
    if ops.is_empty() {
        return Ok(None);
    }
    let seq = next_sequence(tx)?;

    let commit = Commit {
        id: commit_id,
        group_id: Some(group_id),
        source: source.to_string(),
        timestamp: now,
        active: 1,
        author: author.map(str::to_string),
        redoable: Some(1),
    };
    schema::upsert(tx, std::slice::from_ref(&commit), None)?;
    tx.execute(
        "UPDATE commits SET redoable = 0 WHERE active = 0 AND redoable = 1 AND author IS ?",
        rusqlite::params![author],
    )?;

    append_ops(tx, commit_id, ops.values(), seq)?;
    let touched: Vec<(EntityType, String)> = ops.keys().cloned().collect();
    materialize_many(tx, &touched, seq)?;
    Ok(Some(commit))
}

fn append_ops<'a>(tx: &Connection, commit_id: i64, ops: impl Iterator<Item = &'a PendingOp>, seq: i64) -> Result<()> {
    let mut stmt = tx.prepare_cached(
        "INSERT OR REPLACE INTO entity_log (entity_type, entity_key, commit_id, op, changes, sequence) VALUES (?,?,?,?,?,?)",
    )?;
    for o in ops {
        let changes = o.changes.as_ref().map(|c| pyjson::dumps(&Value::Object(c.clone())));
        stmt.execute(rusqlite::params![o.et.as_str(), o.key, commit_id, o.op, changes, seq])?;
    }
    Ok(())
}

struct Cell {
    value_type: EntityType,
    tag_type: Option<EntityType>,
    anchor: Value,
    pid: i64,
    value: Value,
}

fn build_ops(tx: &Connection, data: &DataCommit) -> Result<OpMap> {
    let mut ops: OpMap = IndexMap::new();
    let mut del_prop_ids: Vec<i64> = Vec::new();
    let mut del_tag_ids: Vec<i64> = Vec::new();

    for g in &data.property_groups {
        let row = GenericRow::from_model(EntityType::Group.spec(), g)?;
        add(&mut ops, entity_op(tx, EntityType::Group, &row)?);
    }
    for p in &data.properties {
        if p.operation == Some(OP_DELETE) {
            del_prop_ids.push(p.id);
        }
        let row = GenericRow::from_model(EntityType::Property.spec(), p)?;
        add(&mut ops, entity_op(tx, EntityType::Property, &row)?);
    }
    for t in &data.tags {
        if t.operation == Some(OP_DELETE) {
            del_tag_ids.push(t.id);
        }
        let row = GenericRow::from_model(EntityType::Tag.spec(), t)?;
        add(&mut ops, entity_op(tx, EntityType::Tag, &row)?);
    }

    let dtypes = dtype_map(tx, data)?;
    let tag_type_for = |pid: i64, tt: Option<EntityType>| -> Option<EntityType> {
        if is_tag_dtype(dtypes.get(&pid).and_then(|d| d.as_deref())) { tt } else { None }
    };
    let mut cells: Vec<Cell> = Vec::new();
    for v in &data.instance_values {
        cells.push(Cell {
            value_type: EntityType::InstanceValue,
            tag_type: tag_type_for(v.property_id, Some(EntityType::InstanceTagValue)),
            anchor: Value::from(v.instance_id),
            pid: v.property_id,
            value: v.value.clone().unwrap_or(Value::Null),
        });
    }
    for v in &data.sha1_values {
        cells.push(Cell {
            value_type: EntityType::Sha1Value,
            tag_type: tag_type_for(v.property_id, Some(EntityType::Sha1TagValue)),
            anchor: Value::from(v.sha1.clone()),
            pid: v.property_id,
            value: v.value.clone().unwrap_or(Value::Null),
        });
    }
    for v in &data.file_values {
        cells.push(Cell {
            value_type: EntityType::FileValue,
            tag_type: None,
            anchor: Value::from(v.file_id),
            pid: v.property_id,
            value: v.value.clone().unwrap_or(Value::Null),
        });
    }

    let (values, tags) = current_cells(tx, &cells)?;
    for cell in &cells {
        if let Some(tt) = cell.tag_type {
            let existing = tags.get(&(tt, pyjson::dumps_compact(&cell.anchor), cell.pid)).cloned().unwrap_or_default();
            tag_junction_ops(&mut ops, tt, &cell.anchor, cell.pid, &cell.value, &existing)?;
        } else {
            let key = encode_key(&value_pk(cell.value_type, cell.pid, &cell.anchor));
            let current = values.get(&(cell.value_type, key.clone()));
            add(&mut ops, scalar_value_op(cell.value_type, key, &cell.value, current));
        }
    }

    for op in cascade_delete_ops(tx, &del_prop_ids, &del_tag_ids)? {
        add(&mut ops, Some(op));
    }
    Ok(ops)
}

/// pk of a scalar value cell, in spec order (`property_id` first for all three value tables).
fn value_pk(et: EntityType, pid: i64, anchor: &Value) -> Vec<Value> {
    et.spec().pk_fields.iter().map(|f| if *f == "property_id" { Value::from(pid) } else { anchor.clone() }).collect()
}

fn entity_op(tx: &Connection, et: EntityType, incoming: &GenericRow) -> Result<Option<PendingOp>> {
    let spec = et.spec();
    let key = incoming.key(spec);
    if incoming.operation == Some(OP_DELETE) {
        // Already dead: a second DELETE would only add an undo that does nothing.
        if alive_row(tx, spec, &key)?.is_none() {
            return Ok(None);
        }
        return Ok(Some(PendingOp { et, key, op: OP_DELETE, changes: None }));
    }
    let current = alive_row(tx, spec, &key)?;
    let op = if current.is_none() { OP_CREATE } else { schema::OP_UPDATE };
    let changes = diff_changes(spec, current.as_ref(), incoming)?;
    if op == schema::OP_UPDATE && changes.is_empty() {
        return Ok(None);
    }
    Ok(Some(PendingOp { et, key, op, changes: Some(changes) }))
}

type CellValues = HashMap<(EntityType, String), GenericRow>;
type CellTags = HashMap<(EntityType, String, i64), BTreeSet<i64>>;

/// `_current_cells`: what the written cells hold now (alive scalar rows; alive tag ids).
fn current_cells(tx: &Connection, cells: &[Cell]) -> Result<(CellValues, CellTags)> {
    let mut scalar_keys: IndexMap<EntityType, IndexSet<String>> = IndexMap::new();
    let mut tag_anchors: IndexMap<(EntityType, i64), IndexMap<String, Value>> = IndexMap::new();
    for c in cells {
        match c.tag_type {
            Some(tt) => {
                tag_anchors.entry((tt, c.pid)).or_default().insert(pyjson::dumps_compact(&c.anchor), c.anchor.clone());
            }
            None => {
                scalar_keys.entry(c.value_type).or_default().insert(encode_key(&value_pk(c.value_type, c.pid, &c.anchor)));
            }
        }
    }
    let mut values: CellValues = HashMap::new();
    for (vt, keys) in scalar_keys {
        let spec = vt.spec();
        let keys: Vec<String> = keys.into_iter().collect();
        for (key, row) in current_rows(tx, spec, &keys)? {
            if row.operation != Some(OP_DELETE) {
                values.insert((vt, key), row);
            }
        }
    }
    let mut tags: CellTags = HashMap::new();
    for ((tt, pid), anchors) in tag_anchors {
        let spec = tt.spec();
        let anchor_field = tt.tag_anchor().expect("junction type");
        let f = Filter::new().eq("property_id", pid).is_in(anchor_field, anchors.values().map(key_part_sql));
        for r in generic_get(tx, spec, &f, State::Any)? {
            if r.operation == Some(OP_CREATE) {
                let anchor = pyjson::dumps_compact(r.get(spec, anchor_field));
                let tag_id = as_int(r.get(spec, "tag_id"))?;
                tags.entry((tt, anchor, pid)).or_default().insert(tag_id);
            }
        }
    }
    Ok((values, tags))
}

fn scalar_value_op(et: EntityType, key: String, value: &Value, current: Option<&GenericRow>) -> Option<PendingOp> {
    if let Some(cur) = current {
        if pyjson::py_eq(cur.get(et.spec(), "value"), value) {
            return None;
        }
    }
    let mut changes = Map::new();
    changes.insert("value".into(), value.clone());
    // A value set asserts existence: OP_CREATE, so the last enabled set wins.
    Some(PendingOp { et, key, op: OP_CREATE, changes: Some(changes) })
}

fn junction_key(tt: EntityType, anchor: &Value, pid: i64, tag_id: i64) -> String {
    let anchor_field = tt.tag_anchor().expect("junction type");
    let pk: Vec<Value> = tt
        .spec()
        .pk_fields
        .iter()
        .map(|f| {
            if *f == anchor_field {
                anchor.clone()
            } else if *f == "property_id" {
                Value::from(pid)
            } else {
                Value::from(tag_id)
            }
        })
        .collect();
    encode_key(&pk)
}

fn tag_junction_ops(
    ops: &mut OpMap,
    tt: EntityType,
    anchor: &Value,
    pid: i64,
    value: &Value,
    existing: &BTreeSet<i64>,
) -> Result<()> {
    let mut new_tags = BTreeSet::new();
    match value {
        Value::Null => {}
        Value::Array(a) => {
            for x in a {
                new_tags.insert(as_int(x)?);
            }
        }
        other => return Err(DbError::invalid(format!("tag property {pid} expects a list of tag ids, got {other}"))),
    }
    for tag_id in existing.difference(&new_tags) {
        let key = junction_key(tt, anchor, pid, *tag_id);
        add(ops, Some(PendingOp { et: tt, key, op: OP_DELETE, changes: None }));
    }
    for tag_id in new_tags.difference(existing) {
        let key = junction_key(tt, anchor, pid, *tag_id);
        add(ops, Some(PendingOp { et: tt, key, op: OP_CREATE, changes: None }));
    }
    Ok(())
}

fn delete_ops_for(tx: &Connection, et: EntityType, filter: &Filter) -> Result<Vec<PendingOp>> {
    let spec = et.spec();
    Ok(generic_get(tx, spec, filter, State::Alive)?
        .into_iter()
        .map(|r| PendingOp { et, key: r.key(spec), op: OP_DELETE, changes: None })
        .collect())
}

/// Cascade deletes (same commit, so undo restores the whole subtree).
fn cascade_delete_ops(tx: &Connection, prop_ids: &[i64], del_tag_ids: &[i64]) -> Result<Vec<PendingOp>> {
    let mut out = Vec::new();
    let mut tag_ids: Vec<i64> = del_tag_ids.to_vec();
    if !prop_ids.is_empty() {
        let props: Vec<Property> = schema::get(tx, &Filter::new().is_in("id", prop_ids.iter().copied()), State::Alive)?;
        let tag_props: Vec<i64> = props.iter().filter(|p| is_tag_dtype(p.dtype.as_deref())).map(|p| p.id).collect();
        let non_tag: Vec<i64> = props.iter().filter(|p| !is_tag_dtype(p.dtype.as_deref())).map(|p| p.id).collect();
        let list_ids: Vec<i64> =
            props.iter().filter(|p| is_tag_dtype(p.dtype.as_deref())).filter_map(|p| p.tag_list_id).collect();
        if !non_tag.is_empty() {
            let f = Filter::new().is_in("property_id", non_tag.iter().copied());
            out.extend(delete_ops_for(tx, EntityType::InstanceValue, &f)?);
            out.extend(delete_ops_for(tx, EntityType::Sha1Value, &f)?);
            out.extend(delete_ops_for(tx, EntityType::FileValue, &f)?);
        }
        if !tag_props.is_empty() {
            let f = Filter::new().is_in("property_id", tag_props.iter().copied());
            out.extend(delete_ops_for(tx, EntityType::InstanceTagValue, &f)?);
            out.extend(delete_ops_for(tx, EntityType::Sha1TagValue, &f)?);
        }
        if !list_ids.is_empty() {
            let tags: Vec<Tag> = schema::get(tx, &Filter::new().is_in("list_id", list_ids.iter().copied()), State::Alive)?;
            for t in tags {
                out.push(PendingOp { et: EntityType::Tag, key: encode_key(&[Value::from(t.id)]), op: OP_DELETE, changes: None });
                tag_ids.push(t.id);
            }
        }
    }
    if !tag_ids.is_empty() {
        let f = Filter::new().is_in("tag_id", tag_ids.iter().copied());
        out.extend(delete_ops_for(tx, EntityType::InstanceTagValue, &f)?);
        out.extend(delete_ops_for(tx, EntityType::Sha1TagValue, &f)?);
    }
    Ok(out)
}

/// `_dtype_map`: dtype of every property a value write targets (+ properties created by the
/// same commit).
fn dtype_map(tx: &Connection, data: &DataCommit) -> Result<HashMap<i64, Option<String>>> {
    let mut pids: IndexSet<i64> = IndexSet::new();
    pids.extend(data.instance_values.iter().map(|v| v.property_id));
    pids.extend(data.sha1_values.iter().map(|v| v.property_id));
    pids.extend(data.file_values.iter().map(|v| v.property_id));
    let mut out: HashMap<i64, Option<String>> = HashMap::new();
    if !pids.is_empty() {
        let props: Vec<Property> = schema::get(tx, &Filter::new().is_in("id", pids.iter().copied()), State::Alive)?;
        for p in props {
            out.insert(p.id, p.dtype);
        }
    }
    for p in &data.properties {
        if p.dtype.is_some() {
            out.insert(p.id, p.dtype.clone());
        }
    }
    Ok(out)
}

// ======================================================================
// Materialization
// ======================================================================

fn materialize_many(tx: &Connection, touched: &[(EntityType, String)], seq: i64) -> Result<()> {
    let mut by_type: IndexMap<EntityType, IndexSet<String>> = IndexMap::new();
    for (et, key) in touched {
        by_type.entry(*et).or_default().insert(key.clone());
    }
    for (et, keys) in &by_type {
        let spec = et.spec();
        let keys: Vec<String> = keys.iter().cloned().collect();
        let ops = enabled_ops_many(tx, *et, &keys)?;
        let mut resolved: IndexMap<String, Option<GenericRow>> = IndexMap::with_capacity(keys.len());
        for k in keys {
            let r = resolve(spec, &k, ops.get(&k).map(Vec::as_slice).unwrap_or(&[]))?;
            resolved.insert(k, r);
        }
        write_results(tx, spec, &resolved, seq)?;
    }
    let (losers, winners) = mono_tag_arity(tx, touched, None)?;
    let mut fixes: IndexMap<EntityType, IndexMap<String, Option<GenericRow>>> = IndexMap::new();
    for (et, key) in losers {
        fixes.entry(et).or_default().insert(key, None);
    }
    for ((et, key), row) in winners {
        fixes.entry(et).or_default().insert(key, Some(row));
    }
    for (et, resolved) in &fixes {
        write_results(tx, et.spec(), resolved, seq)?;
    }
    Ok(())
}

/// Upsert resolved entities of one type; a fresh sequence is written only when the state
/// changes; a resolved `None` tombstones a live row (keeping its last values).
fn write_results(tx: &Connection, spec: &EntitySpec, resolved: &IndexMap<String, Option<GenericRow>>, seq: i64) -> Result<()> {
    let keys: Vec<&String> = resolved.keys().collect();
    for chunk in keys.chunks(MAX_VARS) {
        let owned: Vec<String> = chunk.iter().map(|k| (*k).clone()).collect();
        let current = current_rows(tx, spec, &owned)?;
        let mut rows: Vec<Vec<SqlValue>> = Vec::new();
        for key in chunk {
            if let Some(row) = result_change(spec, current.get(*key), resolved[*key].as_ref())? {
                rows.push(row.to_sql(spec));
            }
        }
        schema::upsert_raw(tx, spec.table, &rows, Some(seq))?;
    }
    Ok(())
}

fn result_change(spec: &EntitySpec, current: Option<&GenericRow>, resolved: Option<&GenericRow>) -> Result<Option<GenericRow>> {
    match resolved {
        None => Ok(match current {
            Some(cur) if cur.operation != Some(OP_DELETE) => {
                let mut t = cur.clone();
                t.operation = Some(OP_DELETE);
                Some(t)
            }
            _ => None,
        }),
        Some(res) => {
            if let Some(cur) = current {
                if same_state(spec, cur, res)? {
                    return Ok(None);
                }
            }
            Ok(Some(res.clone()))
        }
    }
}

type Losers = IndexSet<(EntityType, String)>;
type Winners = IndexMap<(EntityType, String), GenericRow>;

/// `_mono_tag_arity`: elect the single surviving tag of every mono-tag (`dtype == "tag"`) cell
/// hit by `touched`: the newest enabled commit wins, tag id breaks ties.
fn mono_tag_arity(tx: &Connection, touched: &[(EntityType, String)], up_to: Option<i64>) -> Result<(Losers, Winners)> {
    let mut losers: Losers = IndexSet::new();
    let mut winners: Winners = IndexMap::new();
    for ((et, _, _), keys) in mono_tag_cells(tx, touched)? {
        let spec = et.spec();
        let mut alive: Vec<(String, GenericRow)> = Vec::new();
        for key in keys {
            if let Some(r) = resolve(spec, &key, &enabled_ops(tx, et, &key, up_to)?)? {
                alive.push((key, r));
            }
        }
        if alive.is_empty() {
            continue;
        }
        let mut best: Option<(i64, i64, usize)> = None;
        for (i, (key, r)) in alive.iter().enumerate() {
            let commit = r.commit_id.unwrap_or(i64::MIN);
            let tag_id = decode_key(key)?.last().map(as_int).transpose()?.unwrap_or(i64::MIN);
            if best.is_none_or(|(c, t, _)| (commit, tag_id) > (c, t)) {
                best = Some((commit, tag_id, i));
            }
        }
        let (_, _, wi) = best.expect("non-empty");
        for (i, (key, r)) in alive.into_iter().enumerate() {
            if i == wi {
                winners.insert((et, key), r);
            } else {
                losers.insert((et, key));
            }
        }
    }
    Ok((losers, winners))
}

/// `_mono_tag_cells`: each mono-tag cell hit by `touched` → every junction key known for it
/// (result rows, tombstones included, + the touched keys).
fn mono_tag_cells(tx: &Connection, touched: &[(EntityType, String)]) -> Result<IndexMap<(EntityType, String, i64), IndexSet<String>>> {
    let mut cells: IndexMap<(EntityType, String, i64), (Value, IndexSet<String>)> = IndexMap::new();
    for (et, key) in touched {
        let Some(anchor_field) = et.tag_anchor() else { continue };
        let spec = et.spec();
        let pk = decode_key(key)?;
        let get = |f: &str| spec.pk_fields.iter().position(|x| *x == f).and_then(|i| pk.get(i)).cloned().unwrap_or(Value::Null);
        let anchor = get(anchor_field);
        let pid = as_int(&get("property_id"))?;
        let e = cells.entry((*et, pyjson::dumps_compact(&anchor), pid)).or_insert_with(|| (anchor, IndexSet::new()));
        e.1.insert(key.clone());
    }
    let mut out = IndexMap::new();
    if cells.is_empty() {
        return Ok(out);
    }
    let pids: IndexSet<i64> = cells.keys().map(|(_, _, p)| *p).collect();
    let props: HashMap<i64, Property> = schema::get::<Property>(tx, &Filter::new().is_in("id", pids.iter().copied()), State::Alive)?
        .into_iter()
        .map(|p| (p.id, p))
        .collect();
    for ((et, anchor_key, pid), (anchor, mut keys)) in cells {
        match props.get(&pid) {
            Some(p) if p.dtype.as_deref() == Some(TAG_DTYPE) => {}
            _ => continue,
        }
        let spec = et.spec();
        let anchor_field = et.tag_anchor().expect("junction type");
        let f = Filter::new().eq(anchor_field, key_part_sql(&anchor)).eq("property_id", pid);
        for r in generic_get(tx, spec, &f, State::Any)? {
            keys.insert(r.key(spec));
        }
        out.insert((et, anchor_key, pid), keys);
    }
    Ok(out)
}

// ======================================================================
// Undo / redo / compaction
// ======================================================================

fn set_commit_active_tx(tx: &Connection, commit_id: i64, active: bool) -> Result<Option<Commit>> {
    let rows: Vec<Commit> = schema::get(tx, &Filter::new().eq("id", commit_id), State::Any)?;
    let Some(mut commit) = rows.into_iter().next() else {
        return Ok(None);
    };
    let seq = next_sequence(tx)?;
    // Disabling puts the commit back on its author's redo stack.
    let redoable = if active { commit.redoable } else { Some(1) };
    tx.execute(
        "UPDATE commits SET active = ?, redoable = ? WHERE id = ?",
        rusqlite::params![active as i64, redoable, commit_id],
    )?;
    let touched = touched_by_commit(tx, commit_id)?;
    materialize_many(tx, &touched, seq)?;
    for (et, key) in &touched {
        if *et == EntityType::Tag {
            // Re-ship the value cells holding this tag on the next delta (their junction rows
            // live under other commits and did not change).
            let tag_id = decode_key(key)?.first().map(as_int).transpose()?.unwrap_or_default();
            tx.execute("UPDATE instance_tag_values SET sequence = ? WHERE tag_id = ?", [seq, tag_id])?;
            tx.execute("UPDATE sha1_tag_values SET sequence = ? WHERE tag_id = ?", [seq, tag_id])?;
        }
    }
    commit.active = active as i64;
    commit.redoable = redoable;
    Ok(Some(commit))
}

fn compact_tx(tx: &Connection, horizon: i64) -> Result<()> {
    let seq = next_sequence(tx)?;
    let mut touched: Vec<(EntityType, String)> = Vec::new();
    {
        let mut stmt = tx.prepare_cached(
            "SELECT DISTINCT entity_type, entity_key FROM entity_log WHERE commit_id > ? AND commit_id <= ?",
        )?;
        let mut rows = stmt.query([GENESIS_COMMIT_ID, horizon])?;
        while let Some(r) = rows.next()? {
            let et: String = r.get(0)?;
            let et = EntityType::parse(&et).ok_or_else(|| DbError::invalid(format!("unknown entity_type {et:?}")))?;
            touched.push((et, r.get(1)?));
        }
    }
    // Elect mono-tag winners before the fold: the losers must be physically dropped here.
    let (losers, _) = mono_tag_arity(tx, &touched, Some(horizon))?;
    for (et, key) in &touched {
        let spec = et.spec();
        let mut resolved = resolve(spec, key, &enabled_ops(tx, *et, key, Some(horizon))?)?;
        if losers.contains(&(*et, key.clone())) {
            resolved = None;
        }
        tx.execute(
            "DELETE FROM entity_log WHERE entity_type = ? AND entity_key = ? AND commit_id <= ?",
            rusqlite::params![et.as_str(), key, horizon],
        )?;
        let Some(resolved) = resolved else {
            // Dead at the baseline: drop the genesis op and GC the result row.
            schema::delete_by_pk(tx, spec.table, &[key_to_pk_sql(key)?])?;
            continue;
        };
        let changes = snapshot_changes(spec, &resolved)?.map(|c| pyjson::dumps(&Value::Object(c)));
        tx.execute(
            "INSERT OR REPLACE INTO entity_log (entity_type, entity_key, commit_id, op, changes, sequence) VALUES (?,?,?,?,?,?)",
            rusqlite::params![et.as_str(), key, GENESIS_COMMIT_ID, OP_CREATE, changes, seq],
        )?;
    }
    tx.execute("DELETE FROM commits WHERE id > ? AND id <= ?", [GENESIS_COMMIT_ID, horizon])?;
    Ok(())
}

// ======================================================================
// Structural deletes (+ orphan GC of value rows and their log ops)
// ======================================================================

fn ids_sql(ids: &[i64]) -> Vec<Vec<SqlValue>> {
    ids.iter().map(|i| vec![SqlValue::Integer(*i)]).collect()
}

fn delete_instances_tx(tx: &Connection, ids: &[i64]) -> Result<OrphanReport> {
    if ids.is_empty() {
        return Ok(OrphanReport::default());
    }
    let rows = schema::select(tx, &INSTANCES, &["sha1", "file_id"], &Filter::new().is_in("id", ids.iter().copied()))?;
    let mut cand_sha1s: IndexSet<String> = IndexSet::new();
    let mut cand_files: IndexSet<i64> = IndexSet::new();
    for r in rows {
        if let SqlValue::Text(s) = &r[0] {
            if !s.is_empty() {
                cand_sha1s.insert(s.clone());
            }
        }
        if let SqlValue::Integer(f) = r[1] {
            cand_files.insert(f);
        }
    }
    let idv: Vec<Value> = ids.iter().map(|i| Value::from(*i)).collect();
    purge_value_rows(tx, EntityType::InstanceValue, "instance_id", &idv)?;
    purge_value_rows(tx, EntityType::InstanceTagValue, "instance_id", &idv)?;
    schema::delete_by_pk(tx, &INSTANCES, &ids_sql(ids))?;
    gc_orphans(tx, cand_sha1s, cand_files)
}

fn delete_files_tx(tx: &Connection, file_ids: &[i64]) -> Result<OrphanReport> {
    if file_ids.is_empty() {
        return Ok(OrphanReport::default());
    }
    let inst: Vec<i64> = schema::select(tx, &INSTANCES, &["id"], &Filter::new().is_in("file_id", file_ids.iter().copied()))?
        .into_iter()
        .filter_map(|r| int_of(&r[0]))
        .collect();
    let report = delete_instances_tx(tx, &inst)?;
    let fv: Vec<Value> = file_ids.iter().map(|i| Value::from(*i)).collect();
    purge_value_rows(tx, EntityType::FileValue, "file_id", &fv)?;
    schema::delete_by_pk(tx, &FILES, &ids_sql(file_ids))?;
    Ok(report)
}

fn delete_folders_tx(tx: &Connection, folder_ids: &[i64]) -> Result<OrphanReport> {
    if folder_ids.is_empty() {
        return Ok(OrphanReport::default());
    }
    // descendants (BFS over `parent`)
    let mut seen: IndexSet<i64> = folder_ids.iter().copied().collect();
    let mut frontier: Vec<i64> = folder_ids.to_vec();
    while !frontier.is_empty() {
        let children: Vec<i64> = schema::select(tx, &FOLDERS, &["id"], &Filter::new().is_in("parent", frontier.iter().copied()))?
            .into_iter()
            .filter_map(|r| int_of(&r[0]))
            .collect();
        frontier = children.into_iter().filter(|c| !seen.contains(c)).collect();
        seen.extend(frontier.iter().copied());
    }
    let all: Vec<i64> = seen.into_iter().collect();
    let files: Vec<i64> = schema::select(tx, &FILES, &["id"], &Filter::new().is_in("folder_id", all.iter().copied()))?
        .into_iter()
        .filter_map(|r| int_of(&r[0]))
        .collect();
    let report = delete_files_tx(tx, &files)?;
    schema::delete_by_pk(tx, &FOLDERS, &ids_sql(&all))?;
    Ok(report)
}

fn gc_orphans(tx: &Connection, cand_sha1s: IndexSet<String>, cand_files: IndexSet<i64>) -> Result<OrphanReport> {
    let mut sha1_stmt = tx.prepare_cached("SELECT 1 FROM instances WHERE sha1 = ? LIMIT 1")?;
    let mut orphan_sha1s: Vec<String> = Vec::new();
    for s in cand_sha1s {
        if !sha1_stmt.exists([&s])? {
            orphan_sha1s.push(s);
        }
    }
    drop(sha1_stmt);
    let mut file_stmt = tx.prepare_cached("SELECT 1 FROM instances WHERE file_id = ? LIMIT 1")?;
    let mut orphan_files: Vec<i64> = Vec::new();
    for f in cand_files {
        if !file_stmt.exists([f])? {
            orphan_files.push(f);
        }
    }
    drop(file_stmt);
    orphan_sha1s.sort();
    orphan_files.sort();
    if !orphan_sha1s.is_empty() {
        let v: Vec<Value> = orphan_sha1s.iter().map(|s| Value::from(s.clone())).collect();
        purge_value_rows(tx, EntityType::Sha1Value, "sha1", &v)?;
        purge_value_rows(tx, EntityType::Sha1TagValue, "sha1", &v)?;
    }
    if !orphan_files.is_empty() {
        let v: Vec<Value> = orphan_files.iter().map(|f| Value::from(*f)).collect();
        purge_value_rows(tx, EntityType::FileValue, "file_id", &v)?;
        schema::delete_by_pk(tx, &FILES, &ids_sql(&orphan_files))?;
    }
    Ok(OrphanReport { orphan_sha1s, orphan_file_ids: orphan_files })
}

/// Hard-delete value / junction result rows with `col IN values`, plus their `entity_log` ops
/// (structural GC — never undone).
fn purge_value_rows(tx: &Connection, et: EntityType, col: &str, values: &[Value]) -> Result<()> {
    if values.is_empty() {
        return Ok(());
    }
    let spec = et.spec();
    let pk_cols = spec.pk_fields.join(", ");
    let mut keys: Vec<String> = Vec::new();
    for chunk in values.chunks(MAX_VARS) {
        let sql = format!("SELECT {pk_cols} FROM {} WHERE {col} IN ({})", spec.table.name, vec!["?"; chunk.len()].join(", "));
        let params: Vec<SqlValue> = chunk.iter().map(key_part_sql).collect();
        let mut stmt = tx.prepare_cached(&sql)?;
        let mut rows = stmt.query(params_from_iter(params.iter()))?;
        while let Some(r) = rows.next()? {
            let pk: Vec<Value> = (0..spec.pk_fields.len()).map(|i| r.get_ref(i).map(crate::schema::sql_to_plain)).collect::<rusqlite::Result<_>>()?;
            keys.push(encode_key(&pk));
        }
    }
    for chunk in values.chunks(MAX_VARS) {
        let sql = format!("DELETE FROM {} WHERE {col} IN ({})", spec.table.name, vec!["?"; chunk.len()].join(", "));
        let params: Vec<SqlValue> = chunk.iter().map(key_part_sql).collect();
        tx.prepare_cached(&sql)?.execute(params_from_iter(params.iter()))?;
    }
    for chunk in keys.chunks(MAX_VARS - 1) {
        let sql = format!(
            "DELETE FROM entity_log WHERE entity_type = ? AND entity_key IN ({})",
            vec!["?"; chunk.len()].join(", ")
        );
        let mut params: Vec<&str> = vec![et.as_str()];
        params.extend(chunk.iter().map(String::as_str));
        tx.prepare_cached(&sql)?.execute(params_from_iter(params))?;
    }
    Ok(())
}

// Keep Entity in scope for generic calls above.
#[allow(dead_code)]
fn _assert_entity<T: Entity>() {}
