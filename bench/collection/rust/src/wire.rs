//! Wire benchmark: the bytes the webview has to receive, and what it costs Rust to produce them.
//!
//! - `stream`: today's `/instances/column/{prop_id}` NDJSON, one file per column. Same shape as
//!   `project_routes.get_property_column`: 10k-row batches of `StreamResult { state,
//!   instance_values: [{property_id, ids, values}] }`, every value its own JSON text (the DB's
//!   JSON column passed through), slots with no value left out.
//! - `window`: rows `[offset, offset + w)` of a sorted collection with every property, as row
//!   objects or as columns, in JSON and msgpack.
//! - `page`: a page of a flattened group tree (group header lines and image rows of `PER_ROW`
//!   ids), plus the property values of the images in it.
//! - `headers`: every group header of a tree, what the front needs to size the whole scroll.
//!
//! Every payload is written to `<out>/`, listed in `<out>/manifest.json`, so `js/wire.js` and
//! `py/stream_encode.py` can decode / re-encode the exact same bytes.

use std::fmt::Write as _;
use std::path::Path;
use std::time::Instant;

use rustc_hash::FxHashSet;
use serde::{Serialize, Serializer};

use crate::data::{Col, Data, N_TAGS, N_WORDS};
use crate::group::{GKey, GroupManager, Level, NONE, Tree};
use crate::sort::{self, SortKey};

const BATCH: usize = 10_000; // project_routes._STREAM_BATCH
const PER_ROW: usize = 10;
const PAGE_LINES: usize = 50;

/// (property id, name, front column kind) of every synthetic column.
pub const PROPS: [(u32, &str, &str); 7] = [
    (1, "text", "string"),
    (2, "label", "string"),
    (3, "number", "numeric"),
    (4, "score", "numeric"),
    (5, "date", "date"),
    (6, "checkbox", "bool"),
    (7, "tags", "tag"),
];

// ── today's column stream ──────────────────────────────────────────────────────

/// stream_models.LoadState: not `omit_defaults`, so every field goes out on every line.
#[derive(Serialize, Default)]
struct LoadState {
    finished_property: bool,
    finished_instance: bool,
    finished_tags: bool,
    finished_instance_values: bool,
    finished_image_values: bool,
    finished_file_values: bool,
    finished_property_groups: bool,
    counter_instance: u32,
    counter_instance_value: u32,
    counter_image_value: u32,
    counter_file_value: u32,
    max_instance: u32,
    max_instance_value: u32,
    max_image_value: u32,
    max_file_value: u32,
    max_sequence: u32,
}

#[derive(Serialize)]
struct InstanceValuesColumn<'a> {
    property_id: u32,
    ids: &'a [u32],
    values: &'a [String],
}

#[derive(Serialize)]
struct StreamResult<'a> {
    state: LoadState,
    instance_values: [InstanceValuesColumn<'a>; 1],
}

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

/// The stored JSON text of one cell, or None when the slot has no value (no DB row).
fn cell_text(d: &Data, prop: u32, s: usize) -> Option<String> {
    let mut t = String::new();
    match prop {
        1 | 2 => {
            let c = d.str_col(if prop == 1 { Col::Text } else { Col::Label });
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
        6 => match d.check[s] {
            255 => return None,
            1 => t.push_str("true"),
            _ => t.push_str("false"),
        },
        _ => {
            let tags = d.tags.get(s as u32);
            if tags.is_empty() {
                return None;
            }
            t.push('[');
            for (i, id) in tags.iter().enumerate() {
                if i > 0 {
                    t.push(',');
                }
                write!(t, "{id}").unwrap();
            }
            t.push(']');
        }
    }
    Some(t)
}

/// The value rows of one column as SQLite hands them over: instance id and stored JSON text.
fn value_rows(d: &Data, prop: u32) -> (Vec<u32>, Vec<String>) {
    (0..d.number.len()).filter_map(|s| cell_text(d, prop, s).map(|v| (s as u32 + 1, v))).unzip()
}

/// One full column as NDJSON, in `BATCH`-row lines. Returns the line count.
fn encode_stream(prop: u32, ids: &[u32], values: &[String], out: &mut Vec<u8>) -> usize {
    out.clear();
    let total = ids.len() as u32; // COUNT(*) of the value rows
    let mut counter = 0u32;
    let mut lines = 0;
    for (ids, values) in ids.chunks(BATCH).zip(values.chunks(BATCH)) {
        counter += ids.len() as u32;
        let line = StreamResult {
            state: LoadState { counter_instance_value: counter, max_instance_value: total, ..Default::default() },
            instance_values: [InstanceValuesColumn { property_id: prop, ids, values }],
        };
        serde_json::to_writer(&mut *out, &line).unwrap();
        out.push(b'\n');
        lines += 1;
    }
    lines
}

// ── windowed payloads ──────────────────────────────────────────────────────────

/// A number that goes out as an integer when it is one (msgpack then uses 1–9 bytes, not 9).
#[derive(Clone, Copy)]
struct Num(f64);

impl Serialize for Num {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        if self.0.fract() == 0.0 && self.0.abs() < 9.0e15 { s.serialize_i64(self.0 as i64) } else { s.serialize_f64(self.0) }
    }
}

