//! Cold-start column loads: value rows vs a cached column blob (opti/03 "column snapshot cache").
//!
//!   load-bench --db=<data.db> --cold=<scratch dir>
//!
//! data.db is copied once to `<dir>/cache.db`, which gets a `column_cache(property_id, codec,
//! raw_len, data)` table holding every column as the typed load builds it: `raw` (the arrays as
//! little-endian bytes) and `zstd` (the same, level 3). Every cold measure runs on a fresh copy
//! of cache.db written with F_NOCACHE, so none of its pages are in the OS cache: `resident` is
//! the share of the copy's pages in memory just before the timed load (mincore), `copy_resident`
//! the same right after the copy. Open, schema
//! and identity are read untimed, then one column load is timed. Repeating that load on the
//! same connection gives the warm time.
//!
//! Variants: `sqlite` (rows stepped only), `typed` (rows → column), `blob` and `blob-zstd`
//! (blob → column). Op `open` times a whole project open on a fresh copy: connection, schema,
//! identity and every column.
//!
//! Blob layout, slots in identity order: num = n f64; bool = n u8; str = n u32 codes, then per
//! dict code from 1: u32 length + UTF-8 bytes; tags = n + 1 u32 offsets, then the i32 tag ids.

use std::fs::{self, File};
use std::io::{Read, Write};
use std::os::fd::AsRawFd;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Instant;

use rusqlite::{Connection, params};

use crate::schema::{ColumnKind, PropertyDef};
use crate::store::{Column, Delta, Snapshot, StrColumn, StrDict, TagColumn};
use crate::{digest, load_base, load_schema, load_typed, open, scan, time};

const VARIANTS: [&str; 4] = ["sqlite", "typed", "blob", "blob-zstd"];

// ── blob codec ─────────────────────────────────────────────────────────────────

fn encode(col: &Column) -> Vec<u8> {
    let mut out = Vec::new();
    match col {
        Column::Num(d) => d.iter().for_each(|x| out.extend_from_slice(&x.to_le_bytes())),
        Column::Bool(d) => out.extend_from_slice(d),
        Column::Str(s) => {
            s.codes.iter().for_each(|c| out.extend_from_slice(&c.to_le_bytes()));
            for code in 1..s.dict.len() as u32 {
                let v = s.dict.get(code).unwrap().as_bytes();
                out.extend_from_slice(&(v.len() as u32).to_le_bytes());
                out.extend_from_slice(v);
            }
        }
        Column::Tags(t) => {
            t.offsets.iter().for_each(|o| out.extend_from_slice(&o.to_le_bytes()));
            t.values.iter().for_each(|v| out.extend_from_slice(&v.to_le_bytes()));
        }
    }
    out
}

fn u32s(b: &[u8]) -> Vec<u32> {
    b.chunks_exact(4).map(|c| u32::from_le_bytes(c.try_into().unwrap())).collect()
}

fn decode(kind: ColumnKind, n: usize, b: &[u8]) -> Column {
    match kind {
        ColumnKind::Num => Column::Num(Arc::new(b.chunks_exact(8).map(|c| f64::from_le_bytes(c.try_into().unwrap())).collect())),
        ColumnKind::Bool => Column::Bool(Arc::new(b.to_vec())),
        ColumnKind::Str => {
            let codes = u32s(&b[..n * 4]);
            let mut dict = StrDict::new();
            let mut rest = &b[n * 4..];
            while !rest.is_empty() {
                let len = u32::from_le_bytes(rest[..4].try_into().unwrap()) as usize;
                dict.intern(std::str::from_utf8(&rest[4..4 + len]).unwrap());
                rest = &rest[4 + len..];
            }
            Column::Str(Arc::new(StrColumn { codes, dict: Arc::new(dict) }))
        }
        ColumnKind::Tags => {
            let offsets = u32s(&b[..(n + 1) * 4]);
            let values = b[(n + 1) * 4..].chunks_exact(4).map(|c| i32::from_le_bytes(c.try_into().unwrap())).collect();
            Column::Tags(Arc::new(TagColumn { offsets, values }))
        }
    }
}

fn load_blob(c: &Connection, n: usize, p: &PropertyDef, codec: &str) -> Column {
    let mut st = c.prepare_cached("SELECT raw_len, data FROM column_cache WHERE property_id = ?1 AND codec = ?2").unwrap();
    st.query_row(params![p.id, codec], |r| {
        let b = r.get_ref(1)?.as_blob()?;
        Ok(if codec == "zstd" {
            decode(p.ptype.kind(), n, &zstd::bulk::decompress(b, r.get::<_, usize>(0)?).unwrap())
        } else {
            decode(p.ptype.kind(), n, b)
        })
    })
    .unwrap()
}

