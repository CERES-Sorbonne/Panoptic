//! Collection benchmark — Rust side. Same data, same ops, same checksums as `js/bench.js`.
//! Every op runs twice: on a 1-thread rayon pool and on a pool with every core.
//!
//!   cargo run --release -- --n=1000000

mod data;
mod filter;
mod group;
mod lines;
mod sort;
mod wire;

use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicBool, AtomicIsize, Ordering::Relaxed};
use std::time::Instant;

use data::{Col, Data};
use filter::{FilterState, Node, Op};
use group::{GKey, GroupManager, Level, Tree};
use sort::SortKey;

fn arg(name: &str) -> Option<String> {
    let p = format!("--{name}=");
    std::env::args().find_map(|a| a.strip_prefix(&p).map(str::to_string))
}

/// Counts live heap bytes and their high-water mark, only when `--mem` is on (one relaxed load
/// per allocation otherwise). Signed so blocks allocated before tracking starts can't underflow.
struct Counting;
static TRACK: AtomicBool = AtomicBool::new(false);
static LIVE: AtomicIsize = AtomicIsize::new(0);
static PEAK: AtomicIsize = AtomicIsize::new(0);

#[inline]
fn track(delta: isize) {
    if TRACK.load(Relaxed) {
        let live = LIVE.fetch_add(delta, Relaxed) + delta;
        if delta > 0 {
            PEAK.fetch_max(live, Relaxed);
        }
    }
}

unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, l: Layout) -> *mut u8 {
        let p = System.alloc(l);
        if !p.is_null() {
            track(l.size() as isize);
        }
        p
    }
    unsafe fn alloc_zeroed(&self, l: Layout) -> *mut u8 {
        let p = System.alloc_zeroed(l);
        if !p.is_null() {
            track(l.size() as isize);
        }
        p
    }
    unsafe fn dealloc(&self, p: *mut u8, l: Layout) {
        System.dealloc(p, l);
        track(-(l.size() as isize));
    }
    unsafe fn realloc(&self, p: *mut u8, l: Layout, new: usize) -> *mut u8 {
        let q = System.realloc(p, l, new);
        if !q.is_null() {
            track(new as isize - l.size() as isize);
        }
        q
    }
}

#[global_allocator]
static ALLOC: Counting = Counting;

#[inline]
fn mix(h: u32, v: u32) -> u32 {
    h.wrapping_mul(31).wrapping_add(v)
}

struct Res {
    count: usize,
    entries: Option<usize>,
    hash: u32,
}

fn hash_slots(s: &[u32]) -> Res {
    Res { count: s.len(), entries: None, hash: s.iter().fold(0, |h, &x| mix(h, x + 1)) }
}

fn hash_tree(t: &Tree) -> Res {
    let (mut h, mut groups, mut entries) = (0u32, 0usize, 0usize);
    fn visit(t: &Tree, i: usize, h: &mut u32, groups: &mut usize, entries: &mut usize) {
        let n = &t.nodes[i];
        *h = mix(*h, 0x9e37_79b9 ^ n.n_children);
        if n.n_children == 0 {
            *entries += n.len as usize;
            for &s in &t.slots[n.start as usize..(n.start + n.len) as usize] {
                *h = mix(*h, s + 1);
            }
        } else {
            for c in n.first_child..n.first_child + n.n_children {
                *groups += 1;
                visit(t, c as usize, h, groups, entries);
            }
        }
    }
    visit(t, 0, &mut h, &mut groups, &mut entries);
    Res { count: groups, entries: Some(entries), hash: h }
}

enum Out {
    Slots(Vec<u32>),
    Tree(Tree),
}

impl Out {
    fn hash(&self) -> Res {
        match self {
            Out::Slots(s) => hash_slots(s),
            Out::Tree(t) => hash_tree(t),
        }
    }
}

type OpFn<'a> = Box<dyn FnMut(&[u32]) -> Out + 'a>;

fn leaf(c: Col, op: Op) -> Node {
    Node::Leaf(c, op)
}
fn fstate(root: Node) -> FilterState {
    FilterState { root, query: None }
}
fn compound() -> Node {
    Node::And(vec![
        leaf(Col::Number, Op::Greater(2000.0)),
        leaf(Col::Date, Op::Greater(1_514_764_800_000.0)), // '2018-01-01'
        Node::Or(vec![leaf(Col::Tags, Op::ContainsAny(vec![5])), leaf(Col::Text, Op::Contains("ka".into()))]),
    ])
}
fn asc(col: Col) -> SortKey {
    SortKey { col, dir: 1 }
}
fn desc(col: Col) -> SortKey {
    SortKey { col, dir: -1 }
}
fn lv(key: GKey) -> Level {
    Level { key, dir: 1 }
}