fn num(x: f64) -> Option<Num> {
    if x.is_nan() { None } else { Some(Num(x)) }
}

fn str_of(c: &crate::data::StrCol, s: usize) -> Option<&str> {
    let code = c.codes[s];
    if code == 0 { None } else { Some(&c.dict[code as usize]) }
}

fn check(d: &Data, s: usize) -> Option<bool> {
    match d.check[s] {
        255 => None,
        v => Some(v == 1),
    }
}

fn tags(d: &Data, s: usize) -> Option<&[u32]> {
    let t = d.tags.get(s as u32);
    if t.is_empty() { None } else { Some(t) }
}

/// One image, keyed by property id; properties with no value are left out.
#[derive(Serialize)]
struct Row<'a> {
    id: u32,
    #[serde(rename = "1", skip_serializing_if = "Option::is_none")]
    text: Option<&'a str>,
    #[serde(rename = "2", skip_serializing_if = "Option::is_none")]
    label: Option<&'a str>,
    #[serde(rename = "3", skip_serializing_if = "Option::is_none")]
    number: Option<Num>,
    #[serde(rename = "4", skip_serializing_if = "Option::is_none")]
    score: Option<Num>,
    #[serde(rename = "5", skip_serializing_if = "Option::is_none")]
    date: Option<Num>,
    #[serde(rename = "6", skip_serializing_if = "Option::is_none")]
    check: Option<bool>,
    #[serde(rename = "7", skip_serializing_if = "Option::is_none")]
    tags: Option<&'a [u32]>,
}

fn rows<'a>(d: &'a Data, slots: &[u32]) -> Vec<Row<'a>> {
    slots
        .iter()
        .map(|&s| {
            let s = s as usize;
            Row {
                id: s as u32 + 1,
                text: str_of(&d.text, s),
                label: str_of(&d.label, s),
                number: num(d.number[s]),
                score: num(d.score[s]),
                date: num(d.date[s]),
                check: check(d, s),
                tags: tags(d, s),
            }
        })
        .collect()
}

/// The same images as one array per property (null = no value).
#[derive(Serialize)]
struct Cols<'a> {
    ids: Vec<u32>,
    #[serde(rename = "1")]
    text: Vec<Option<&'a str>>,
    #[serde(rename = "2")]
    label: Vec<Option<&'a str>>,
    #[serde(rename = "3")]
    number: Vec<Option<Num>>,
    #[serde(rename = "4")]
    score: Vec<Option<Num>>,
    #[serde(rename = "5")]
    date: Vec<Option<Num>>,
    #[serde(rename = "6")]
    check: Vec<Option<bool>>,
    #[serde(rename = "7")]
    tags: Vec<Option<&'a [u32]>>,
}

