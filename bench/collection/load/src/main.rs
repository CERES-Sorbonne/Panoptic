//! Column load benchmark — Rust side. Loads full property columns from a `data.db` (Python
//! schema) into a prototype column store (`store.rs`, with `js.rs` and `schema.rs`: the first
//! engine draft, kept here only as the measured loader).
//!
//!   load-bench --make-db=<data.db> --n=1000000   fill a schema-only data.db with the synthetic set
//!   load-bench --db=<data.db>                    time every load, print JSONL
//!   load-bench --db=<data.db> --cold=<dir>       cold loads: rows vs column blob (cache.rs)
//!
//! Per column, three variants:
//! - `sqlite`: the query alone, each row stepped and its value bytes touched (the floor).
//! - `typed`: query → typed column built directly (numbers parsed in place, strings interned
//!   without an intermediate `serde_json::Value`, tags counting-sorted into CSR) → `SetColumn`.
//!   What an initial load would do.
//! - `generic`: query → `serde_json::Value` → `CellValue::from_json` per cell → `SetValues`. The
//!   engine's delta path, as it exists today.
//!
//! The identity (`instances`) is timed the same way, as `op = "base"`. Every column is checked
//! against the generated data (`count` / `hash`), and `typed` and `generic` must agree.

#[path = "../../rust/src/data.rs"]
#[allow(dead_code)]
mod data;
#[allow(dead_code)]
mod js;
#[allow(dead_code)]
mod schema;
#[allow(dead_code)]
mod store;

mod cache;
mod make_db;

use std::hash::{Hash, Hasher};
use std::sync::Arc;
use std::time::Instant;

use rusqlite::{Connection, OpenFlags, types::ValueRef};
use rustc_hash::FxHasher;

use schema::{ColumnKind, PropertyDef, PropertyType, Schema, TagDef};
use store::{CellValue, Column, Delta, Snapshot, StrColumn, StrDict, TagColumn, ValueKeys, build};

const OP_CREATE: i64 = 1;

fn arg(name: &str) -> Option<String> {
    let p = format!("--{name}=");
    std::env::args().find_map(|a| a.strip_prefix(&p).map(str::to_string))
}

fn time(reps: usize, mut f: impl FnMut()) -> (f64, f64, usize) {
    f(); // warmup: pages the table into the OS cache, like every later load of a running app
    let mut times: Vec<f64> = (0..reps)
        .map(|_| {
            let t0 = Instant::now();
            f();
            t0.elapsed().as_secs_f64() * 1000.0
        })
        .collect();
    times.sort_by(|a, b| a.partial_cmp(b).unwrap());
    (times[times.len() / 2], times[0], times.len())
}

/// A long-lived read connection, with the pragmas of the Python `SQLiteReader`.
fn open(path: &str) -> Connection {
    let c = Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX).unwrap();
    c.execute_batch("PRAGMA cache_size = -100000; PRAGMA temp_store = MEMORY; PRAGMA mmap_size = 30000000000;").unwrap();
    c
}

// ── schema + identity ──────────────────────────────────────────────────────────

fn load_schema(c: &Connection) -> Schema {
    let mut st = c.prepare("SELECT id, dtype, mode, name, system_key, tag_list_id FROM properties WHERE operation = ?").unwrap();
    let rows: Vec<(PropertyDef, Option<i64>)> = st
        .query_map([OP_CREATE], |r| {
            let def = serde_json::json!({
                "id": r.get::<_, i64>(0)?, "dtype": r.get::<_, Option<String>>(1)?,
                "mode": r.get::<_, Option<String>>(2)?.unwrap_or_else(|| "id".into()),
                "name": r.get::<_, Option<String>>(3)?.unwrap_or_default(), "systemKey": r.get::<_, Option<String>>(4)?,
            });
            Ok((serde_json::from_value(def).unwrap(), r.get::<_, Option<i64>>(5)?))
        })
        .unwrap()
        .map(Result::unwrap)
        .collect();
    let mut st = c.prepare("SELECT id, list_id, parents, value, color FROM tags WHERE operation = ?").unwrap();
    let tags: Vec<TagDef> = st
        .query_map([OP_CREATE], |r| {
            let list: Option<i64> = r.get(1)?;
            let prop = rows.iter().find(|(_, l)| *l == list && list.is_some()).map(|(p, _)| p.id).unwrap_or(0);
            let parents: Option<String> = r.get(2)?;
            Ok(TagDef {
                id: r.get(0)?,
                property_id: prop,
                value: r.get::<_, Option<String>>(3)?.unwrap_or_default(),
                parents: parents.and_then(|p| serde_json::from_str(&p).ok()).unwrap_or_default(),
                color: r.get(4)?,
                deleted: false,
            })
        })
        .unwrap()
        .map(Result::unwrap)
        .collect();
    Schema::new(rows.into_iter().map(|(p, _)| p), tags, [])
}