fn ops(d: &Data) -> Vec<(&'static str, &'static str, OpFn<'_>)> {
    let f = |st: FilterState| -> OpFn { Box::new(move |s: &[u32]| Out::Slots(filter::filter(d, &st, s))) };
    let so = |keys: Vec<SortKey>| -> OpFn { Box::new(move |s: &[u32]| Out::Slots(sort::sort(d, &keys, s))) };
    let g = |levels: Vec<Level>| -> OpFn {
        let mut gm = GroupManager::new(levels);
        Box::new(move |s: &[u32]| Out::Tree(gm.group(d, s)))
    };
    let and1 = |c, op| fstate(Node::And(vec![leaf(c, op)]));
    let w7 = d.words[7].clone();
    vec![
        ("filter", "number > 5000", f(and1(Col::Number, Op::Greater(5000.0)))),
        ("filter", "number isSet", f(and1(Col::Number, Op::IsSet))),
        ("filter", "score <= 250.5", f(and1(Col::Score, Op::Leq(250.5)))),
        ("filter", "date > 2020-01-01", f(and1(Col::Date, Op::Greater(1_577_836_800_000.0)))),
        ("filter", "checkbox isTrue", f(and1(Col::Check, Op::IsTrue))),
        ("filter", "text contains", f(and1(Col::Text, Op::Contains("lumi".into())))),
        ("filter", "text startsWith", f(and1(Col::Text, Op::StartsWith("ka".into())))),
        ("filter", "text like (regex)", f(and1(Col::Text, Op::Like(r"^ka.*_\d{3}\.jpg$".into())))),
        ("filter", "label equal", f(and1(Col::Label, Op::Equal(w7)))),
        ("filter", "tags containsAny", f(and1(Col::Tags, Op::ContainsAny(vec![3, 17])))),
        ("filter", "tags containsNot", f(and1(Col::Tags, Op::ContainsNot(vec![1])))),
        ("filter", "search box (text+tags)", f(FilterState { root: Node::And(vec![]), query: Some("lumi".into()) })),
        ("filter", "compound and/or", f(fstate(compound()))),
        ("sort", "number", so(vec![asc(Col::Number)])),
        ("sort", "score (float) desc", so(vec![desc(Col::Score)])),
        ("sort", "date", so(vec![asc(Col::Date)])),
        ("sort", "text", so(vec![asc(Col::Text)])),
        ("sort", "tags (count)", so(vec![asc(Col::Tags)])),
        ("sort", "label, score desc", so(vec![asc(Col::Label), desc(Col::Score)])),
        ("group", "number (10k values)", g(vec![lv(GKey::Num(Col::Number))])),
        ("group", "date by month", g(vec![lv(GKey::DateMonth)])),
        ("group", "label (300 values)", g(vec![lv(GKey::Str(Col::Label))])),
        ("group", "checkbox", g(vec![lv(GKey::Check)])),
        ("group", "tags (+parents)", g(vec![lv(GKey::Tags)])),
        ("group", "label > date by year", g(vec![lv(GKey::Str(Col::Label)), lv(GKey::DateYear)])),
        ("group", "text (~N values)", g(vec![lv(GKey::Str(Col::Text))])),
        ("pipeline", "compound > sort > tags", {
            let st = fstate(compound());
            let keys = vec![asc(Col::Label), desc(Col::Score)];
            let mut gm = GroupManager::new(vec![lv(GKey::Tags)]);
            Box::new(move |s: &[u32]| {
                let f = filter::filter(d, &st, s);
                let so = sort::sort(d, &keys, &f);
                Out::Tree(gm.group(d, &so))
            })
        }),
    ]
}

