//! Sorting — port of `src/core/SortManager.ts` (`buildSortCols` + `sortByPackedKey`).
//!
//! Per sort property a key is derived per slot exactly as the TS `sortParser` / fast paths do
//! (numbers: NaN → -Infinity; strings: lower-cased, missing → `LAST_STRING`; tags: first tag's
//! label; multi-tags: tag count; …). Keys compare numerically or by UTF-16 code units, the
//! direction applies per key, and ties keep the input order (the TS packed key embeds the input
//! position). An active plugin query's scores sort before every property.

use std::cmp::Ordering;

use rayon::prelude::*;
use rustc_hash::FxHashMap;
use serde::{Deserialize, Serialize};

use crate::Scores;
use crate::cancel::{CHUNK, CancelToken, Cancelled, PAR_THRESHOLD};
use crate::js::{self, Jv};
use crate::schema::{PropId, PropertyDef, PropertyType, Schema};
use crate::store::{ColRef, Slot, Snapshot};

pub const LAST_STRING: &str = "zzzzzzzzzzzzzzzzzzzzzzzzzzzz";

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SortOption {
    /// 1 ascending, -1 descending.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub direction: Option<i32>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SortState {
    #[serde(default)]
    pub sort_by: Vec<PropId>,
    #[serde(default)]
    pub options: FxHashMap<PropId, SortOption>,
}

impl SortState {
    /// `verifyState`: the sort keys on live properties.
    pub fn live_keys<'a>(&'a self, schema: &'a Schema) -> impl Iterator<Item = &'a PropertyDef> + 'a {
        self.sort_by.iter().filter_map(|id| schema.live_property(*id))
    }
}

/// A sort key column, indexed by input position.
pub(crate) enum KeyCol {
    Num(Vec<f64>),
    /// Dense rank of a string key (UTF-16 order).
    Rank(Vec<u32>),
}

/// Order-preserving u64 of an f64 (no NaN expected; -0 == +0).
#[inline]
pub(crate) fn f64_key(x: f64) -> u64 {
    let x = if x == 0.0 { 0.0 } else { x };
    let b = x.to_bits();
    if b >> 63 == 1 { !b } else { b ^ (1 << 63) }
}

fn par_map<T: Send>(slots: &[Slot], cancel: &CancelToken, f: impl Fn(Slot) -> T + Sync) -> Result<Vec<T>, Cancelled> {
    if slots.len() < PAR_THRESHOLD {
        cancel.check()?;
        return Ok(slots.iter().map(|&s| f(s)).collect());
    }
    let chunks: Result<Vec<Vec<T>>, Cancelled> = slots
        .par_chunks(CHUNK)
        .map(|c| {
            cancel.check()?;
            Ok(c.iter().map(|&s| f(s)).collect::<Vec<T>>())
        })
        .collect();
    Ok(chunks?.into_iter().flatten().collect())
}

/// Rank strings: `keys[code]` → dense rank in UTF-16 order (equal strings share a rank).
fn rank_strings(keys: &[String]) -> Vec<u32> {
    let mut idx: Vec<u32> = (0..keys.len() as u32).collect();
    idx.sort_by(|&a, &b| js::utf16_cmp(&keys[a as usize], &keys[b as usize]));
    let mut rank = vec![0u32; keys.len()];
    let mut r = 0u32;
    for i in 0..idx.len() {
        if i > 0 && keys[idx[i] as usize] != keys[idx[i - 1] as usize] {
            r += 1;
        }
        rank[idx[i] as usize] = r;
    }
    rank
}

fn is_numeric_sort(t: PropertyType) -> bool {
    use PropertyType::*;
    matches!(t, Checkbox | Color | Date | MultiTags | Number | Height | Width | Id)
}

/// `sortParser[type](raw)` for the numeric sort types, then `+v` with NaN → -Infinity.
fn numeric_parse(t: PropertyType, raw: Jv) -> f64 {
    use PropertyType::*;
    let v: Jv = match t {
        Checkbox => Jv::Num(if raw.truthy() { 1.0 } else { 0.0 }),
        Color => {
            // isNaN(x) ? -1 : x
            if js::to_number(&raw).is_nan() { Jv::Num(-1.0) } else { raw }
        }
        Date => {
            if !raw.truthy() {
                Jv::Num(0.0)
            } else {
                raw
            }
        }
        MultiTags => match raw {
            Jv::Tags(t) => Jv::Num(t.len() as f64),
            _ => Jv::Num(0.0),
        },
        Number => {
            if raw.is_nullish() {
                Jv::Num(f64::NEG_INFINITY)
            } else {
                raw
            }
        }
        _ => raw,
    };
    if v.is_nullish() {
        return f64::NEG_INFINITY;
    }
    let n = js::to_number(&v);
    if n.is_nan() { f64::NEG_INFINITY } else { n }
}