/// One column load; None for `sqlite`, which builds nothing.
fn run(variant: &str, c: &Connection, base: &Snapshot, p: &PropertyDef) -> Option<Snapshot> {
    let col = match variant {
        "sqlite" => {
            std::hint::black_box(scan(c, p));
            return None;
        }
        "typed" => load_typed(c, base, p),
        "blob" => load_blob(c, base.len(), p, "raw"),
        _ => load_blob(c, base.len(), p, "zstd"),
    };
    Some(base.apply(&[Delta::SetColumn { property_id: p.id, column: col }]).0)
}

// ── cold files ─────────────────────────────────────────────────────────────────

fn no_cache(f: &File) {
    assert_ne!(unsafe { libc::fcntl(f.as_raw_fd(), libc::F_NOCACHE, 1) }, -1);
}

/// A copy of `src` whose pages are not in the OS cache: read and written with F_NOCACHE.
fn fresh_copy(src: &Path, dst: &Path) {
    for ext in ["", "-wal", "-shm"] {
        let _ = fs::remove_file(format!("{}{ext}", dst.display()));
    }
    let mut i = File::open(src).unwrap();
    let mut o = File::create(dst).unwrap();
    no_cache(&i);
    no_cache(&o);
    let mut buf = vec![0u8; 8 << 20];
    loop {
        let k = i.read(&mut buf).unwrap();
        if k == 0 {
            break;
        }
        o.write_all(&buf[..k]).unwrap();
    }
    o.sync_all().unwrap();
}

/// Share of the file's pages in the OS cache.
fn resident(path: &Path) -> f64 {
    let f = File::open(path).unwrap();
    let len = f.metadata().unwrap().len() as usize;
    let page = unsafe { libc::sysconf(libc::_SC_PAGESIZE) } as usize;
    unsafe {
        let m = libc::mmap(std::ptr::null_mut(), len, libc::PROT_READ, libc::MAP_SHARED, f.as_raw_fd(), 0);
        assert_ne!(m, libc::MAP_FAILED);
        let mut v = vec![0 as libc::c_char; len.div_ceil(page)];
        assert_eq!(libc::mincore(m as _, len, v.as_mut_ptr() as _), 0);
        libc::munmap(m, len);
        v.iter().filter(|&&x| x & 1 != 0).count() as f64 / v.len() as f64
    }
}

// ── main ───────────────────────────────────────────────────────────────────────

fn build_cache(src: &str, dst: &Path) {
    fs::copy(src, dst).unwrap();
    let c = Connection::open(dst).unwrap();
    c.execute_batch(
        "CREATE TABLE column_cache (property_id INTEGER NOT NULL, codec TEXT NOT NULL, raw_len INTEGER NOT NULL,
            data BLOB NOT NULL, PRIMARY KEY (property_id, codec)) WITHOUT ROWID;",
    )
    .unwrap();
    let schema = Arc::new(load_schema(&c));
    let base = load_base(&c, &schema);
    for p in schema.properties.values().filter(|p| p.system_key.is_none()) {
        let raw = encode(&load_typed(&c, &base, p));
        let z = zstd::bulk::compress(&raw, 3).unwrap();
        for (codec, data) in [("raw", &raw), ("zstd", &z)] {
            c.execute("INSERT INTO column_cache VALUES (?1, ?2, ?3, ?4)", params![p.id, codec, raw.len(), data]).unwrap();
        }
    }
    // Blob pages land after the value tables, as a cache written by a running app would.
    c.execute_batch("PRAGMA wal_checkpoint(TRUNCATE);").ok();
}

