//! Cost of recording deletes: tombstones kept inline, a separate tombstone table, or no
//! tombstones at all (a reader that misses a delete reloads the column).
//!
//!   tomb --n=1000000 --dead=0.1 --variant=inline --dir=<scratch dir>   one case, JSONL on stdout
//!
//! Variants (one value table, two properties: 1 = number, 2 = text, one cell per instance):
//! - `inline`: today's layout. Rowid table, composite PK, indexes on `sequence` and `operation`.
//!   A delete sets `operation = 3`; loads filter it out.
//! - `lean`: inline tombstones, WITHOUT ROWID, no `operation` index.
//! - `table`: hard delete from the value table plus a row in `tombstones`, table_id 1 (opti/03 §3).
//! - `full`: hard delete, no tombstones. A delete bumps the property's `column_version`; a reader
//!   that synced before it reloads the whole column.
//!
//! `--dead` is the share of cells that were cleared before the measures start, by real delete
//! commits, so the B-trees carry the fragmentation of churn. Each reader keeps a column and
//! is checked against a fresh load after every sync.

use std::collections::HashSet;
use std::hash::{Hash, Hasher};
use std::time::Instant;

use rusqlite::types::{Value, ValueRef};
use rusqlite::{Connection, params};
use rustc_hash::FxHasher;
use serde_json::json;

const DEL: i64 = 3;

#[derive(Clone, Copy, PartialEq)]
enum V {
    Inline,
    Lean,
    Table,
    Full,
}

fn arg(name: &str) -> Option<String> {
    let p = format!("--{name}=");
    std::env::args().find_map(|a| a.strip_prefix(&p).map(str::to_string))
}

struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }
    fn below(&mut self, n: usize) -> usize {
        (self.next() % n as u64) as usize
    }
}

fn value(prop: i64, rng: &mut Rng) -> Value {
    if prop == 1 {
        Value::Real((rng.next() % 1_000_000) as f64 / 100.0)
    } else {
        Value::Text(format!("word{} word{}", rng.next() % 5000, rng.next() % 5000))
    }
}

struct Db {
    c: Connection,
    v: V,
    seq: i64,
    /// Properties whose column_version must move at commit (`full`).
    dirty: HashSet<i64>,
}

