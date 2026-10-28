//! Group: same tree as GroupManager.computePropertySubGroup (one bucket per value, tags expanded
//! to their parents, date steps, children sorted by value, stable ids from a persistent value
//! index, a slot -> leaf membership index). Buckets are built with a stable counting sort, so a
//! bucket's slots keep the input (sorted) order.

use std::cmp::Ordering;
use std::sync::atomic::{AtomicU32, Ordering::Relaxed};

use rayon::prelude::*;
use rustc_hash::FxHashMap;

use crate::data::{Col, Data, LAST_STRING, N_TAGS, SyncPtr};

#[derive(Clone)]
pub enum GKey {
    Num(Col),
    DateMonth,
    DateYear,
    Str(Col),
    Check,
    Tags,
}

#[derive(Clone)]
pub struct Level {
    pub key: GKey,
    pub dir: i32,
}

pub const NONE: u64 = u64::MAX;

#[derive(Clone, Default)]
pub struct Node {
    pub id: u32,
    /// Bucket value key (`NONE` for the empty bucket); see `bucketize` for the encoding.
    pub key: u64,
    pub first_child: u32,
    pub n_children: u32,
    /// Leaves: range in `Tree::slots`. Inner nodes: `len` is the slot count.
    pub start: u32,
    pub len: u32,
    pub order: u32,
}

#[allow(dead_code)] // root_slots mirrors root.slots = Array.from(slots)
pub struct Tree {
    pub nodes: Vec<Node>,
    pub root_slots: Vec<u32>,
    pub slots: Vec<u32>,
    /// slot -> leaf node indices (CSR), the `imageToGroups` equivalent.
    pub member_offsets: Vec<u32>,
    pub member_values: Vec<u32>,
}

pub struct GroupManager {
    pub levels: Vec<Level>,
    value_index: FxHashMap<(u32, u64), u32>,
    next_id: u32,
}

/// Slots of one parent split into buckets: `out` holds the slots bucket after bucket.
struct Buckets {
    out: Vec<u32>,
    /// (value key, start, len) of every non-empty bucket.
    kids: Vec<(u64, u32, u32)>,
}

fn threads() -> usize {
    rayon::current_num_threads()
}

/// Stable counting sort of `slots` by `ids` (dense, < b).
fn counting(slots: &[u32], ids: &[u32], b: usize, key_of: impl Fn(usize) -> u64) -> Buckets {
    let n = slots.len();
    let mut nchunks = (threads() * 4).min(n / (1 << 14)).max(1);
    if b * nchunks > 1 << 22 {
        nchunks = 1;
    }
    let chunk = n.div_ceil(nchunks).max(1);
    let hists: Vec<Vec<u32>> = ids
        .par_chunks(chunk)
        .map(|c| {
            let mut h = vec![0u32; b];
            for &i in c {
                h[i as usize] += 1;
            }
            h
        })
        .collect();
    let mut cursors: Vec<Vec<u32>> = vec![vec![0u32; b]; hists.len()];
    let mut kids = Vec::new();
    let mut run = 0u32;
    for k in 0..b {
        let start = run;
        for (c, h) in hists.iter().enumerate() {
            cursors[c][k] = run;
            run += h[k];
        }
        if run > start {
            kids.push((key_of(k), start, run - start));
        }
    }
    let mut out = vec![0u32; n];
    let ptr = SyncPtr(out.as_mut_ptr());
    ids.par_chunks(chunk).zip(slots.par_chunks(chunk)).zip(cursors.par_iter_mut()).for_each(|((ic, sc), cur)| {
        for (&i, &s) in ic.iter().zip(sc) {
            let p = &mut cur[i as usize];
            // SAFETY: every (chunk, bucket) owns a disjoint range of `out`.
            unsafe { ptr.write(*p as usize, s) };
            *p += 1;
        }
    });
    Buckets { out, kids }
}