pub fn run_cold(db: &str, dir: &str) {
    fs::create_dir_all(dir).unwrap();
    let cache_db = PathBuf::from(dir).join("cache.db");
    let cold = PathBuf::from(dir).join("cold.db");
    if !cache_db.exists() {
        eprintln!("building {}", cache_db.display());
        build_cache(db, &cache_db);
    }
    let reps: usize = crate::arg("reps").map(|x| x.parse().unwrap()).unwrap_or(5);
    let only = crate::arg("only");

    let c = open(cache_db.to_str().unwrap());
    let schema = Arc::new(load_schema(&c));
    let n = load_base(&c, &schema).len();
    let file_bytes = fs::metadata(&cache_db).unwrap().len();
    let sizes: Vec<(i64, String, i64)> = {
        let mut st = c.prepare("SELECT property_id, codec, length(data) FROM column_cache").unwrap();
        st.query_map([], |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?))).unwrap().map(Result::unwrap).collect()
    };
    drop(c);
    let size = |id: i64, codec: &str| sizes.iter().find(|s| s.0 == id && s.1 == codec).map_or(0, |s| s.2);
    let (raw_total, z_total): (i64, i64) = sizes.iter().fold((0, 0), |a, s| if s.1 == "raw" { (a.0 + s.2, a.1) } else { (a.0, a.1 + s.2) });
    println!(r#"{{"kind":"cold-file","n":{n},"file_bytes":{file_bytes},"raw_bytes":{raw_total},"zstd_bytes":{z_total}}}"#);

    let emit = |op: &str, variant: &str, state: &str, ms: &mut Vec<f64>, extra: String| {
        ms.sort_by(|a, b| a.partial_cmp(b).unwrap());
        println!(
            r#"{{"kind":"cold","n":{n},"op":"{op}","variant":"{variant}","state":"{state}","ms":{:.3},"min_ms":{:.3},"reps":{}{extra}}}"#,
            ms[ms.len() / 2],
            ms[0],
            ms.len()
        );
    };

    let props: Vec<PropertyDef> = schema.properties.values().filter(|p| p.system_key.is_none()).cloned().collect();
    for p in &props {
        if only.as_deref().is_some_and(|o| !p.name.contains(o)) {
            continue;
        }
        let mut want = None;
        for v in VARIANTS {
            eprintln!("{} {v}", p.name);
            let (mut cold_ms, mut res, mut copy_res) = (Vec::new(), Vec::new(), Vec::new());
            let mut warm = (0.0, 0.0, 0);
            for rep in 0..reps {
                fresh_copy(&cache_db, &cold);
                copy_res.push(resident(&cold));
                let c = open(cold.to_str().unwrap());
                let schema = Arc::new(load_schema(&c));
                let base = load_base(&c, &schema);
                res.push(resident(&cold));
                let t0 = Instant::now();
                let snap = std::hint::black_box(run(v, &c, &base, p));
                cold_ms.push(t0.elapsed().as_secs_f64() * 1000.0);
                if rep == 0 {
                    if let Some(s) = &snap {
                        let d = digest(s, p.id);
                        assert_eq!(*want.get_or_insert(d), d, "{}: {v} differs from typed", p.name);
                    }
                    warm = time(reps, || drop(std::hint::black_box(run(v, &c, &base, p))));
                }
            }
            let bytes = match v {
                "blob" => size(p.id, "raw"),
                "blob-zstd" => size(p.id, "zstd"),
                _ => 0,
            };
            let max_res = res.iter().cloned().fold(0.0, f64::max);
            let max_copy = copy_res.iter().cloned().fold(0.0, f64::max);
            emit(&p.name, v, "cold", &mut cold_ms, format!(r#","copy_resident":{max_copy:.4},"resident":{max_res:.4},"bytes":{bytes}"#));
            println!(
                r#"{{"kind":"cold","n":{n},"op":"{}","variant":"{v}","state":"warm","ms":{:.3},"min_ms":{:.3},"reps":{},"bytes":{bytes}}}"#,
                p.name, warm.0, warm.1, warm.2
            );
        }
    }

    // Whole project open: connection, schema, identity, every column, from a cold file.
    if only.is_none() {
        for v in ["typed", "blob", "blob-zstd"] {
            eprintln!("open {v}");
            let (mut ms, mut res) = (Vec::new(), Vec::new());
            for _ in 0..reps {
                fresh_copy(&cache_db, &cold);
                res.push(resident(&cold));
                let t0 = Instant::now();
                let c = open(cold.to_str().unwrap());
                let schema = Arc::new(load_schema(&c));
                let mut snap = load_base(&c, &schema);
                for p in &props {
                    snap = run(v, &c, &snap, p).unwrap();
                }
                std::hint::black_box(&snap);
                ms.push(t0.elapsed().as_secs_f64() * 1000.0);
            }
            let max_res = res.iter().cloned().fold(0.0, f64::max);
            emit("open", v, "cold", &mut ms, format!(r#","resident":{max_res:.4}"#));
        }
    }
    for ext in ["", "-wal", "-shm"] {
        let _ = fs::remove_file(format!("{}{ext}", cold.display()));
    }
}