fn load_base(c: &Connection, schema: &Arc<Schema>) -> Snapshot {
    let mut st = c.prepare_cached("SELECT id, sha1, file_id FROM instances").unwrap();
    let (mut ids, mut sha1s, mut file_ids) = (Vec::new(), Vec::new(), Vec::new());
    let mut rows = st.query([]).unwrap();
    while let Some(r) = rows.next().unwrap() {
        ids.push(r.get::<_, i32>(0).unwrap());
        sha1s.push(r.get::<_, Option<String>>(1).unwrap());
        file_ids.push(r.get::<_, Option<i32>>(2).unwrap().unwrap_or(0));
    }
    build::snapshot(schema.clone(), ids, sha1s, file_ids, 1)
}

// ── columns ────────────────────────────────────────────────────────────────────

fn value_sql(p: &PropertyDef) -> &'static str {
    if p.ptype.is_tag() {
        "SELECT instance_id, tag_id FROM instance_tag_values WHERE property_id = ?1 AND operation = 1"
    } else {
        "SELECT instance_id, value FROM instance_values WHERE property_id = ?1"
    }
}

/// The query alone: rows stepped, value bytes touched.
fn scan(c: &Connection, p: &PropertyDef) -> (usize, u64) {
    let mut st = c.prepare_cached(value_sql(p)).unwrap();
    let mut rows = st.query([p.id]).unwrap();
    let (mut count, mut sink) = (0usize, 0u64);
    while let Some(r) = rows.next().unwrap() {
        sink = sink.wrapping_add(r.get_ref(0).unwrap().as_i64().unwrap() as u64);
        sink = sink.wrapping_add(match r.get_ref(1).unwrap() {
            ValueRef::Text(t) => t.len() as u64,
            ValueRef::Integer(i) => i as u64,
            _ => 0,
        });
        count += 1;
    }
    (count, sink)
}

/// A stored cell through the generic path: SQLite value → `serde_json::Value` → `CellValue`.
/// The `value` column is declared JSON, which SQLite gives NUMERIC affinity: numbers come back
/// as INTEGER / REAL, everything else as JSON text. None = no value.
fn generic_cell(ptype: PropertyType, v: ValueRef<'_>) -> Option<CellValue> {
    let j = match v {
        ValueRef::Integer(i) => serde_json::Value::from(i),
        ValueRef::Real(x) => serde_json::Value::from(x),
        ValueRef::Text(t) => serde_json::from_slice(t).unwrap_or(serde_json::Value::Null),
        ValueRef::Null | ValueRef::Blob(_) => return None,
    };
    Some(CellValue::from_json(ptype, &j))
}

/// The JSON string literal's content when it holds no escape: the common case, no allocation.
#[inline]
fn plain_json_str(t: &str) -> Option<&str> {
    let b = t.as_bytes();
    (b.len() >= 2 && b[0] == b'"' && b[b.len() - 1] == b'"' && !b.contains(&b'\\')).then(|| &t[1..t.len() - 1])
}