fn main() {
    let n: usize = arg("n").map_or(1_000_000, |v| v.parse().unwrap());
    let reps: usize = arg("reps").map_or(if n >= 5_000_000 { 3 } else { 5 }, |v| v.parse().unwrap());
    let warmup: usize = arg("warmup").map_or(1, |v| v.parse().unwrap());
    let only = arg("only").map(|r| regex::Regex::new(&r).unwrap());
    let skip = arg("skip").map(|r| regex::Regex::new(&r).unwrap());
    let all_threads = std::thread::available_parallelism().map_or(1, |p| p.get());
    // --mem: one run per op, reporting live heap bytes retained by the result and the heap peak.
    let mem = std::env::args().any(|a| a == "--mem");
    let exact_op = arg("op");
    TRACK.store(mem, Relaxed);
    let threads: Vec<usize> = arg("threads").map_or(vec![1, all_threads], |v| v.split(',').map(|t| t.parse().unwrap()).collect());

    if std::env::args().any(|a| a == "--list") {
        let d = data::generate(0);
        for (kind, op, _) in ops(&d) {
            println!("{kind}: {op}");
        }
        return;
    }

    let live0 = LIVE.load(Relaxed);
    let t0 = Instant::now();
    let d = data::generate(n);
    let live = if mem { format!(r#","live_bytes":{}"#, LIVE.load(Relaxed) - live0) } else { String::new() };
    println!(r#"{{"impl":"rust","meta":true,"n":{n},"gen_ms":{}{live}}}"#, t0.elapsed().as_millis());
    // --wait (set by memwatch): block until stdin says go, so the load is left out of the peak.
    if std::env::args().any(|a| a == "--wait") {
        std::io::stdin().read_line(&mut String::new()).unwrap();
    }

    // --lines: scroller line layout (see lines.rs) instead of the compute ops.
    if std::env::args().any(|a| a == "--lines") {
        let list = |name: &str, def: &str| arg(name).unwrap_or(def.into()).split(',').map(str::to_string).collect::<Vec<_>>();
        let trees = list("trees", "flat,label-year,tags,text,label-year-piles");
        let views = list("views", "grid,table");
        lines::run(&d, n, &trees, &views, &threads, reps, warmup);
        return;
    }

    // --wire=<dir>: payload sizes and encode cost (see wire.rs) instead of the compute ops.
    if let Some(dir) = arg("wire") {
        let wins: Vec<usize> = arg("win").map_or(vec![200, 500], |v| v.split(',').map(|w| w.parse().unwrap()).collect());
        wire::run(&d, n, std::path::Path::new(&dir), &wins, only.as_ref());
        return;
    }

    let all: Vec<u32> = (0..n as u32).collect();
    for &t in &threads {
        let pool = rayon::ThreadPoolBuilder::new().num_threads(t).build().unwrap();
        let name = format!("rust-{t}t");
        pool.install(|| {
            for (kind, op, mut f) in ops(&d) {
                let id = format!("{kind}: {op}");
                if only.as_ref().is_some_and(|r| !r.is_match(&id))
                    || skip.as_ref().is_some_and(|r| r.is_match(&id))
                    || exact_op.as_ref().is_some_and(|o| *o != id)
                {
                    continue;
                }
                if mem {
                    let base = LIVE.load(Relaxed);
                    PEAK.store(base, Relaxed);
                    let t0 = Instant::now();
                    let out = f(&all);
                    let ms = t0.elapsed().as_secs_f64() * 1000.0;
                    let (peak, retained) = (PEAK.load(Relaxed) - base, LIVE.load(Relaxed) - base);
                    let res = out.hash();
                    drop(out);
                    let entries = res.entries.map_or(String::new(), |e| format!(r#","entries":{e}"#));
                    println!(
                        r#"{{"impl":"{name}","n":{n},"kind":"{kind}","op":"{op}","mem":true,"ms":{ms:.3},"retained_bytes":{retained},"peak_bytes":{peak},"count":{}{entries},"hash":{}}}"#,
                        res.count, res.hash
                    );
                    continue;
                }
                let mut times = Vec::new();
                let mut res = None;
                for r in 0..warmup + reps {
                    let t0 = Instant::now();
                    let out = f(&all);
                    let dt = t0.elapsed().as_secs_f64() * 1000.0;
                    if r >= warmup {
                        times.push(dt);
                    }
                    res = Some(out.hash());
                    drop(out);
                }
                let res = res.unwrap();
                times.sort_by(|a, b| a.partial_cmp(b).unwrap());
                let entries = res.entries.map_or(String::new(), |e| format!(r#","entries":{e}"#));
                println!(
                    r#"{{"impl":"{name}","n":{n},"kind":"{kind}","op":"{op}","ms":{:.3},"min_ms":{:.3},"count":{}{entries},"hash":{}}}"#,
                    times[times.len() / 2],
                    times[0],
                    res.count,
                    res.hash
                );
            }
        });
    }
}