/// Dense ids for arbitrary u64 keys, in first-seen order. Chunk-local hash maps, merged once.
fn dense_ids(keys: &[u64]) -> (Vec<u32>, Vec<u64>) {
    let chunk = 1 << 16;
    let locals: Vec<(Vec<u32>, Vec<u64>)> = keys
        .par_chunks(chunk)
        .map(|c| {
            let mut m: FxHashMap<u64, u32> = FxHashMap::default();
            let mut uniq = Vec::new();
            let ids = c
                .iter()
                .map(|&k| {
                    *m.entry(k).or_insert_with(|| {
                        uniq.push(k);
                        uniq.len() as u32 - 1
                    })
                })
                .collect();
            (ids, uniq)
        })
        .collect();
    let mut global: FxHashMap<u64, u32> = FxHashMap::default();
    let mut uniq = Vec::new();
    let remaps: Vec<Vec<u32>> = locals
        .iter()
        .map(|(_, lu)| {
            lu.iter()
                .map(|&k| {
                    *global.entry(k).or_insert_with(|| {
                        uniq.push(k);
                        uniq.len() as u32 - 1
                    })
                })
                .collect()
        })
        .collect();
    let mut ids = vec![0u32; keys.len()];
    ids.par_chunks_mut(chunk).zip(locals.par_iter()).zip(remaps.par_iter()).for_each(|((o, (l, _)), r)| {
        for (o, &l) in o.iter_mut().zip(l) {
            *o = r[l as usize];
        }
    });
    (ids, uniq)
}

/// Bucket by an arbitrary u64 key per slot.
fn by_keys(slots: &[u32], keys: Vec<u64>) -> Buckets {
    let (ids, uniq) = dense_ids(&keys);
    counting(slots, &ids, uniq.len(), |k| uniq[k])
}

fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = y - era * 400;
    let mp = (m + 9) % 12;
    let doy = (153 * mp + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
}

fn civil_from_days(z: i64) -> (i64, i64) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (if m <= 2 { y + 1 } else { y }, m)
}

/// UTC (year*12 + month0) or year of an epoch-ms date.
fn date_key(ms: f64, month: bool) -> u64 {
    if ms.is_nan() || ms == 0.0 {
        return NONE;
    }
    let (y, m) = civil_from_days((ms / 86_400_000.0).floor() as i64);
    (if month { y * 12 + m - 1 } else { y }) as u64
}

fn bucketize(d: &Data, key: &GKey, slots: &[u32]) -> Buckets {
    let n = slots.len();
    let dense = |ids: Vec<u32>, b: usize, key_of: &dyn Fn(usize) -> u64| {
        if b > 2 * n + 1024 {
            // Few slots over a large dictionary: compress the ids first.
            by_keys(slots, ids.into_iter().map(|i| key_of(i as usize)).collect())
        } else {
            counting(slots, &ids, b, key_of)
        }
    };
    let par_map = |f: &(dyn Fn(u32) -> u32 + Sync)| -> Vec<u32> { slots.par_iter().with_min_len(1 << 14).map(|&s| f(s)).collect() };
    match key {
        GKey::Str(c) => {
            let sc = d.str_col(*c);
            let ids = par_map(&|s| sc.codes[s as usize]);
            dense(ids, sc.dict.len(), &|k| if k == 0 { NONE } else { k as u64 })
        }
        GKey::Check => {
            // null and false share the `false` bucket (valueParser.checkbox).
            let ids = par_map(&|s| (d.check[s as usize] == 1) as u32);
            dense(ids, 2, &|k| k as u64)
        }
        GKey::Num(c) => {
            let v = d.f64_col(*c);
            let keys = slots
                .par_iter()
                .with_min_len(1 << 14)
                .map(|&s| {
                    let x = v[s as usize];
                    if x.is_nan() { NONE } else { (x + 0.0).to_bits() }
                })
                .collect();
            by_keys(slots, keys)
        }
        GKey::DateMonth | GKey::DateYear => {
            let month = matches!(key, GKey::DateMonth);
            let keys: Vec<u64> = slots.par_iter().with_min_len(1 << 14).map(|&s| date_key(d.date[s as usize], month)).collect();
            let (lo, hi) = keys
                .par_iter()
                .filter(|&&k| k != NONE)
                .fold(|| (u64::MAX, 0), |(a, b), &k| (a.min(k), b.max(k)))
                .reduce(|| (u64::MAX, 0), |(a, b), (c, e)| (a.min(c), b.max(e)));
            if lo > hi {
                return counting(slots, &vec![0; n], 1, |_| NONE);
            }
            let ids = keys.par_iter().with_min_len(1 << 14).map(|&k| if k == NONE { 0 } else { (k - lo + 1) as u32 }).collect::<Vec<_>>();
            dense(ids, (hi - lo + 2) as usize, &|k| if k == 0 { NONE } else { k as u64 - 1 + lo })
        }
        GKey::Tags => tag_buckets(d, slots),
    }
}

