//! Fills a schema-only `data.db` (created by the Python `DataWriter`, so the tables are exactly
//! the backend's) with the synthetic collection of `data.rs`: N instances, the 7 properties of
//! the wire bench, their values as the backend stores them (JSON text in `instance_values`, one
//! `instance_tag_values` row per tag), and the 1000 tags with their parents.

use std::fmt::Write;

use rusqlite::{Connection, params};

use crate::data::{self, N_TAGS, N_WORDS};

/// (property id, name, dtype). Same ids and names as `rust/src/wire.rs` PROPS.
pub const PROPS: [(i64, &str, &str); 7] = [
    (1, "text", "text"),
    (2, "label", "text"),
    (3, "number", "number"),
    (4, "score", "number"),
    (5, "date", "date"),
    (6, "checkbox", "checkbox"),
    (7, "tags", "multi_tags"),
];
const TAG_LIST: i64 = 1;

// `civil`, `iso` and `num_text` are the ones of `rust/src/wire.rs`, so the stored text is the
// text the wire bench's stream carries.
fn civil(z: i64) -> (i64, i64, i64) {
    let z = z + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (yoe + era * 400 + (m <= 2) as i64, m, d)
}

/// `Date.prototype.toISOString`.
fn iso(ms: f64, out: &mut String) {
    let ms = ms as i64;
    let (days, rem) = (ms.div_euclid(86_400_000), ms.rem_euclid(86_400_000));
    let (y, m, d) = civil(days);
    let (h, mi, s, f) = (rem / 3_600_000, rem / 60_000 % 60, rem / 1000 % 60, rem % 1000);
    write!(out, "{y:04}-{m:02}-{d:02}T{h:02}:{mi:02}:{s:02}.{f:03}Z").unwrap();
}

/// JSON number text the way Python's json / orjson writes it (integers without `.0`).
fn num_text(x: f64, out: &mut String) {
    if x.fract() == 0.0 && x.abs() < 9.0e15 {
        write!(out, "{}", x as i64).unwrap();
    } else {
        out.push_str(&serde_json::to_string(&x).unwrap());
    }
}

/// The stored JSON text of one non-tag cell, or None when the slot has no value (no row).
fn cell_text(d: &data::Data, prop: i64, s: usize) -> Option<String> {
    let mut t = String::new();
    match prop {
        1 | 2 => {
            let c = if prop == 1 { &d.text } else { &d.label };
            let code = c.codes[s];
            if code == 0 {
                return None;
            }
            t = serde_json::to_string(&*c.dict[code as usize]).unwrap();
        }
        3 | 4 => {
            let x = if prop == 3 { d.number[s] } else { d.score[s] };
            if x.is_nan() {
                return None;
            }
            num_text(x, &mut t);
        }
        5 => {
            if d.date[s].is_nan() {
                return None;
            }
            t.push('"');
            iso(d.date[s], &mut t);
            t.push('"');
        }
        _ => match d.check[s] {
            255 => return None,
            1 => t.push_str("true"),
            _ => t.push_str("false"),
        },
    }
    Some(t)
}

/// A fake, unique, 40-hex sha1 per instance (splitmix64 of the id).
fn sha1(id: u64) -> String {
    let mix = |mut z: u64| {
        z = z.wrapping_add(0x9E37_79B9_7F4A_7C15);
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    };
    format!("{:016x}{:016x}{:08x}", mix(id), mix(id ^ 0xA5A5), mix(id ^ 0x5A5A) as u32)
}

pub fn fill(path: &str, n: usize) {
    let d = data::generate(n);
    let mut c = Connection::open(path).unwrap();
    let empty: i64 = c.query_row("SELECT COUNT(*) FROM instances", [], |r| r.get(0)).expect("data.db has no schema: create it with py/column_load.py --create");
    assert_eq!(empty, 0, "{path} is not empty");
    c.execute_batch("PRAGMA synchronous = OFF; PRAGMA cache_size = -500000;").unwrap();
    let tx = c.transaction().unwrap();
    {
        let mut st = tx
            .prepare("INSERT INTO properties (id, dtype, mode, name, access, tag_list_id, system_key, property_group_id, commit_id, operation, sequence) VALUES (?, ?, 'id', ?, NULL, ?, NULL, NULL, 0, 1, 1)")
            .unwrap();
        for (id, name, dtype) in PROPS {
            st.execute(params![id, dtype, name, (dtype == "multi_tags").then_some(TAG_LIST)]).unwrap();
        }
        tx.execute("INSERT INTO tag_lists (id, name) VALUES (?, 'tags')", [TAG_LIST]).unwrap();
        let mut st = tx.prepare("INSERT INTO tags (id, list_id, parents, value, color, commit_id, operation, sequence) VALUES (?, ?, ?, ?, -1, 0, 1, 1)").unwrap();
        for id in 1..=N_TAGS {
            let parents = d.tag_defs[id].all_parents.first().map(|p| format!("[{p}]")).unwrap_or_else(|| "[]".into());
            st.execute(params![id as i64, TAG_LIST, parents, d.words[N_WORDS - N_TAGS + id - 1]]).unwrap();
        }

        let mut st = tx.prepare("INSERT INTO instances (id, file_id, sha1, sequence) VALUES (?, ?, ?, 1)").unwrap();
        for s in 0..n {
            let id = s as i64 + 1;
            st.execute(params![id, id, sha1(id as u64)]).unwrap();
        }
        // Rows in (property_id, instance_id) order: the primary key order, as the backend's
        // bulk imports leave them.
        let mut st = tx.prepare("INSERT INTO instance_values (property_id, instance_id, value, commit_id, operation, sequence) VALUES (?, ?, ?, 0, 1, 1)").unwrap();
        for (prop, _, dtype) in PROPS {
            if dtype == "multi_tags" {
                continue;
            }
            for s in 0..n {
                if let Some(v) = cell_text(&d, prop, s) {
                    st.execute(params![prop, s as i64 + 1, v]).unwrap();
                }
            }
        }
        let mut st = tx.prepare("INSERT INTO instance_tag_values (instance_id, property_id, tag_id, commit_id, operation, sequence) VALUES (?, 7, ?, 0, 1, 1)").unwrap();
        for s in 0..n {
            for &t in d.tags.get(s as u32) {
                st.execute(params![s as i64 + 1, t as i64]).unwrap();
            }
        }
    }
    tx.commit().unwrap();
    c.execute_batch("PRAGMA wal_checkpoint(TRUNCATE); ANALYZE;").unwrap();
}
