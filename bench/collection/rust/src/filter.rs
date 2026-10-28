//! Filter: same semantics as FilterManager.ts (mask narrowed leaf by leaf, OR groups collect
//! passes over a todo mask), on Rust columns. String predicates run once per dictionary entry,
//! then each slot is a table lookup.

use memchr::memmem;
use rayon::prelude::*;
use regex::Regex;

use crate::data::{Col, Data, N_TAGS, StrCol};

pub enum Op {
    IsSet,
    Greater(f64),
    Leq(f64),
    IsTrue,
    Contains(String),
    StartsWith(String),
    Like(String),
    Equal(String),
    ContainsAny(Vec<u32>),
    ContainsNot(Vec<u32>),
}

pub enum Node {
    Leaf(Col, Op),
    And(Vec<Node>),
    Or(Vec<Node>),
}

pub struct FilterState {
    pub root: Node,
    pub query: Option<String>,
}

const MIN_LEN: usize = 1 << 14;

#[inline]
fn narrow<F: Fn(u32) -> bool + Sync + Send>(slots: &[u32], mask: &mut [bool], f: F) {
    mask.par_iter_mut().zip(slots.par_iter()).with_min_len(MIN_LEN).for_each(|(m, &s)| {
        if *m && !f(s) {
            *m = false
        }
    });
}

/// `pred` evaluated once per dictionary code (`None` = no value).
fn dict_table(col: &StrCol, pred: impl Fn(Option<&str>) -> bool + Sync + Send) -> Vec<bool> {
    (0..col.lower.len())
        .into_par_iter()
        .with_min_len(4096)
        .map(|c| pred(if c == 0 { None } else { Some(&col.lower[c]) }))
        .collect()
}

fn tag_table(d: &Data, tags: &[u32]) -> Vec<bool> {
    let mut t = vec![false; N_TAGS + 1];
    for &v in tags {
        t[v as usize] = true;
        for &c in &d.tag_defs[v as usize].all_children {
            t[c as usize] = true;
        }
    }
    t
}

fn apply_leaf(d: &Data, col: Col, op: &Op, slots: &[u32], mask: &mut [bool]) {
    match (col, op) {
        (Col::Number | Col::Score | Col::Date, op) => {
            let v = d.f64_col(col);
            match *op {
                Op::IsSet => narrow(slots, mask, |s| !v[s as usize].is_nan()),
                Op::Greater(b) => narrow(slots, mask, |s| v[s as usize] > b), // NaN > b is false
                Op::Leq(b) => narrow(slots, mask, |s| v[s as usize] <= b),
                _ => unimplemented!(),
            }
        }
        (Col::Check, Op::IsTrue) => narrow(slots, mask, |s| d.check[s as usize] == 1),
        (Col::Text | Col::Label, op) => {
            let sc = d.str_col(col);
            let tbl = match op {
                Op::Contains(b) if !b.is_empty() => {
                    let f = memmem::Finder::new(&b.to_lowercase()).into_owned();
                    dict_table(sc, |a| a.is_some_and(|a| f.find(a.as_bytes()).is_some()))
                }
                Op::StartsWith(b) if !b.is_empty() => {
                    let b = b.to_lowercase();
                    dict_table(sc, |a| a.is_some_and(|a| a.starts_with(&b)))
                }
                Op::Like(b) if !b.is_empty() => {
                    let re = Regex::new(&b.to_lowercase()).unwrap();
                    dict_table(sc, |a| a.is_some_and(|a| re.is_match(a)))
                }
                Op::Equal(b) if !b.is_empty() => {
                    let b = b.to_lowercase();
                    dict_table(sc, |a| a.is_some_and(|a| a == b))
                }
                _ => return, // empty filter value passes everything
            };
            let codes = &sc.codes;
            narrow(slots, mask, |s| tbl[codes[s as usize] as usize]);
        }
        (Col::Tags, Op::ContainsAny(v)) if !v.is_empty() => {
            let t = tag_table(d, v);
            narrow(slots, mask, |s| d.tags.get(s).iter().any(|&x| t[x as usize]));
        }
        (Col::Tags, Op::ContainsNot(v)) if !v.is_empty() => {
            let t = tag_table(d, v);
            narrow(slots, mask, |s| !d.tags.get(s).iter().any(|&x| t[x as usize]));
        }
        _ => {}
    }
}

fn apply_node(d: &Data, n: &Node, slots: &[u32], mask: &mut [bool]) {
    match n {
        Node::Leaf(c, op) => apply_leaf(d, *c, op, slots, mask),
        Node::And(children) => {
            for c in children {
                apply_node(d, c, slots, mask);
            }
        }
        Node::Or(children) => {
            if children.is_empty() {
                return;
            }
            let mut todo = mask.to_vec();
            mask.par_iter_mut().with_min_len(MIN_LEN).for_each(|m| *m = false);
            for c in children {
                if !todo.par_iter().any(|&t| t) {
                    break;
                }
                let mut work = todo.clone();
                apply_node(d, c, slots, &mut work);
                mask.par_iter_mut().zip(todo.par_iter_mut()).zip(work.par_iter()).with_min_len(MIN_LEN).for_each(
                    |((m, t), &w)| {
                        if w {
                            *m = true;
                            *t = false;
                        }
                    },
                );
            }
        }
    }
}

/// The search box: every string column, then the labels of the slot's tags.
fn apply_query(d: &Data, q: &str, slots: &[u32], mask: &mut [bool]) {
    let f = memmem::Finder::new(&q.to_lowercase()).into_owned();
    let hit = |a: Option<&str>| a.is_some_and(|a| f.find(a.as_bytes()).is_some());
    let text = dict_table(&d.text, hit);
    let label = dict_table(&d.label, hit);
    let tags: Vec<bool> = d.tag_defs.iter().map(|t| f.find(t.lower.as_bytes()).is_some()).collect();
    let (tc, lc) = (&d.text.codes, &d.label.codes);
    narrow(slots, mask, |s| {
        let i = s as usize;
        text[tc[i] as usize] || label[lc[i] as usize] || d.tags.get(s).iter().any(|&t| tags[t as usize])
    });
}

pub fn filter(d: &Data, state: &FilterState, slots: &[u32]) -> Vec<u32> {
    let mut mask = vec![true; slots.len()];
    if let Some(q) = &state.query {
        if !q.is_empty() {
            apply_query(d, q, slots, &mut mask);
        }
    }
    apply_node(d, &state.root, slots, &mut mask);
    slots.par_iter().zip(mask.par_iter()).with_min_len(MIN_LEN).filter(|(_, m)| **m).map(|(s, _)| *s).collect()
}