/// The string sort key of a raw value (non-numeric sort types, tag excepted).
fn string_parse(t: PropertyType, raw: Jv, schema: &Schema) -> String {
    use PropertyType::*;
    match t {
        Path | Text | Url | Tag => {
            if !raw.truthy() {
                LAST_STRING.into()
            } else {
                js::lower(&js::to_string(&raw)).into_owned()
            }
        }
        Folder => match raw {
            Jv::Num(x) => schema.folder_name(x as i64).filter(|_| x.fract() == 0.0).map(|s| s.to_string()).unwrap_or_else(|| LAST_STRING.into()),
            _ => LAST_STRING.into(),
        },
        _ => {
            if raw.is_nullish() {
                LAST_STRING.into()
            } else {
                js::to_string(&raw).into_owned()
            }
        }
    }
}

pub(crate) fn key_column(snap: &Snapshot, p: &PropertyDef, slots: &[Slot], cancel: &CancelToken) -> Result<KeyCol, Cancelled> {
    let col = snap.col(p.id);
    let schema = &snap.schema;
    if is_numeric_sort(p.ptype) {
        if let ColRef::Num(data) = col {
            // Float64Array fast path: NaN → -Infinity, no parser.
            return Ok(KeyCol::Num(par_map(slots, cancel, |s| {
                let v = data[s as usize];
                if v.is_nan() { f64::NEG_INFINITY } else { v }
            })?));
        }
        let t = p.ptype;
        return Ok(KeyCol::Num(par_map(slots, cancel, |s| numeric_parse(t, col.read(s)))?));
    }
    // String keys: computed once per distinct stored value, then ranked.
    match col {
        ColRef::Tags(c) if p.ptype == PropertyType::Tag => {
            // First tag's label in the property's registry, lower-cased; LAST_STRING otherwise.
            let mut labels: FxHashMap<i32, u32> = FxHashMap::default();
            let mut keys: Vec<String> = vec![LAST_STRING.into()];
            for t in schema.tags.values().filter(|t| t.property_id == p.id) {
                if !t.value.is_empty() {
                    labels.insert(t.id, keys.len() as u32);
                    keys.push(js::lower(&t.value).into_owned());
                }
            }
            let rank = rank_strings(&keys);
            Ok(KeyCol::Rank(par_map(slots, cancel, |s| {
                let tags = c.get(s);
                let k = tags.first().and_then(|t| labels.get(t)).copied().unwrap_or(0);
                rank[k as usize]
            })?))
        }
        ColRef::Str(c) => {
            let dict = &c.dict;
            let mut keys = Vec::with_capacity(dict.len());
            keys.push(string_parse(p.ptype, Jv::Null, schema));
            for code in 1..dict.len() as u32 {
                keys.push(string_parse(p.ptype, Jv::Str(dict.get(code).unwrap()), schema));
            }
            let rank = rank_strings(&keys);
            Ok(KeyCol::Rank(par_map(slots, cancel, |s| rank[c.codes[s as usize] as usize])?))
        }
        ColRef::Sha1(id) => {
            let dict = &id.sha1_dict;
            let mut keys = Vec::with_capacity(dict.len());
            keys.push(string_parse(p.ptype, Jv::Null, schema));
            for code in 1..dict.len() as u32 {
                keys.push(string_parse(p.ptype, Jv::Str(dict.get(code).unwrap()), schema));
            }
            let rank = rank_strings(&keys);
            Ok(KeyCol::Rank(par_map(slots, cancel, |s| rank[id.sha1[s as usize] as usize])?))
        }
        other => {
            // Generic: compute the string per slot (folder ids, tags for non-tag types, …),
            // then rank the distinct ones.
            let t = p.ptype;
            let strs: Vec<String> = par_map(slots, cancel, |s| string_parse(t, other.read(s), schema))?;
            let mut ids: FxHashMap<&str, u32> = FxHashMap::default();
            let mut keys: Vec<String> = Vec::new();
            let mut codes = Vec::with_capacity(strs.len());
            for s in &strs {
                let c = *ids.entry(s.as_str()).or_insert_with(|| {
                    keys.push(s.clone());
                    keys.len() as u32 - 1
                });
                codes.push(c);
            }
            let rank = rank_strings(&keys);
            Ok(KeyCol::Rank(codes.into_iter().map(|c| rank[c as usize]).collect()))
        }
    }
}