fn load_typed(c: &Connection, snap: &Snapshot, p: &PropertyDef) -> Column {
    let n = snap.len();
    let slot_of = &snap.identity.slot_of;
    let mut st = c.prepare_cached(value_sql(p)).unwrap();
    let mut rows = st.query([p.id]).unwrap();
    macro_rules! each_row {
        (|$slot:ident, $v:ident| $body:block) => {
            while let Some(r) = rows.next().unwrap() {
                let id = r.get_ref(0).unwrap().as_i64().unwrap() as i32;
                let Some(&$slot) = slot_of.get(&id) else { continue };
                let $v = r.get_ref(1).unwrap();
                $body
            }
        };
    }
    match p.ptype.kind() {
        ColumnKind::Num => {
            let mut d = vec![f64::NAN; n];
            let date = p.ptype == PropertyType::Date;
            each_row!(|slot, v| {
                d[slot as usize] = match v {
                    ValueRef::Integer(i) => i as f64,
                    ValueRef::Real(x) => x,
                    ValueRef::Text(t) => match std::str::from_utf8(t).ok().and_then(plain_json_str) {
                        Some(s) if date => js::parse_date(s),
                        _ => match generic_cell(p.ptype, v) {
                            Some(CellValue::Num(x)) => x,
                            Some(CellValue::Bool(b)) => b as i32 as f64,
                            _ => f64::NAN,
                        },
                    },
                    _ => continue,
                };
            });
            Column::Num(Arc::new(d))
        }
        ColumnKind::Bool => {
            let mut d = vec![255u8; n];
            each_row!(|slot, v| {
                d[slot as usize] = match v {
                    ValueRef::Text(b"true") => 1,
                    ValueRef::Text(b"false") => 0,
                    _ => match generic_cell(p.ptype, v) {
                        Some(CellValue::Bool(b)) => b as u8,
                        _ => continue,
                    },
                };
            });
            Column::Bool(Arc::new(d))
        }
        ColumnKind::Str => {
            let mut codes = vec![0u32; n];
            let mut dict = StrDict::new();
            each_row!(|slot, v| {
                let plain = match v {
                    ValueRef::Text(t) => std::str::from_utf8(t).ok().and_then(plain_json_str),
                    _ => None,
                };
                codes[slot as usize] = match plain {
                    Some(s) => dict.intern(s),
                    None => match generic_cell(p.ptype, v) {
                        Some(CellValue::Str(s)) => dict.intern(&s),
                        _ => continue,
                    },
                };
            });
            Column::Str(Arc::new(StrColumn { codes, dict: Arc::new(dict) }))
        }
        ColumnKind::Tags => {
            // Counting sort of (slot, tag) into CSR: no assumption on the row order.
            let mut pairs: Vec<(u32, i32)> = Vec::new();
            each_row!(|slot, v| {
                pairs.push((slot, v.as_i64().unwrap() as i32));
            });
            let mut offsets = vec![0u32; n + 1];
            for &(s, _) in &pairs {
                offsets[s as usize + 1] += 1;
            }
            for i in 0..n {
                offsets[i + 1] += offsets[i];
            }
            let mut fill = offsets.clone();
            let mut values = vec![0i32; pairs.len()];
            for &(s, t) in &pairs {
                values[fill[s as usize] as usize] = t;
                fill[s as usize] += 1;
            }
            Column::Tags(Arc::new(TagColumn { offsets, values }))
        }
    }
}

fn load_generic(c: &Connection, p: &PropertyDef) -> Delta {
    let mut st = c.prepare_cached(value_sql(p)).unwrap();
    let mut rows = st.query([p.id]).unwrap();
    let (mut ids, mut values) = (Vec::new(), Vec::new());
    if p.ptype.is_tag() {
        let mut by_id: rustc_hash::FxHashMap<i32, Vec<i32>> = Default::default();
        while let Some(r) = rows.next().unwrap() {
            by_id.entry(r.get(0).unwrap()).or_default().push(r.get(1).unwrap());
        }
        for (id, tags) in by_id {
            ids.push(id);
            values.push(CellValue::Tags(tags));
        }
    } else {
        while let Some(r) = rows.next().unwrap() {
            let Some(v) = generic_cell(p.ptype, r.get_ref(1).unwrap()) else { continue };
            ids.push(r.get(0).unwrap());
            values.push(v);
        }
    }
    Delta::SetValues { property_id: p.id, keys: ValueKeys::Instances(ids), values }
}

// ── checks ─────────────────────────────────────────────────────────────────────

/// (non-empty cells, order-independent hash) of a column as the engine reads it.
fn digest(snap: &Snapshot, prop: i64) -> (usize, u64) {
    let (mut count, mut acc) = (0usize, 0u64);
    for s in 0..snap.len() as u32 {
        let mut h = FxHasher::default();
        s.hash(&mut h);
        match snap.col(prop).read(s) {
            js::Jv::Num(x) => x.to_bits().hash(&mut h),
            js::Jv::Bool(b) => b.hash(&mut h),
            js::Jv::Str(x) => x.hash(&mut h),
            js::Jv::Tags(t) => {
                let mut t = t.to_vec();
                t.sort_unstable();
                t.hash(&mut h)
            }
            _ => continue,
        }
        count += 1;
        acc = acc.wrapping_add(h.finish());
    }
    (count, acc)
}