/// Tag buckets: each slot joins the bucket of every tag it has and of all their parents (once),
/// or the empty bucket (0) when it has no tags.
fn tag_buckets(d: &Data, slots: &[u32]) -> Buckets {
    let b = N_TAGS + 1;
    let expand: Vec<Vec<u32>> = d
        .tag_defs
        .iter()
        .enumerate()
        .map(|(id, t)| {
            let mut v = t.all_parents.clone();
            v.push(id as u32);
            v
        })
        .collect();
    let n = slots.len();
    let nchunks = (threads() * 4).min(n / (1 << 14)).max(1);
    let chunk = n.div_ceil(nchunks).max(1);
    let each = |c: &[u32], f: &mut dyn FnMut(u32, usize)| {
        let mut stamp = vec![u32::MAX; b];
        for (i, &s) in c.iter().enumerate() {
            let tags = d.tags.get(s);
            if tags.is_empty() {
                f(s, 0);
                continue;
            }
            for &t in tags {
                for &p in &expand[t as usize] {
                    if stamp[p as usize] != i as u32 {
                        stamp[p as usize] = i as u32;
                        f(s, p as usize);
                    }
                }
            }
        }
    };
    let hists: Vec<Vec<u32>> = slots
        .par_chunks(chunk)
        .map(|c| {
            let mut h = vec![0u32; b];
            each(c, &mut |_, k| h[k] += 1);
            h
        })
        .collect();
    let mut cursors: Vec<Vec<u32>> = vec![vec![0u32; b]; hists.len()];
    let mut kids = Vec::new();
    let mut run = 0u32;
    for k in 0..b {
        let start = run;
        for (c, h) in hists.iter().enumerate() {
            cursors[c][k] = run;
            run += h[k];
        }
        if run > start {
            kids.push((if k == 0 { NONE } else { k as u64 }, start, run - start));
        }
    }
    let mut out = vec![0u32; run as usize];
    let ptr = SyncPtr(out.as_mut_ptr());
    slots.par_chunks(chunk).zip(cursors.par_iter_mut()).for_each(|(c, cur)| {
        each(c, &mut |s, k| {
            // SAFETY: every (chunk, bucket) owns a disjoint range of `out`.
            unsafe { ptr.write(cur[k] as usize, s) };
            cur[k] += 1;
        })
    });
    Buckets { out, kids }
}

enum SortVal<'a> {
    F(f64),
    S(&'a str),
}

/// GroupManager's sortGroupByProperty value of a bucket.
fn sort_val<'a>(d: &'a Data, key: &GKey, k: u64) -> SortVal<'a> {
    match key {
        GKey::Num(_) => SortVal::F(if k == NONE { f64::NEG_INFINITY } else { f64::from_bits(k) }),
        GKey::DateMonth if k != NONE => {
            let (y, m) = ((k / 12) as i64, (k % 12) as i64);
            SortVal::F((days_from_civil(y, m + 1, 1) * 86_400_000) as f64)
        }
        GKey::DateYear if k != NONE => SortVal::F((days_from_civil(k as i64, 1, 1) * 86_400_000) as f64),
        GKey::DateMonth | GKey::DateYear => SortVal::F(0.0),
        GKey::Check => SortVal::F(k as f64),
        GKey::Str(c) => SortVal::S(if k == NONE { LAST_STRING } else { &d.str_col(*c).lower[k as usize] }),
        GKey::Tags => SortVal::S(if k == NONE { LAST_STRING } else { &d.tag_defs[k as usize].lower }),
    }
}

fn cmp_val(a: &SortVal, b: &SortVal) -> Ordering {
    match (a, b) {
        (SortVal::F(a), SortVal::F(b)) => a.partial_cmp(b).unwrap(),
        (SortVal::S(a), SortVal::S(b)) => a.cmp(b),
        _ => unreachable!(),
    }
}

struct Plan {
    out: Vec<u32>,
    kids: Vec<(u64, u32, u32)>,
    subs: Vec<Plan>,
}