impl Db {
    fn create(path: &str, v: V) -> Db {
        let _ = std::fs::remove_file(path);
        let _ = std::fs::remove_file(format!("{path}-wal"));
        let _ = std::fs::remove_file(format!("{path}-shm"));
        let c = Connection::open(path).unwrap();
        c.execute_batch(
            "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA page_size=8192;
             PRAGMA mmap_size=1073741824; PRAGMA temp_store=MEMORY;",
        )
        .unwrap();
        let ddl = match v {
            V::Inline => {
                "CREATE TABLE v (property_id INTEGER NOT NULL, instance_id INTEGER NOT NULL,
                   value ANY, operation INTEGER NOT NULL, sequence INTEGER NOT NULL,
                   PRIMARY KEY (property_id, instance_id));
                 CREATE INDEX v_seq ON v(sequence);
                 CREATE INDEX v_op ON v(operation);"
            }
            V::Lean => {
                "CREATE TABLE v (property_id INTEGER NOT NULL, instance_id INTEGER NOT NULL,
                   value ANY, operation INTEGER NOT NULL, sequence INTEGER NOT NULL,
                   PRIMARY KEY (property_id, instance_id)) STRICT, WITHOUT ROWID;
                 CREATE INDEX v_seq ON v(sequence);"
            }
            V::Table => {
                "CREATE TABLE v (property_id INTEGER NOT NULL, instance_id INTEGER NOT NULL,
                   value ANY NOT NULL, sequence INTEGER NOT NULL,
                   PRIMARY KEY (property_id, instance_id)) STRICT, WITHOUT ROWID;
                 CREATE INDEX v_seq ON v(sequence);
                 CREATE TABLE tombstones (table_id INTEGER NOT NULL, k1 INTEGER NOT NULL,
                   k2 INTEGER, k3 INTEGER, sequence INTEGER NOT NULL) STRICT;
                 CREATE INDEX tombstones_seq ON tombstones(sequence);"
            }
            V::Full => {
                "CREATE TABLE v (property_id INTEGER NOT NULL, instance_id INTEGER NOT NULL,
                   value ANY NOT NULL, sequence INTEGER NOT NULL,
                   PRIMARY KEY (property_id, instance_id)) STRICT, WITHOUT ROWID;
                 CREATE INDEX v_seq ON v(sequence);"
            }
        };
        c.execute_batch(ddl).unwrap();
        c.execute_batch(
            "CREATE TABLE props (id INTEGER PRIMARY KEY, column_version INTEGER NOT NULL);
             INSERT INTO props VALUES (1, 0), (2, 0);",
        )
        .unwrap();
        Db { c, v, seq: 0, dirty: HashSet::new() }
    }

    fn begin(&mut self) {
        self.c.execute_batch("BEGIN").unwrap();
        self.seq += 1;
    }

    fn commit(&mut self) {
        if self.v == V::Full {
            let mut st = self.c.prepare_cached("UPDATE props SET column_version = ? WHERE id = ?").unwrap();
            for p in self.dirty.drain() {
                st.execute(params![self.seq, p]).unwrap();
            }
        }
        self.c.execute_batch("COMMIT").unwrap();
    }

    fn set(&mut self, prop: i64, inst: i64, val: &Value) {
        let sql = match self.v {
            V::Inline | V::Lean => {
                "INSERT INTO v (property_id, instance_id, value, operation, sequence) VALUES (?1, ?2, ?3, 1, ?4)
                 ON CONFLICT (property_id, instance_id) DO UPDATE
                 SET value = excluded.value, operation = 1, sequence = excluded.sequence"
            }
            V::Table | V::Full => {
                "INSERT INTO v (property_id, instance_id, value, sequence) VALUES (?1, ?2, ?3, ?4)
                 ON CONFLICT (property_id, instance_id) DO UPDATE
                 SET value = excluded.value, sequence = excluded.sequence"
            }
        };
        self.c.prepare_cached(sql).unwrap().execute(params![prop, inst, val, self.seq]).unwrap();
    }

    fn del(&mut self, prop: i64, inst: i64) {
        match self.v {
            V::Inline | V::Lean => {
                self.c
                    .prepare_cached(
                        "UPDATE v SET operation = 3, sequence = ?1
                         WHERE property_id = ?2 AND instance_id = ?3 AND operation != 3",
                    )
                    .unwrap()
                    .execute(params![self.seq, prop, inst])
                    .unwrap();
            }
            V::Table => {
                let n = self
                    .c
                    .prepare_cached("DELETE FROM v WHERE property_id = ? AND instance_id = ?")
                    .unwrap()
                    .execute(params![prop, inst])
                    .unwrap();
                if n > 0 {
                    self.c
                        .prepare_cached("INSERT INTO tombstones VALUES (1, ?, ?, NULL, ?)")
                        .unwrap()
                        .execute(params![prop, inst, self.seq])
                        .unwrap();
                }
            }
            V::Full => {
                let n = self
                    .c
                    .prepare_cached("DELETE FROM v WHERE property_id = ? AND instance_id = ?")
                    .unwrap()
                    .execute(params![prop, inst])
                    .unwrap();
                if n > 0 {
                    self.dirty.insert(prop);
                }
            }
        }
    }

    /// Whole-column delete (property removed, plugin run undone).
    fn del_column(&mut self, prop: i64) {
        match self.v {
            V::Inline | V::Lean => {
                self.c
                    .execute(
                        "UPDATE v SET operation = 3, sequence = ? WHERE property_id = ? AND operation != 3",
                        params![self.seq, prop],
                    )
                    .unwrap();
            }
            V::Table => {
                self.c
                    .execute(
                        "INSERT INTO tombstones SELECT 1, property_id, instance_id, NULL, ?
                         FROM v WHERE property_id = ?",
                        params![self.seq, prop],
                    )
                    .unwrap();
                self.c.execute("DELETE FROM v WHERE property_id = ?", [prop]).unwrap();
            }
            V::Full => {
                self.c.execute("DELETE FROM v WHERE property_id = ?", [prop]).unwrap();
                self.dirty.insert(prop);
            }
        }
    }

    fn load_sql(&self) -> &'static str {
        match self.v {
            V::Inline | V::Lean => "SELECT instance_id, value FROM v WHERE property_id = ? AND operation != 3",
            V::Table | V::Full => "SELECT instance_id, value FROM v WHERE property_id = ?",
        }
    }

    /// Cold column load as the engine does it: one pass, no allocation per cell.
    fn scan(&self, prop: i64) -> (usize, u64) {
        let mut st = self.c.prepare_cached(self.load_sql()).unwrap();
        let mut rows = st.query([prop]).unwrap();
        let (mut n, mut h) = (0usize, 0u64);
        while let Some(r) = rows.next().unwrap() {
            n += 1;
            h = h.wrapping_add(cell_hash(r.get::<_, i64>(0).unwrap(), r.get_ref(1).unwrap()));
        }
        (n, h)
    }

    fn load(&self, prop: i64, n: usize) -> Vec<Option<Value>> {
        let mut col = vec![None; n];
        let mut st = self.c.prepare_cached(self.load_sql()).unwrap();
        let mut rows = st.query([prop]).unwrap();
        while let Some(r) = rows.next().unwrap() {
            col[r.get::<_, i64>(0).unwrap() as usize] = Some(r.get::<_, Value>(1).unwrap());
        }
        col
    }

    /// Brings `col` (synced at `since`) up to date. Returns (rows read, reloaded).
    fn sync(&self, prop: i64, since: i64, col: &mut Vec<Option<Value>>) -> (usize, bool) {
        let mut read = 0;
        match self.v {
            V::Inline | V::Lean => {
                let mut st = self
                    .c
                    .prepare_cached(
                        "SELECT instance_id, value, operation FROM v WHERE sequence > ? AND +property_id = ?",
                    )
                    .unwrap();
                let mut rows = st.query(params![since, prop]).unwrap();
                while let Some(r) = rows.next().unwrap() {
                    read += 1;
                    let i = r.get::<_, i64>(0).unwrap() as usize;
                    col[i] = if r.get::<_, i64>(2).unwrap() == DEL { None } else { Some(r.get(1).unwrap()) };
                }
            }
            V::Table | V::Full => {
                if self.v == V::Full {
                    let ver: i64 = self
                        .c
                        .prepare_cached("SELECT column_version FROM props WHERE id = ?")
                        .unwrap()
                        .query_row([prop], |r| r.get(0))
                        .unwrap();
                    if ver > since {
                        *col = self.load(prop, col.len());
                        return (col.iter().filter(|c| c.is_some()).count(), true);
                    }
                } else {
                    // Deletes first: a cell deleted then set again is in the value table.
                    let mut st = self
                        .c
                        .prepare_cached("SELECT k2 FROM tombstones WHERE sequence > ? AND +table_id = 1 AND +k1 = ?")
                        .unwrap();
                    let mut rows = st.query(params![since, prop]).unwrap();
                    while let Some(r) = rows.next().unwrap() {
                        read += 1;
                        col[r.get::<_, i64>(0).unwrap() as usize] = None;
                    }
                }
                let mut st = self
                    .c
                    .prepare_cached("SELECT instance_id, value FROM v WHERE sequence > ? AND +property_id = ?")
                    .unwrap();
                let mut rows = st.query(params![since, prop]).unwrap();
                while let Some(r) = rows.next().unwrap() {
                    read += 1;
                    col[r.get::<_, i64>(0).unwrap() as usize] = Some(r.get(1).unwrap());
                }
            }
        }
        (read, false)
    }

    /// Drops every tombstone up to `seq`.
    fn prune(&self, seq: i64) -> usize {
        match self.v {
            V::Inline | V::Lean => {
                self.c.execute("DELETE FROM v WHERE operation = 3 AND sequence <= ?", [seq]).unwrap()
            }
            V::Table => self.c.execute("DELETE FROM tombstones WHERE sequence <= ?", [seq]).unwrap(),
            V::Full => 0,
        }
    }

    fn checkpoint(&self) {
        self.c.query_row("PRAGMA wal_checkpoint(TRUNCATE)", [], |_| Ok(())).unwrap();
    }

    fn pragma(&self, p: &str) -> i64 {
        self.c.query_row(&format!("PRAGMA {p}"), [], |r| r.get(0)).unwrap()
    }

    /// Bytes per table / index, if dbstat is compiled in.
    fn objects(&self) -> serde_json::Value {
        let Ok(mut st) = self.c.prepare("SELECT name, SUM(pgsize) FROM dbstat GROUP BY name") else {
            return json!(null);
        };
        let rows = st.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, i64>(1)?))).unwrap();
        let m: serde_json::Map<_, _> = rows.map(|r| r.unwrap()).map(|(k, v)| (k, json!(v))).collect();
        json!(m)
    }

    fn plan(&self, sql: &str) -> String {
        let mut st = self.c.prepare(&format!("EXPLAIN QUERY PLAN {sql}")).unwrap();
        let rows = st.query_map([], |r| r.get::<_, String>(3)).unwrap();
        rows.map(|r| r.unwrap()).collect::<Vec<_>>().join("; ")
    }
}

