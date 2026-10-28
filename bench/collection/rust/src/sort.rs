//! Multi-key sort with SortManager.ts semantics (no value = -inf for numbers, LAST_STRING for
//! strings, lowercased string compare, ties by input position). Every key column becomes an
//! order-preserving integer; the keys and the position are packed into one u64/u128 and sorted
//! with a plain integer sort.

use rayon::prelude::*;

use crate::data::{Col, Data, LAST_STRING, f64_key};

pub struct SortKey {
    pub col: Col,
    pub dir: i32,
}

fn bits_for(n: u64) -> u32 {
    64 - n.saturating_sub(1).leading_zeros().min(64)
}

/// One key column: a value per input position, and how many bits it uses.
struct KeyCol {
    vals: Vec<u64>,
    bits: u32,
}

fn key_column(d: &Data, k: &SortKey, slots: &[u32]) -> KeyCol {
    let desc = k.dir < 0;
    match k.col {
        Col::Number | Col::Score | Col::Date => {
            let v = d.f64_col(k.col);
            let vals = slots
                .par_iter()
                .with_min_len(1 << 14)
                .map(|&s| {
                    let x = v[s as usize];
                    let key = f64_key(if x.is_nan() { f64::NEG_INFINITY } else { x });
                    if desc { !key } else { key }
                })
                .collect();
            KeyCol { vals, bits: 64 }
        }
        Col::Text | Col::Label => {
            // Dense rank of every dictionary code by lowercased value (code 0 = LAST_STRING).
            let sc = d.str_col(k.col);
            let s = |c: u32| if c == 0 { LAST_STRING } else { &sc.lower[c as usize] };
            let mut order: Vec<u32> = (0..sc.lower.len() as u32).collect();
            order.par_sort_unstable_by(|&a, &b| s(a).cmp(s(b)));
            let mut rank = vec![0u32; order.len()];
            let mut r = 0u32;
            for i in 0..order.len() {
                if i > 0 && s(order[i]) != s(order[i - 1]) {
                    r += 1;
                }
                rank[order[i] as usize] = r;
            }
            let max = r as u64;
            let codes = &sc.codes;
            let vals = slots
                .par_iter()
                .with_min_len(1 << 14)
                .map(|&sl| {
                    let x = rank[codes[sl as usize] as usize] as u64;
                    if desc { max - x } else { x }
                })
                .collect();
            KeyCol { vals, bits: bits_for(max + 1) }
        }
        Col::Tags => {
            // multi_tags sorts by the number of tags.
            let vals = slots
                .par_iter()
                .with_min_len(1 << 14)
                .map(|&s| {
                    let n = d.tags.get(s).len() as u64;
                    if desc { 255 - n } else { n }
                })
                .collect();
            KeyCol { vals, bits: 8 }
        }
        Col::Check => unimplemented!(),
    }
}

pub fn sort(d: &Data, keys: &[SortKey], slots: &[u32]) -> Vec<u32> {
    let n = slots.len();
    if keys.is_empty() || n == 0 {
        return slots.to_vec();
    }
    let cols: Vec<KeyCol> = keys.iter().map(|k| key_column(d, k, slots)).collect();
    let pos_bits = bits_for(n as u64);
    let total: u32 = cols.iter().map(|c| c.bits).sum::<u32>() + pos_bits;

    if total <= 64 {
        let mut packed: Vec<u64> = (0..n)
            .into_par_iter()
            .with_min_len(1 << 14)
            .map(|i| {
                let mut k = 0u64;
                for c in &cols {
                    k = (k << c.bits) | c.vals[i];
                }
                (k << pos_bits) | i as u64
            })
            .collect();
        packed.par_sort_unstable();
        let m = (1u64 << pos_bits) - 1;
        packed.par_iter().map(|&k| slots[(k & m) as usize]).collect()
    } else if total <= 128 {
        let mut packed: Vec<u128> = (0..n)
            .into_par_iter()
            .with_min_len(1 << 14)
            .map(|i| {
                let mut k = 0u128;
                for c in &cols {
                    k = (k << c.bits) | c.vals[i] as u128;
                }
                (k << pos_bits) | i as u128
            })
            .collect();
        packed.par_sort_unstable();
        let m = (1u128 << pos_bits) - 1;
        packed.par_iter().map(|&k| slots[(k & m) as usize]).collect()
    } else {
        let mut idx: Vec<u32> = (0..n as u32).collect();
        idx.par_sort_unstable_by(|&a, &b| {
            for c in &cols {
                let o = c.vals[a as usize].cmp(&c.vals[b as usize]);
                if o.is_ne() {
                    return o;
                }
            }
            a.cmp(&b)
        });
        idx.par_iter().map(|&i| slots[i as usize]).collect()
    }
}