fn plan(d: &Data, levels: &[Level], slots: &[u32]) -> Plan {
    let lvl = &levels[0];
    let Buckets { out, mut kids } = bucketize(d, &lvl.key, slots);
    let mut vals: Vec<(SortVal, (u64, u32, u32))> = kids.drain(..).map(|k| (sort_val(d, &lvl.key, k.0), k)).collect();
    if vals.len() > 1 << 14 {
        vals.par_sort_by(|a, b| if lvl.dir < 0 { cmp_val(&b.0, &a.0) } else { cmp_val(&a.0, &b.0) });
    } else {
        vals.sort_by(|a, b| if lvl.dir < 0 { cmp_val(&b.0, &a.0) } else { cmp_val(&a.0, &b.0) });
    }
    let kids: Vec<(u64, u32, u32)> = vals.into_iter().map(|v| v.1).collect();
    let subs = if levels.len() > 1 {
        kids.par_iter().map(|&(_, s, l)| plan(d, &levels[1..], &out[s as usize..(s + l) as usize])).collect()
    } else {
        Vec::new()
    };
    Plan { out, kids, subs }
}

impl GroupManager {
    pub fn new(levels: Vec<Level>) -> Self {
        GroupManager { levels, value_index: FxHashMap::default(), next_id: 1 }
    }

    fn assemble(&mut self, p: Plan, parent: usize, tree: &mut Tree) {
        let parent_id = tree.nodes[parent].id;
        let first = tree.nodes.len();
        let base = tree.slots.len() as u32;
        let leaf = p.subs.is_empty();
        if leaf {
            tree.slots.extend_from_slice(&p.out);
        }
        for &(key, start, len) in &p.kids {
            let next = &mut self.next_id;
            let id = *self.value_index.entry((parent_id, key)).or_insert_with(|| {
                *next += 1;
                *next - 1
            });
            tree.nodes.push(Node { id, key, start: if leaf { base + start } else { 0 }, len, ..Default::default() });
        }
        tree.nodes[parent].first_child = first as u32;
        tree.nodes[parent].n_children = p.kids.len() as u32;
        for (i, sub) in p.subs.into_iter().enumerate() {
            self.assemble(sub, first + i, tree);
        }
    }

    pub fn group(&mut self, d: &Data, slots: &[u32]) -> Tree {
        let mut tree = Tree {
            nodes: vec![Node { id: 0, len: slots.len() as u32, ..Default::default() }],
            root_slots: slots.to_vec(),
            slots: Vec::new(),
            member_offsets: Vec::new(),
            member_values: Vec::new(),
        };
        let p = plan(d, &self.levels, slots);
        self.assemble(p, 0, &mut tree);

        // setOrder: DFS display order.
        let mut stack = vec![0usize];
        let mut order = 0u32;
        while let Some(i) = stack.pop() {
            tree.nodes[i].order = order;
            order += 1;
            let (f, c) = (tree.nodes[i].first_child as usize, tree.nodes[i].n_children as usize);
            stack.extend((f..f + c).rev());
        }

        // slot -> leaves membership (CSR).
        let max_slot = slots.par_iter().copied().max().unwrap_or(0) as usize;
        let leaves: Vec<u32> = (1..tree.nodes.len() as u32).filter(|&i| tree.nodes[i as usize].n_children == 0).collect();
        let counts: Vec<AtomicU32> = (0..max_slot + 2).map(|_| AtomicU32::new(0)).collect();
        let leaf_slots = |l: u32| {
            let n = &tree.nodes[l as usize];
            &tree.slots[n.start as usize..(n.start + n.len) as usize]
        };
        leaves.par_iter().for_each(|&l| {
            for &s in leaf_slots(l) {
                counts[s as usize + 1].fetch_add(1, Relaxed);
            }
        });
        let mut offsets: Vec<u32> = counts.into_iter().map(|c| c.into_inner()).collect();
        for i in 1..offsets.len() {
            offsets[i] += offsets[i - 1];
        }
        let cursor: Vec<AtomicU32> = offsets.iter().map(|&o| AtomicU32::new(o)).collect();
        let mut values = vec![0u32; *offsets.last().unwrap() as usize];
        let ptr = SyncPtr(values.as_mut_ptr());
        leaves.par_iter().for_each(|&l| {
            for &s in leaf_slots(l) {
                let at = cursor[s as usize].fetch_add(1, Relaxed);
                // SAFETY: fetch_add hands out every index once.
                unsafe { ptr.write(at as usize, l) };
            }
        });
        tree.member_offsets = offsets;
        tree.member_values = values;
        tree
    }
}