fn cols<'a>(d: &'a Data, slots: &[u32]) -> Cols<'a> {
    let it = || slots.iter().map(|&s| s as usize);
    Cols {
        ids: slots.iter().map(|&s| s + 1).collect(),
        text: it().map(|s| str_of(&d.text, s)).collect(),
        label: it().map(|s| str_of(&d.label, s)).collect(),
        number: it().map(|s| num(d.number[s])).collect(),
        score: it().map(|s| num(d.score[s])).collect(),
        date: it().map(|s| num(d.date[s])).collect(),
        check: it().map(|s| check(d, s)).collect(),
        tags: it().map(|s| tags(d, s)).collect(),
    }
}

#[derive(Serialize)]
#[serde(untagged)]
enum Values<'a> {
    Rows { rows: Vec<Row<'a>> },
    Cols { cols: Cols<'a> },
}

#[derive(Clone, Copy, PartialEq)]
enum Layout {
    Rows,
    Cols,
}

fn values<'a>(d: &'a Data, slots: &[u32], l: Layout) -> Values<'a> {
    match l {
        Layout::Rows => Values::Rows { rows: rows(d, slots) },
        Layout::Cols => Values::Cols { cols: cols(d, slots) },
    }
}

#[derive(Serialize)]
struct Window<'a> {
    offset: u32,
    total: u32,
    #[serde(flatten)]
    values: Values<'a>,
}

// ── group tree pages ───────────────────────────────────────────────────────────

#[derive(Serialize)]
#[serde(untagged)]
enum GVal<'a> {
    S(&'a str),
    N(Num),
    B(bool),
}

#[derive(Serialize)]
#[serde(untagged)]
enum Line<'a> {
    Group { group: u32, depth: u32, count: u32, value: Option<GVal<'a>> },
    Images { group: u32, ids: Vec<u32> },
}

#[derive(Serialize)]
struct Page<'a> {
    offset: u64,
    total_lines: u64,
    lines: Vec<Line<'a>>,
    #[serde(flatten)]
    values: Values<'a>,
}

#[derive(Serialize)]
struct Headers<'a> {
    total_lines: u64,
    groups: Vec<Line<'a>>,
}

/// The tree flattened into display lines: a header per group, then `PER_ROW` images per line
/// in leaves. Built once per tree; a page is then a binary search away.
struct Lines {
    /// (node index, depth, first line) in display order.
    nodes: Vec<(u32, u32, u64)>,
    total: u64,
}

fn line_layout(t: &Tree) -> Lines {
    let mut nodes = Vec::with_capacity(t.nodes.len());
    let mut line = 0u64;
    let root = &t.nodes[0];
    let mut stack: Vec<(u32, u32)> = (root.first_child..root.first_child + root.n_children).rev().map(|c| (c, 1)).collect();
    while let Some((i, depth)) = stack.pop() {
        let n = &t.nodes[i as usize];
        nodes.push((i, depth, line));
        line += 1;
        if n.n_children == 0 {
            line += (n.len as usize).div_ceil(PER_ROW) as u64;
        } else {
            stack.extend((n.first_child..n.first_child + n.n_children).rev().map(|c| (c, depth + 1)));
        }
    }
    Lines { nodes, total: line }
}

fn group_value<'a>(d: &'a Data, levels: &[Level], depth: u32, key: u64) -> Option<GVal<'a>> {
    if key == NONE {
        return None;
    }
    Some(match levels[depth as usize - 1].key {
        GKey::Str(c) => GVal::S(&d.str_col(c).dict[key as usize]),
        GKey::Tags => GVal::S(&d.words[N_WORDS - N_TAGS + key as usize - 1]),
        GKey::Num(_) => GVal::N(Num(f64::from_bits(key))),
        GKey::DateMonth | GKey::DateYear => GVal::N(Num(key as f64)),
        GKey::Check => GVal::B(key == 1),
    })
}

fn header<'a>(d: &'a Data, t: &Tree, levels: &[Level], i: u32, depth: u32) -> Line<'a> {
    let n = &t.nodes[i as usize];
    Line::Group { group: n.id, depth, count: n.len, value: group_value(d, levels, depth, n.key) }
}