/// Order positions `0..n` by `cols` (direction per key), ties by position.
pub(crate) fn sort_positions(n: usize, cols: &[KeyCol], dirs: &[i32], cancel: &CancelToken) -> Result<Vec<u32>, Cancelled> {
    let key = |c: &KeyCol, i: usize, d: i32| -> u64 {
        let k = match c {
            KeyCol::Num(v) => f64_key(v[i]),
            KeyCol::Rank(v) => v[i] as u64,
        };
        if d < 0 { !k } else { k }
    };
    cancel.check()?;
    match cols.len() {
        0 => Ok((0..n as u32).collect()),
        1 => {
            let mut v: Vec<(u64, u32)> = (0..n).map(|i| (key(&cols[0], i, dirs[0]), i as u32)).collect();
            if n >= PAR_THRESHOLD { v.par_sort_unstable() } else { v.sort_unstable() }
            cancel.check()?;
            Ok(v.into_iter().map(|(_, i)| i).collect())
        }
        2 => {
            let mut v: Vec<(u64, u64, u32)> =
                (0..n).map(|i| (key(&cols[0], i, dirs[0]), key(&cols[1], i, dirs[1]), i as u32)).collect();
            if n >= PAR_THRESHOLD { v.par_sort_unstable() } else { v.sort_unstable() }
            cancel.check()?;
            Ok(v.into_iter().map(|(_, _, i)| i).collect())
        }
        _ => {
            let keys: Vec<Vec<u64>> = cols.iter().zip(dirs).map(|(c, &d)| (0..n).map(|i| key(c, i, d)).collect()).collect();
            let cmp = |a: &u32, b: &u32| -> Ordering {
                for k in &keys {
                    match k[*a as usize].cmp(&k[*b as usize]) {
                        Ordering::Equal => continue,
                        o => return o,
                    }
                }
                a.cmp(b)
            };
            let mut v: Vec<u32> = (0..n as u32).collect();
            if n >= PAR_THRESHOLD { v.par_sort_unstable_by(cmp) } else { v.sort_unstable_by(cmp) }
            cancel.check()?;
            Ok(v)
        }
    }
}

/// Sort `slots` (the filter output) by `state`, with `scores` (an active plugin query's)
/// first when present.
pub fn sort(snap: &Snapshot, state: &SortState, slots: &[Slot], scores: Option<&Scores>, cancel: &CancelToken) -> Result<Vec<Slot>, Cancelled> {
    let mut cols: Vec<KeyCol> = Vec::new();
    let mut dirs: Vec<i32> = Vec::new();
    if let Some(sc) = scores {
        let missing = if sc.max_is_best { f64::NEG_INFINITY } else { f64::INFINITY };
        let ids = &snap.identity.ids;
        cols.push(KeyCol::Num(par_map(slots, cancel, |s| match sc.value_index.get(&ids[s as usize]) {
            Some(v) if !v.is_nan() => *v,
            _ => missing,
        })?));
        dirs.push(if sc.max_is_best { -1 } else { 1 });
    }
    for p in state.live_keys(&snap.schema) {
        cols.push(key_column(snap, p, slots, cancel)?);
        // `options[id].direction === Ascending ? 1 : -1`: an option without a direction is
        // descending. (A missing option threw in TS; here it sorts ascending.)
        let d = state.options.get(&p.id).map(|o| if o.direction == Some(1) { 1 } else { -1 }).unwrap_or(1);
        dirs.push(d);
    }
    if cols.is_empty() {
        return Ok(slots.to_vec());
    }
    let order = sort_positions(slots.len(), &cols, &dirs, cancel)?;
    Ok(order.into_iter().map(|i| slots[i as usize]).collect())
}