fn cell_hash(i: i64, v: ValueRef<'_>) -> u64 {
    let mut h = FxHasher::default();
    i.hash(&mut h);
    match v {
        ValueRef::Real(f) => f.to_bits().hash(&mut h),
        ValueRef::Text(t) => t.hash(&mut h),
        ValueRef::Integer(x) => x.hash(&mut h),
        _ => 0u8.hash(&mut h),
    }
    h.finish()
}

fn col_digest(col: &[Option<Value>]) -> (usize, u64) {
    let (mut n, mut h) = (0usize, 0u64);
    for (i, c) in col.iter().enumerate() {
        if let Some(v) = c {
            n += 1;
            h = h.wrapping_add(cell_hash(i as i64, v.into()));
        }
    }
    (n, h)
}

fn ms(t: Instant) -> f64 {
    t.elapsed().as_secs_f64() * 1e3
}

fn pct(v: &mut [f64], p: f64) -> f64 {
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    v[((v.len() - 1) as f64 * p).round() as usize]
}

fn median(v: &mut [f64]) -> f64 {
    pct(v, 0.5)
}

fn main() {
    let n: usize = arg("n").map_or(100_000, |s| s.parse().unwrap());
    let dead: f64 = arg("dead").map_or(0.0, |s| s.parse().unwrap());
    let name = arg("variant").unwrap_or_else(|| "inline".into());
    let v = match name.as_str() {
        "inline" => V::Inline,
        "lean" => V::Lean,
        "table" => V::Table,
        "full" => V::Full,
        _ => panic!("--variant=inline|lean|table|full"),
    };
    let dir = arg("dir").expect("--dir=<scratch dir>");
    let path = format!("{dir}/tomb-{name}-{n}-{dead}.db");
    let emit = |op: &str, extra: serde_json::Value| {
        let mut o = json!({ "variant": name, "n": n, "dead": dead, "op": op });
        o.as_object_mut().unwrap().extend(extra.as_object().unwrap().clone());
        println!("{o}");
    };

    let mut rng = Rng(0x9E37_79B9_7F4A_7C15);
    let mut db = Db::create(&path, v);

    // Fill: every instance has both values.
    let t = Instant::now();
    db.begin();
    for prop in [1, 2] {
        for i in 0..n {
            let val = value(prop, &mut rng);
            db.set(prop, i as i64, &val);
        }
    }
    db.commit();
    let fill_ms = ms(t);

    // Churn: clear `dead` of the cells, 10k per commit, in random order.
    let t = Instant::now();
    let mut order: Vec<usize> = (0..n).collect();
    for i in (1..n).rev() {
        order.swap(i, rng.below(i + 1));
    }
    let n_dead = (n as f64 * dead) as usize;
    for prop in [1, 2] {
        for chunk in order[..n_dead].chunks(10_000) {
            db.begin();
            for &i in chunk {
                db.del(prop, i as i64);
            }
            db.commit();
        }
    }
    db.checkpoint();
    let mut live: Vec<i64> = order[n_dead..].iter().map(|&i| i as i64).collect();
    live.sort_unstable();
    emit(
        "build",
        json!({ "fill_ms": fill_ms, "churn_ms": ms(t), "live": live.len(),
                "bytes": db.pragma("page_count") * db.pragma("page_size"),
                "freelist_pages": db.pragma("freelist_count"), "objects": db.objects(),
                "load_plan": db.plan(&db.load_sql().replace('?', "1")) }),
    );

    // Cold load.
    for prop in [1, 2] {
        let mut ts = Vec::new();
        let mut d = (0, 0);
        for rep in 0..6 {
            let t = Instant::now();
            d = db.scan(prop);
            if rep > 0 {
                ts.push(ms(t));
            }
        }
        assert_eq!(d.0, live.len());
        emit("load", json!({ "prop": prop, "ms": median(&mut ts), "rows": d.0 }));
    }

    // Point writes: one cell per commit. Each delete is undone (untimed) to keep the state.
    let mut set_t = Vec::new();
    let mut del_t = Vec::new();
    for _ in 0..300 {
        let i = live[rng.below(live.len())];
        let val = value(1, &mut rng);
        let t = Instant::now();
        db.begin();
        db.set(1, i, &val);
        db.commit();
        set_t.push(ms(t));
        let t = Instant::now();
        db.begin();
        db.del(1, i);
        db.commit();
        del_t.push(ms(t));
        db.begin();
        db.set(1, i, &val);
        db.commit();
    }
    emit("point_set", json!({ "p50": median(&mut set_t), "p95": pct(&mut set_t, 0.95) }));
    emit("point_del", json!({ "p50": median(&mut del_t), "p95": pct(&mut del_t, 0.95) }));

    // Range delete: 10k random live cells in one commit (clearing a selection).
    let mut ts = Vec::new();
    for _ in 0..5 {
        let pick: Vec<i64> = (0..10_000.min(live.len())).map(|_| live[rng.below(live.len())]).collect();
        let t = Instant::now();
        db.begin();
        for &i in &pick {
            db.del(1, i);
        }
        db.commit();
        ts.push(ms(t));
        db.begin();
        for &i in &pick {
            let val = value(1, &mut rng);
            db.set(1, i, &val);
        }
        db.commit();
    }
    emit("range_del", json!({ "cells": 10_000, "ms": median(&mut ts) }));

    // Readers with different lag on the same mixed script: 90% point set, 8% point delete,
    // 2% range delete of 1000 cells. `every` = commits between two syncs.
    let commits = 2000;
    let script: Vec<(u8, Vec<i64>)> = (0..commits)
        .map(|_| {
            let r = rng.below(100);
            let k = if r < 98 { 1 } else { 1000 };
            let kind = if r < 90 { 0 } else { 1 };
            (kind, (0..k).map(|_| rng.below(n) as i64).collect())
        })
        .collect();
    let every = [1usize, 10, 100, 1000];
    let mut readers: Vec<(Vec<Option<Value>>, i64, f64, usize, usize, usize)> =
        every.iter().map(|_| (db.load(1, n), db.seq, 0.0, 0, 0, 0)).collect();
    let mut write_ms = 0.0;
    for (c, (kind, cells)) in script.iter().enumerate() {
        let t = Instant::now();
        db.begin();
        for &i in cells {
            if *kind == 0 {
                let val = value(1, &mut rng);
                db.set(1, i, &val);
            } else {
                db.del(1, i);
            }
        }
        db.commit();
        write_ms += ms(t);
        for (r, &e) in readers.iter_mut().zip(&every) {
            if (c + 1) % e == 0 {
                let since = r.1;
                r.1 = db.seq;
                let t = Instant::now();
                let (read, reloaded) = db.sync(1, since, &mut r.0);
                r.2 += ms(t);
                r.3 += read;
                r.4 += reloaded as usize;
                r.5 += 1;
            }
        }
    }
    let truth = col_digest(&db.load(1, n));
    for (r, &e) in readers.iter().zip(&every) {
        assert_eq!(col_digest(&r.0), truth, "reader every={e} diverged");
        emit(
            "mixed_sync",
            json!({ "every": e, "syncs": r.5, "sync_ms": r.2, "per_sync_ms": r.2 / r.5 as f64,
                    "rows_read": r.3, "reloads": r.4 }),
        );
    }
    emit("mixed_write", json!({ "commits": commits, "ms": write_ms }));

    // Tombstone count, size before / after pruning all of them.
    db.checkpoint();
    let before = db.pragma("page_count") * db.pragma("page_size");
    let t = Instant::now();
    db.begin();
    let pruned = db.prune(db.seq);
    db.commit();
    let prune_ms = ms(t);
    db.checkpoint();
    let t = Instant::now();
    db.c.execute_batch("VACUUM").unwrap();
    let vacuum_ms = ms(t);
    let after = db.pragma("page_count") * db.pragma("page_size");
    emit(
        "prune",
        json!({ "tombstones": pruned, "ms": prune_ms, "vacuum_ms": vacuum_ms,
                "bytes_before": before, "bytes_after_vacuum": after }),
    );

    // Column delete of the text property, then a reader of it catching up.
    let mut reader = db.load(2, n);
    let since = db.seq;
    let t = Instant::now();
    db.begin();
    db.del_column(2);
    db.commit();
    let del_ms = ms(t);
    let t = Instant::now();
    let (read, _) = db.sync(2, since, &mut reader);
    assert_eq!(col_digest(&reader), (0, 0));
    emit("column_del", json!({ "ms": del_ms, "sync_ms": ms(t), "sync_rows": read }));

    drop(db);
    for s in ["", "-wal", "-shm"] {
        let _ = std::fs::remove_file(format!("{path}{s}"));
    }
}