/// `PAGE_LINES` lines from `offset`, and the slots of the images they show (deduped: with tags,
/// one image can sit in several groups).
fn page<'a>(d: &'a Data, t: &Tree, levels: &[Level], lay: &Lines, offset: u64) -> (Vec<Line<'a>>, Vec<u32>) {
    let mut k = lay.nodes.partition_point(|&(_, _, start)| start <= offset) - 1;
    let mut lines = Vec::with_capacity(PAGE_LINES);
    let mut slots = Vec::new();
    let mut seen = FxHashSet::default();
    let mut at = offset;
    while lines.len() < PAGE_LINES && k < lay.nodes.len() {
        let (i, depth, start) = lay.nodes[k];
        let n = &t.nodes[i as usize];
        if at == start {
            lines.push(header(d, t, levels, i, depth));
            at += 1;
        }
        if n.n_children == 0 {
            let leaf = &t.slots[n.start as usize..(n.start + n.len) as usize];
            let mut row = (at - start - 1) as usize;
            while lines.len() < PAGE_LINES && row * PER_ROW < leaf.len() {
                let ids = &leaf[row * PER_ROW..((row + 1) * PER_ROW).min(leaf.len())];
                slots.extend(ids.iter().filter(|&&s| seen.insert(s)));
                lines.push(Line::Images { group: n.id, ids: ids.iter().map(|&s| s + 1).collect() });
                row += 1;
                at += 1;
            }
        }
        k += 1;
    }
    (lines, slots)
}

// ── driver ─────────────────────────────────────────────────────────────────────

#[derive(Clone, Copy)]
enum Fmt {
    Json,
    Msgpack,
}

impl Fmt {
    fn name(self) -> &'static str {
        match self {
            Fmt::Json => "json",
            Fmt::Msgpack => "msgpack",
        }
    }
}

fn encode<T: Serialize>(v: &T, f: Fmt, out: &mut Vec<u8>) {
    out.clear();
    match f {
        Fmt::Json => serde_json::to_writer(&mut *out, v).unwrap(),
        Fmt::Msgpack => v.serialize(&mut rmp_serde::Serializer::new(&mut *out).with_struct_map()).unwrap(),
    }
}

/// Median and min ms of `f`, run until both `min_reps` and `budget_ms` are reached.
fn time(min_reps: usize, budget_ms: f64, mut f: impl FnMut()) -> (f64, f64, usize) {
    f(); // warmup
    let mut times = Vec::new();
    let t_all = Instant::now();
    while times.len() < min_reps || (t_all.elapsed().as_secs_f64() * 1000.0) < budget_ms {
        let t0 = Instant::now();
        f();
        times.push(t0.elapsed().as_secs_f64() * 1000.0);
        if times.len() >= 10_000 {
            break;
        }
    }
    times.sort_by(|a, b| a.partial_cmp(b).unwrap());
    (times[times.len() / 2], times[0], times.len())
}

struct Out<'a> {
    n: usize,
    dir: &'a Path,
    manifest: Vec<String>,
}

