//! Filtering — port of `src/core/FilterManager.ts` (`filterSlots` and the operator table).
//!
//! Semantics kept from the TS engine:
//! * the order of evaluation does not change the result (every step only clears bits): text
//!   query, then folders, then the filter tree;
//! * numeric columns (number / date / color / width / height) use the typed fast path: the
//!   filter value goes through `Number(v)` (`+new Date(v)` for dates) once, a NaN value or an
//!   absent one passes everything, a missing cell fails every comparison but `equalNot`;
//! * `text` properties compare lower-cased cell and filter values; every other non-numeric
//!   type goes through the generic operator table with JS loose semantics;
//! * tag operators expand each filter tag to `{tag} ∪ allChildren`.
//!
//! String predicates are evaluated once per dictionary entry, not once per slot.

use rayon::prelude::*;
use regex::Regex;
use rustc_hash::FxHashSet;
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;

use crate::cancel::{CancelToken, Cancelled, CHUNK, PAR_THRESHOLD};
use crate::js::{self, Jv};
use crate::schema::{InstanceId, PropId, PropertyType, Schema, TagId};
use crate::store::{ColRef, Slot, Snapshot, StrColumn};
use crate::Scores;

// ── state (field-compatible with the TS FilterState JSON) ────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum FilterOperator {
    #[serde(rename = "equal")]
    Equal,
    #[serde(rename = "equalNot")]
    EqualNot,
    #[serde(rename = "like")]
    Like,
    #[serde(rename = "notLike")]
    NotLike,
    #[serde(rename = "lower")]
    Lower,
    #[serde(rename = "leq")]
    Leq,
    #[serde(rename = "greater")]
    Greater,
    #[serde(rename = "geq")]
    Geq,
    #[serde(rename = "isTrue")]
    IsTrue,
    #[serde(rename = "isFalse")]
    IsFalse,
    #[serde(rename = "contains")]
    Contains,
    #[serde(rename = "startsWith")]
    StartsWith,
    #[serde(rename = "containsAny")]
    ContainsAny,
    #[serde(rename = "containsAll")]
    ContainsAll,
    #[serde(rename = "containsNot")]
    ContainsNot,
    #[serde(rename = "and")]
    And,
    #[serde(rename = "or")]
    Or,
    #[serde(rename = "isSet")]
    IsSet,
    #[serde(rename = "notSet")]
    NotSet,
    #[serde(other)]
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Filter {
    #[serde(default)]
    pub id: i64,
    pub property_id: PropId,
    pub operator: FilterOperator,
    #[serde(default)]
    pub value: Value,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub is_group: Option<bool>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FilterGroup {
    #[serde(default)]
    pub id: i64,
    pub filters: Vec<FilterNode>,
    pub group_operator: FilterOperator,
    #[serde(default)]
    pub depth: i64,
    pub is_group: bool,
}

impl Default for FilterGroup {
    fn default() -> Self {
        FilterGroup { id: -1, filters: vec![], group_operator: FilterOperator::And, depth: 0, is_group: true }
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RawGroup {
    #[serde(default)]
    id: i64,
    #[serde(default)]
    filters: Vec<FilterNode>,
    #[serde(default = "and_op")]
    group_operator: FilterOperator,
    #[serde(default)]
    depth: i64,
}

fn and_op() -> FilterOperator {
    FilterOperator::And
}

impl<'de> Deserialize<'de> for FilterGroup {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let r = RawGroup::deserialize(d)?;
        Ok(FilterGroup { id: r.id, filters: r.filters, group_operator: r.group_operator, depth: r.depth, is_group: true })
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(untagged)]
pub enum FilterNode {
    Group(FilterGroup),
    Leaf(Filter),
}

impl<'de> Deserialize<'de> for FilterNode {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let v = Value::deserialize(d)?;
        let is_group = v.get("isGroup").and_then(Value::as_bool).unwrap_or(false) || v.get("filters").is_some();
        if is_group {
            FilterGroup::deserialize(v).map(FilterNode::Group).map_err(serde::de::Error::custom)
        } else {
            Filter::deserialize(v).map(FilterNode::Leaf).map_err(serde::de::Error::custom)
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TextQuery {
    #[serde(rename = "type", default = "text_type")]
    pub kind: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ctx: Option<Value>,
}

fn text_type() -> String {
    "text".into()
}

impl Default for TextQuery {
    fn default() -> Self {
        TextQuery { kind: "text".into(), text: Some(String::new()), ctx: None }
    }
}

impl TextQuery {
    pub fn is_active(&self) -> bool {
        self.text.as_deref().is_some_and(|t| !t.is_empty())
    }
    /// A query answered by a plugin on the backend (neither `text` nor `regex`).
    pub fn is_plugin(&self) -> bool {
        self.is_active() && self.kind != "text" && self.kind != "regex"
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct FilterState {
    #[serde(default)]
    pub folders: Vec<i64>,
    #[serde(default)]
    pub filter: FilterGroup,
    #[serde(default)]
    pub query: TextQuery,
}

/// The answer of a plugin text query (`apiCallActions` → `result.groups[0]`), provided by the
/// caller since the engine does no IO.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PluginQueryResult {
    #[serde(default)]
    pub sha1s: Vec<String>,
    #[serde(default)]
    pub ids: Option<Vec<InstanceId>>,
    #[serde(default)]
    pub scores: Option<PluginScores>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PluginScores {
    #[serde(default)]
    pub values: Vec<f64>,
    #[serde(default)]
    pub min: f64,
    #[serde(default)]
    pub max: f64,
    #[serde(default)]
    pub max_is_best: bool,
    #[serde(default)]
    pub description: String,
}

#[derive(Debug, Clone, Default)]
pub struct FilterOutput {
    /// Passing slots, in input order.
    pub slots: Vec<Slot>,
    /// Scores of a plugin query that sent any.
    pub scores: Option<Scores>,
}

// ── compiled predicates ──────────────────────────────────────────────────────

/// The filter value as the operator functions receive it.
enum FVal {
    Json(Value),
    /// Tag operators: one set per filter tag (`{tag} ∪ allChildren`).
    TagSets(Vec<FxHashSet<TagId>>),
}

struct OpCtx {
    op: FilterOperator,
    b: FVal,
    /// Compiled `like` / `notLike` pattern (None = invalid or not needed).
    regex: Option<Regex>,
    regex_bad: bool,
}

impl OpCtx {
    fn new(op: FilterOperator, b: FVal) -> OpCtx {
        let mut c = OpCtx { op, b, regex: None, regex_bad: false };
        if matches!(op, FilterOperator::Like | FilterOperator::NotLike) {
            if let FVal::Json(v) = &c.b {
                let bj = Jv::from_json(v);
                if !bj.is_empty() {
                    let pat = js::to_string(&bj);
                    match Regex::new(&pat) {
                        Ok(r) => c.regex = Some(r),
                        Err(_) => c.regex_bad = true,
                    }
                }
            }
        }
        c
    }

    fn b_empty(&self) -> bool {
        match &self.b {
            FVal::Json(v) => Jv::from_json(v).is_empty(),
            FVal::TagSets(s) => s.is_empty(),
        }
    }

    /// The TS `operatorMap[op](a, b)`.
    fn eval(&self, a: Jv) -> bool {
        use FilterOperator as O;
        let bj = match &self.b {
            FVal::Json(v) => Jv::from_json(v),
            FVal::TagSets(_) => Jv::Obj,
        };
        match self.op {
            O::Geq | O::Leq | O::Lower | O::Greater => {
                if bj.is_nullish() {
                    return true;
                }
                if a.is_nullish() {
                    return false;
                }
                match self.op {
                    O::Geq => js::js_ge(&a, &bj),
                    O::Leq => js::js_le(&a, &bj),
                    O::Lower => js::js_lt(&a, &bj),
                    _ => js::js_gt(&a, &bj),
                }
            }
            O::Contains => {
                if self.b_empty() {
                    return true;
                }
                if a.is_empty() {
                    return false;
                }
                match a {
                    Jv::Str(s) => s.contains(&*js::to_string(&bj)),
                    Jv::Tags(t) => match bj {
                        Jv::Num(x) => t.iter().any(|&v| v as f64 == x),
                        _ => false,
                    },
                    _ => false,
                }
            }
            O::Equal => {
                if self.b_empty() {
                    return true;
                }
                if a.is_empty() {
                    return false;
                }
                js::loose_eq(&a, &bj)
            }
            O::EqualNot => {
                if self.b_empty() {
                    return true;
                }
                if a.is_empty() {
                    return true;
                }
                !js::loose_eq(&a, &bj)
            }
            O::IsFalse => a.is_empty() || js::loose_eq(&a, &Jv::Bool(false)),
            O::IsTrue => a.truthy(),
            O::IsSet => !a.is_empty(),
            O::NotSet => a.is_empty(),
            O::StartsWith => {
                if self.b_empty() {
                    return true;
                }
                if a.is_empty() {
                    return false;
                }
                match a {
                    Jv::Str(s) => s.starts_with(&*js::to_string(&bj)),
                    _ => false,
                }
            }
            O::Like | O::NotLike => {
                if self.b_empty() {
                    return true;
                }
                if a.is_empty() {
                    return false;
                }
                if self.regex_bad {
                    // JS would throw and abort the whole filter run; here the leaf passes.
                    return true;
                }
                let m = match (a, &self.regex) {
                    (Jv::Str(s), Some(r)) => r.is_match(s),
                    _ => false,
                };
                if self.op == O::Like { m } else { !m }
            }
            O::ContainsAll | O::ContainsAny | O::ContainsNot => {
                if self.b_empty() {
                    return true;
                }
                let tags: &[TagId] = match a {
                    Jv::Tags(t) => t,
                    _ => &[],
                };
                if a.is_empty() {
                    return self.op == O::ContainsNot;
                }
                let FVal::TagSets(sets) = &self.b else {
                    // A non-array value: the TS loop would iterate nothing meaningful.
                    return self.op != O::ContainsAny;
                };
                match self.op {
                    O::ContainsAll => tags.iter().all(|t| sets.iter().all(|s| s.contains(t))),
                    O::ContainsAny => tags.iter().any(|t| sets.iter().any(|s| s.contains(t))),
                    _ => !tags.iter().any(|t| sets.iter().any(|s| s.contains(t))),
                }
            }
            // and / or / unknown as a leaf operator: operatorMap has no function (TS throws).
            O::And | O::Or | O::Unknown => true,
        }
    }
}

/// Per-slot predicate of one leaf.
enum Leaf<'a> {
    Pass,
    /// Numeric fast path.
    NumSet(&'a [f64]),
    NumNotSet(&'a [f64]),
    NumCmp { data: &'a [f64], op: FilterOperator, b: f64 },
    /// Precomputed result per dictionary code (index 0 = no value).
    StrTable { codes: &'a [u32], table: Vec<bool> },
    /// Precomputed result per sha1 code.
    Sha1Table { codes: &'a [u32], table: Vec<bool> },
    /// Bool column: result for [false, true, null].
    BoolTable { data: &'a [u8], table: [bool; 3] },
    /// Anything else, evaluated per slot.
    Generic { col: ColRef<'a>, ctx: Box<OpCtx> },
}

impl Leaf<'_> {
    #[inline]
    fn test(&self, slot: Slot) -> bool {
        let s = slot as usize;
        match self {
            Leaf::Pass => true,
            Leaf::NumSet(d) => !d[s].is_nan(),
            Leaf::NumNotSet(d) => d[s].is_nan(),
            Leaf::NumCmp { data, op, b } => {
                let v = data[s];
                match op {
                    FilterOperator::Lower => !(v.is_nan() || v >= *b),
                    FilterOperator::Leq => !(v.is_nan() || v > *b),
                    FilterOperator::Greater => !(v.is_nan() || v <= *b),
                    FilterOperator::Geq => !(v.is_nan() || v < *b),
                    FilterOperator::Equal => v == *b,
                    FilterOperator::EqualNot => v != *b,
                    _ => true,
                }
            }
            Leaf::StrTable { codes, table } => table[codes[s] as usize],
            Leaf::Sha1Table { codes, table } => table[codes[s] as usize],
            Leaf::BoolTable { data, table } => table[match data[s] {
                0 => 0,
                255 => 2,
                _ => 1,
            }],
            Leaf::Generic { col, ctx } => ctx.eval(col.read(slot)),
        }
    }
}

fn dict_table(col: &StrColumn, f: impl Fn(Jv) -> bool) -> Vec<bool> {
    let dict = &col.dict;
    let mut t = Vec::with_capacity(dict.len());
    t.push(f(Jv::Null));
    for c in 1..dict.len() as u32 {
        t.push(f(Jv::Str(dict.get(c).unwrap())));
    }
    t
}

/// `+new Date(v)` of a filter value.
fn date_value(v: &Value) -> f64 {
    match v {
        Value::String(s) => js::parse_date(s),
        Value::Number(n) => js::time_clip(n.as_f64().unwrap_or(f64::NAN)),
        Value::Bool(b) => *b as i32 as f64,
        _ => f64::NAN,
    }
}

fn compile_leaf<'a>(snap: &'a Snapshot, f: &Filter) -> Leaf<'a> {
    use FilterOperator as O;
    let schema = &snap.schema;
    let Some(prop) = schema.live_property(f.property_id) else {
        // verifyState drops filters on unknown / deleted properties.
        return Leaf::Pass;
    };
    let col = snap.col(prop.id);
    // Numeric fast path (TS: `buf instanceof Float64Array` and type !== string).
    if let ColRef::Num(data) = col {
        if prop.ptype != PropertyType::Text {
            match f.operator {
                O::IsSet => return Leaf::NumSet(data),
                O::NotSet => return Leaf::NumNotSet(data),
                O::Lower | O::Leq | O::Greater | O::Geq | O::Equal | O::EqualNot => {
                    if f.value.is_null() {
                        return Leaf::Pass;
                    }
                    let b = if prop.ptype == PropertyType::Date {
                        date_value(&f.value)
                    } else {
                        js::to_number(&Jv::from_json(&f.value))
                    };
                    if b.is_nan() {
                        return Leaf::Pass;
                    }
                    return Leaf::NumCmp { data, op: f.operator, b };
                }
                // other operators fall through to the generic path, as in TS
                _ => {}
            }
        }
    }
    if prop.ptype == PropertyType::Text {
        // Lower-cased cell vs lower-cased filter value.
        let b = match &f.value {
            Value::String(s) if !s.is_empty() => Value::String(js::lower(s).into_owned()),
            other => other.clone(),
        };
        let ctx = OpCtx::new(f.operator, FVal::Json(b));
        return match col {
            ColRef::Str(c) => Leaf::StrTable {
                codes: &c.codes,
                table: dict_table(c, |a| match a {
                    Jv::Str(s) => ctx.eval(Jv::Str(&js::lower(s))),
                    other => ctx.eval(other),
                }),
            },
            other => Leaf::Generic { col: other, ctx: Box::new(ctx) },
        };
    }
    let b = if prop.ptype.is_tag() {
        match &f.value {
            Value::Array(a) if !a.is_empty() => FVal::TagSets(
                a.iter()
                    .map(|v| {
                        let t = js::to_number(&Jv::from_json(v)) as TagId;
                        let mut set: FxHashSet<TagId> =
                            schema.tag_tree(t).map(|tt| tt.all_children.clone()).unwrap_or_default();
                        set.insert(t);
                        set
                    })
                    .collect(),
            ),
            other => FVal::Json(other.clone()),
        }
    } else {
        FVal::Json(f.value.clone())
    };
    let ctx = OpCtx::new(f.operator, b);
    match col {
        ColRef::Str(c) => Leaf::StrTable { codes: &c.codes, table: dict_table(c, |a| ctx.eval(a)) },
        ColRef::Sha1(id) => {
            let dict = &id.sha1_dict;
            let mut table = Vec::with_capacity(dict.len());
            table.push(ctx.eval(Jv::Null));
            for c in 1..dict.len() as u32 {
                table.push(ctx.eval(Jv::Str(dict.get(c).unwrap())));
            }
            Leaf::Sha1Table { codes: &id.sha1, table }
        }
        ColRef::Bool(data) => {
            Leaf::BoolTable { data, table: [ctx.eval(Jv::Bool(false)), ctx.eval(Jv::Bool(true)), ctx.eval(Jv::Null)] }
        }
        other => Leaf::Generic { col: other, ctx: Box::new(ctx) },
    }
}

// ── evaluation over a mask ───────────────────────────────────────────────────

/// Clear the mask bits of slots failing `pred`. Parallel over chunks, checks `cancel`.
fn narrow(
    slots: &[Slot],
    mask: &mut [bool],
    cancel: &CancelToken,
    pred: &(dyn Fn(Slot) -> bool + Sync),
) -> Result<(), Cancelled> {
    if slots.len() < PAR_THRESHOLD {
        cancel.check()?;
        for (m, &s) in mask.iter_mut().zip(slots) {
            if *m && !pred(s) {
                *m = false;
            }
        }
        return Ok(());
    }
    mask.par_chunks_mut(CHUNK).zip(slots.par_chunks(CHUNK)).try_for_each(|(mc, sc)| {
        cancel.check()?;
        for (m, &s) in mc.iter_mut().zip(sc) {
            if *m && !pred(s) {
                *m = false;
            }
        }
        Ok(())
    })
}

fn apply_group(snap: &Snapshot, g: &FilterGroup, slots: &[Slot], mask: &mut [bool], cancel: &CancelToken) -> Result<(), Cancelled> {
    if g.filters.is_empty() {
        return Ok(());
    }
    if g.group_operator == FilterOperator::And {
        for f in &g.filters {
            apply_node(snap, f, slots, mask, cancel)?;
        }
        return Ok(());
    }
    // Anything but `and` is OR (the TS `=== and` / else split): a slot passes when it passes
    // at least one child (and was active).
    let mut todo: Vec<bool> = mask.to_vec();
    mask.iter_mut().for_each(|m| *m = false);
    for f in &g.filters {
        if !todo.iter().any(|&t| t) {
            break;
        }
        let mut work = todo.clone();
        apply_node(snap, f, slots, &mut work, cancel)?;
        for i in 0..work.len() {
            if work[i] {
                mask[i] = true;
                todo[i] = false;
            }
        }
    }
    Ok(())
}

fn apply_node(snap: &Snapshot, n: &FilterNode, slots: &[Slot], mask: &mut [bool], cancel: &CancelToken) -> Result<(), Cancelled> {
    match n {
        FilterNode::Group(g) => apply_group(snap, g, slots, mask, cancel),
        FilterNode::Leaf(f) => {
            let leaf = compile_leaf(snap, f);
            if matches!(leaf, Leaf::Pass) {
                return Ok(());
            }
            narrow(slots, mask, cancel, &|s| leaf.test(s))
        }
    }
}

/// Text / regex query over the text, path and url properties and the tag labels.
fn apply_query(snap: &Snapshot, q: &TextQuery, slots: &[Slot], mask: &mut [bool], cancel: &CancelToken) -> Result<(), Cancelled> {
    let schema: &Schema = &snap.schema;
    let text = q.text.as_deref().unwrap_or("");
    let matcher: Box<dyn Fn(&str) -> bool + Sync> = if q.kind == "text" {
        let needle = js::lower(text).into_owned();
        Box::new(move |s: &str| js::lower(s).contains(needle.as_str()))
    } else {
        match regex::RegexBuilder::new(text).case_insensitive(true).build() {
            Ok(r) => Box::new(move |s: &str| r.is_match(s)),
            // TS logs the invalid pattern and filters nothing.
            Err(_) => return Ok(()),
        }
    };
    // Per text column: result per dictionary code (identity sha1 is type sha1, not text).
    let mut text_tables: Vec<(&[u32], Vec<bool>)> = Vec::new();
    let mut tag_cols = Vec::new();
    for p in schema.properties.values().filter(|p| !p.deleted) {
        if matches!(p.ptype, PropertyType::Text | PropertyType::Path | PropertyType::Url) {
            if let ColRef::Str(c) = snap.col(p.id) {
                let table = dict_table(c, |a| match a {
                    Jv::Str(s) => !s.is_empty() && matcher(s),
                    _ => false,
                });
                text_tables.push((&c.codes, table));
            }
        } else if p.ptype.is_tag() {
            if let ColRef::Tags(c) = snap.col(p.id) {
                tag_cols.push(c);
            }
        }
    }
    // Tag labels from the global tag index (any property), deleted tags excluded.
    let tag_hit: FxHashSet<TagId> =
        schema.tags.values().filter(|t| !t.deleted && matcher(&t.value)).map(|t| t.id).collect();
    narrow(slots, mask, cancel, &|s| {
        for (codes, table) in &text_tables {
            if table[codes[s as usize] as usize] {
                return true;
            }
        }
        for c in &tag_cols {
            if c.get(s).iter().any(|t| tag_hit.contains(t)) {
                return true;
            }
        }
        false
    })
}

fn apply_plugin(snap: &Snapshot, res: &PluginQueryResult, slots: &[Slot], mask: &mut [bool]) -> Option<Scores> {
    let set: FxHashSet<&str> = res.sha1s.iter().map(|s| s.as_str()).collect();
    let values = res.scores.as_ref().map(|s| &s.values);
    let mut sha1_score = rustc_hash::FxHashMap::default();
    let mut id_score = rustc_hash::FxHashMap::default();
    if let Some(values) = values {
        for (i, h) in res.sha1s.iter().enumerate() {
            if let Some(v) = values.get(i) {
                sha1_score.insert(h.as_str(), *v);
            }
        }
        if let Some(ids) = &res.ids {
            for (i, id) in ids.iter().enumerate() {
                if let Some(v) = values.get(i) {
                    id_score.insert(*id, *v);
                }
            }
        }
    }
    let mut value_index = rustc_hash::FxHashMap::default();
    let has_sha1_prop = snap.schema.system.sha1.is_some();
    for (i, &s) in slots.iter().enumerate() {
        if !mask[i] {
            continue;
        }
        if !has_sha1_prop {
            mask[i] = false;
            continue;
        }
        let Some(h) = snap.identity.sha1_of(s) else {
            mask[i] = false;
            continue;
        };
        if !set.contains(h) {
            mask[i] = false;
            continue;
        }
        if values.is_some() {
            let id = snap.instance_id(s);
            if let Some(v) = id_score.get(&id).or_else(|| sha1_score.get(h)) {
                value_index.insert(id, *v);
            }
        }
    }
    let sc = res.scores.as_ref()?;
    Some(Scores { value_index, min: sc.min, max: sc.max, max_is_best: sc.max_is_best, description: sc.description.clone() })
}

/// Run the filter over `slots` (the collection's candidate slots, usually
/// [`Snapshot::active_slots`]). `plugin` is the backend's answer to a plugin query, when the
/// query is one.
pub fn filter(
    snap: &Snapshot,
    state: &FilterState,
    slots: &[Slot],
    plugin: Option<&PluginQueryResult>,
    cancel: &CancelToken,
) -> Result<FilterOutput, Cancelled> {
    let mut mask = vec![true; slots.len()];
    let mut scores = None;
    let q = &state.query;
    if q.is_active() {
        if q.kind == "text" || q.kind == "regex" {
            apply_query(snap, q, slots, &mut mask, cancel)?;
        } else if let Some(res) = plugin {
            scores = apply_plugin(snap, res, slots, &mut mask);
        }
    }
    cancel.check()?;
    // Folders (verifyState keeps only existing folder ids).
    let folders: FxHashSet<i64> = state.folders.iter().copied().filter(|f| snap.schema.folders.contains_key(f)).collect();
    if !folders.is_empty() {
        if let Some(fp) = snap.schema.system.folder {
            let col = snap.col(fp);
            narrow(slots, &mut mask, cancel, &|s| match col.read(s) {
                Jv::Num(x) => folders.contains(&(x as i64)) && x.fract() == 0.0,
                _ => false,
            })?;
        }
    }
    apply_group(snap, &state.filter, slots, &mut mask, cancel)?;
    cancel.check()?;
    let out: Vec<Slot> = slots.iter().zip(&mask).filter(|(_, m)| **m).map(|(s, _)| *s).collect();
    Ok(FilterOutput { slots: out, scores })
}

/// The properties a filter state reads (for column loading on the P4 side).
pub fn required_columns(state: &FilterState, schema: &Schema) -> Vec<PropId> {
    let mut out = Vec::new();
    fn walk(g: &FilterGroup, out: &mut Vec<PropId>) {
        for f in &g.filters {
            match f {
                FilterNode::Group(g) => walk(g, out),
                FilterNode::Leaf(l) => out.push(l.property_id),
            }
        }
    }
    walk(&state.filter, &mut out);
    if !state.folders.is_empty() {
        if let Some(f) = schema.system.folder {
            out.push(f);
        }
    }
    if state.query.is_plugin() {
        if let Some(s) = schema.system.sha1 {
            out.push(s);
        }
    } else if state.query.is_active() {
        out.extend(schema.properties.values().filter(|p| matches!(p.ptype, PropertyType::Text | PropertyType::Path | PropertyType::Url) || p.ptype.is_tag()).map(|p| p.id));
    }
    out.sort_unstable();
    out.dedup();
    out
}