/// The same digest computed from the generated data.
fn expected(d: &data::Data, name: &str) -> (usize, u64) {
    let (mut count, mut acc) = (0usize, 0u64);
    for s in 0..d.number.len() {
        let mut h = FxHasher::default();
        (s as u32).hash(&mut h);
        let ok = match name {
            "text" | "label" => {
                let c = if name == "text" { &d.text } else { &d.label };
                let code = c.codes[s];
                (code != 0).then(|| (*c.dict[code as usize]).hash(&mut h)).is_some()
            }
            "number" | "score" | "date" => {
                let x = match name {
                    "number" => d.number[s],
                    "score" => d.score[s],
                    _ => d.date[s],
                };
                (!x.is_nan()).then(|| x.to_bits().hash(&mut h)).is_some()
            }
            "checkbox" => (d.check[s] != 255).then(|| (d.check[s] == 1).hash(&mut h)).is_some(),
            _ => {
                let mut t: Vec<i32> = d.tags.get(s as u32).iter().map(|&x| x as i32).collect();
                t.sort_unstable();
                (!t.is_empty()).then(|| t.hash(&mut h)).is_some()
            }
        };
        if ok {
            count += 1;
            acc = acc.wrapping_add(h.finish());
        }
    }
    (count, acc)
}

// ── main ───────────────────────────────────────────────────────────────────────

fn main() {
    if let Some(path) = arg("make-db") {
        let n: usize = arg("n").map(|x| x.parse().unwrap()).unwrap_or(1_000_000);
        make_db::fill(&path, n);
        return;
    }
    let path = arg("db").expect("--db=<data.db> or --make-db=<data.db>");
    if let Some(dir) = arg("cold") {
        cache::run_cold(&path, &dir);
        return;
    }
    let c = open(&path);
    let n: usize = c.query_row("SELECT COUNT(*) FROM instances", [], |r| r.get(0)).unwrap();
    let reps: usize = arg("reps").map(|x| x.parse().unwrap()).unwrap_or(if n >= 5_000_000 { 3 } else { 5 });
    let only = arg("only");
    let check = arg("check").is_none_or(|x| x != "0");
    let emit = |op: &str, variant: &str, (ms, min_ms, reps): (f64, f64, usize), extra: &str| {
        println!(
            r#"{{"impl":"rust","kind":"load","n":{n},"op":"{op}","variant":"{variant}","ms":{ms:.3},"min_ms":{min_ms:.3},"reps":{reps}{extra}}}"#
        );
    };

    let schema = Arc::new(load_schema(&c));
    emit("schema", "typed", time(reps, || drop(load_schema(&c))), "");
    let mut base = None;
    let t = time(reps, || base = Some(load_base(&c, &schema)));
    let base = base.unwrap();
    emit("base", "typed", t, &format!(r#","count":{}"#, base.len()));
    let t = time(reps, || {
        let mut st = c.prepare_cached("SELECT id, sha1, file_id FROM instances").unwrap();
        let mut rows = st.query([]).unwrap();
        while let Some(r) = rows.next().unwrap() {
            std::hint::black_box((r.get_ref(0).unwrap(), r.get_ref(1).unwrap(), r.get_ref(2).unwrap()));
        }
    });
    emit("base", "sqlite", t, &format!(r#","count":{}"#, base.len()));

    let d = check.then(|| data::generate(n));
    let props: Vec<PropertyDef> = schema.properties.values().filter(|p| p.system_key.is_none()).cloned().collect();
    for p in &props {
        if only.as_deref().is_some_and(|o| !p.name.contains(o)) {
            continue;
        }
        let mut sc = (0, 0);
        let t = time(reps, || sc = std::hint::black_box(scan(&c, p)));
        emit(&p.name, "sqlite", t, &format!(r#","rows":{}"#, sc.0));

        let mut typed = base.clone();
        let t = time(reps, || {
            let col = load_typed(&c, &base, p);
            typed = base.apply(&[Delta::SetColumn { property_id: p.id, column: col }]).0;
        });
        let dt = digest(&typed, p.id);
        emit(&p.name, "typed", t, &format!(r#","rows":{},"count":{},"hash":"{:016x}""#, sc.0, dt.0, dt.1));

        let mut generic = base.clone();
        let t = time(reps, || generic = base.apply(&[load_generic(&c, p)]).0);
        let dg = digest(&generic, p.id);
        emit(&p.name, "generic", t, &format!(r#","rows":{},"count":{},"hash":"{:016x}""#, sc.0, dg.0, dg.1));

        assert_eq!(dt, dg, "{}: typed and generic loads differ", p.name);
        if let Some(d) = &d {
            assert_eq!(dt, expected(d, &p.name), "{}: loaded column differs from the generated data", p.name);
        }
    }
}