impl Out<'_> {
    /// Writes the payload and prints / records one result line.
    fn emit(&mut self, group: &str, op: &str, fmt: &str, file: &str, bytes: &[u8], (ms, min_ms, reps): (f64, f64, usize), extra: &str) {
        std::fs::write(self.dir.join(file), bytes).unwrap();
        let common = format!(r#""group":"{group}","op":"{op}","fmt":"{fmt}","file":"{file}","bytes":{}{extra}"#, bytes.len());
        println!(r#"{{"impl":"rust","kind":"wire","n":{},{common},"ms":{ms:.4},"min_ms":{min_ms:.4},"reps":{reps}}}"#, self.n);
        self.manifest.push(format!("{{{common}}}"));
    }
}

pub fn run(d: &Data, n: usize, dir: &Path, wins: &[usize], only: Option<&regex::Regex>) {
    std::fs::create_dir_all(dir).unwrap();
    let mut o = Out { n, dir, manifest: Vec::new() };
    let want = |id: &str| only.is_none_or(|r| r.is_match(id));
    let mut buf = Vec::new();
    let reps = if n >= 5_000_000 { 2 } else { 3 };

    for (prop, name, kind) in PROPS {
        if !want(&format!("stream: {name}")) {
            continue;
        }
        let (ids, values) = value_rows(d, prop);
        let mut lines = 0;
        let t = time(reps, 0.0, || lines = encode_stream(prop, &ids, &values, &mut buf));
        let extra = format!(r#","prop":{prop},"col_kind":"{kind}","lines":{lines}"#);
        o.emit("stream", name, "ndjson", &format!("stream-{name}.ndjson"), &buf, t, &extra);
    }

    // The collection as the grid shows it: sorted by label, then score desc.
    let all: Vec<u32> = (0..n as u32).collect();
    let order = sort::sort(d, &[SortKey { col: Col::Label, dir: 1 }, SortKey { col: Col::Score, dir: -1 }], &all);
    let mid = (n / 2) as u32;
    for &w in wins {
        let end = (mid as usize + w).min(n);
        let win = &order[mid as usize..end];
        for layout in [Layout::Rows, Layout::Cols] {
            let lname = if layout == Layout::Rows { "rows" } else { "cols" };
            for f in [Fmt::Json, Fmt::Msgpack] {
                let op = format!("{w} {lname}");
                if !want(&format!("window: {op}")) {
                    continue;
                }
                let t = time(200, 300.0, || {
                    let p = Window { offset: mid, total: n as u32, values: values(d, win, layout) };
                    encode(&p, f, &mut buf);
                });
                let extra = format!(r#","layout":"{lname}","rows":{}"#, win.len());
                o.emit("window", &op, f.name(), &format!("window-{w}-{lname}.{}", f.name()), &buf, t, &extra);
            }
        }
    }

    let trees: [(&str, &str, Vec<Level>); 2] = [
        ("label-year", "label > date by year", vec![Level { key: GKey::Str(Col::Label), dir: 1 }, Level { key: GKey::DateYear, dir: 1 }]),
        ("tags", "tags (+parents)", vec![Level { key: GKey::Tags, dir: 1 }]),
    ];
    let by_score = sort::sort(d, &[SortKey { col: Col::Score, dir: -1 }], &all);
    for (short, name, levels) in trees {
        if !want(&format!("page: {name}")) && !want(&format!("headers: {name}")) {
            continue;
        }
        let tree = GroupManager::new(levels.clone()).group(d, &by_score);
        let mut lay = line_layout(&tree);
        let t_lay = time(5, 200.0, || lay = line_layout(&tree));
        let groups = lay.nodes.len();
        let mid_line = lay.total / 2;
        println!(
            r#"{{"impl":"rust","kind":"wire","n":{n},"group":"layout","op":"{name}","fmt":"-","bytes":0,"groups":{groups},"total_lines":{},"ms":{:.4},"min_ms":{:.4},"reps":{}}}"#,
            lay.total, t_lay.0, t_lay.1, t_lay.2
        );
        for layout in [Layout::Rows, Layout::Cols] {
            let lname = if layout == Layout::Rows { "rows" } else { "cols" };
            for f in [Fmt::Json, Fmt::Msgpack] {
                let mut images = 0;
                let t = time(200, 300.0, || {
                    let (lines, slots) = page(d, &tree, &levels, &lay, mid_line);
                    images = slots.len();
                    let p = Page { offset: mid_line, total_lines: lay.total, lines, values: values(d, &slots, layout) };
                    encode(&p, f, &mut buf);
                });
                let extra = format!(r#","layout":"{lname}","rows":{images},"lines":{PAGE_LINES}"#);
                let op = format!("{name} {lname}");
                o.emit("page", &op, f.name(), &format!("page-{short}-{lname}.{}", f.name()), &buf, t, &extra);
            }
        }
        for f in [Fmt::Json, Fmt::Msgpack] {
            let t = time(5, 200.0, || {
                let groups = lay.nodes.iter().map(|&(i, depth, _)| header(d, &tree, &levels, i, depth)).collect();
                encode(&Headers { total_lines: lay.total, groups }, f, &mut buf);
            });
            let extra = format!(r#","groups":{groups}"#);
            o.emit("headers", name, f.name(), &format!("headers-{short}.{}", f.name()), &buf, t, &extra);
        }
    }

    let manifest = format!("{{\"n\":{n},\"files\":[\n{}\n]}}\n", o.manifest.join(",\n"));
    std::fs::write(dir.join("manifest.json"), manifest).unwrap();
}
