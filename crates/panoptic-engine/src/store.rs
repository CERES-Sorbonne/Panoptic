//! The columnar store: immutable snapshots of instance identity + typed property columns.
//!
//! * A **slot** is the dense index of an instance (`u32`). Slots are only ever appended; deleting
//!   an instance sets its bit in the deleted mask. `epoch` changes when slots are re-minted
//!   (a full reload), so anything holding slot-indexed data can detect it.
//! * Property values are stored **per slot**, whatever the property mode: a sha1-mode or
//!   file-mode value is written to every slot sharing that sha1 / file id when the delta is
//!   applied (this is what the TS `columnStore.updateFromLoadResult` does), and a new instance
//!   inherits the sha1/file-mode values of an existing instance with the same sha1 / file id.
//! * Every column is behind its own `Arc`: a delta clones only the columns it touches, so a new
//!   [`Snapshot`] shares everything else with the previous one and readers never wait on writers.

use std::sync::Arc;

use arc_swap::ArcSwap;
use rustc_hash::{FxHashMap, FxHashSet};

use crate::js;
use crate::schema::{ColumnKind, FolderId, InstanceId, PropId, PropertyMode, PropertyType, Schema, TagId};

pub type Slot = u32;

// ── string dictionary ────────────────────────────────────────────────────────

/// Append-only string interner shared by successive versions of a string column. Code 0 is
/// "no value".
#[derive(Debug, Clone, Default)]
pub struct StrDict {
    values: Vec<Arc<str>>,
    lookup: FxHashMap<Arc<str>, u32>,
}

impl StrDict {
    pub fn new() -> Self {
        StrDict { values: vec![Arc::from("")], lookup: FxHashMap::default() }
    }
    pub fn len(&self) -> usize {
        self.values.len()
    }
    pub fn is_empty(&self) -> bool {
        self.values.len() <= 1
    }
    /// The string of a code (`None` for 0).
    #[inline]
    pub fn get(&self, code: u32) -> Option<&str> {
        if code == 0 { None } else { Some(&self.values[code as usize]) }
    }
    pub fn code_of(&self, s: &str) -> Option<u32> {
        self.lookup.get(s).copied()
    }
    pub fn intern(&mut self, s: &str) -> u32 {
        if let Some(&c) = self.lookup.get(s) {
            return c;
        }
        let a: Arc<str> = Arc::from(s);
        let c = self.values.len() as u32;
        self.values.push(a.clone());
        self.lookup.insert(a, c);
        c
    }
}

#[derive(Debug, Clone)]
pub struct StrColumn {
    pub codes: Vec<u32>,
    pub dict: Arc<StrDict>,
}

impl StrColumn {
    #[inline]
    pub fn get(&self, slot: Slot) -> Option<&str> {
        self.dict.get(self.codes[slot as usize])
    }
}

/// Tag ids per slot, CSR-encoded. An empty list and "no value" are the same thing (every TS
/// reader treats `[]` and `null` alike).
#[derive(Debug, Clone)]
pub struct TagColumn {
    pub offsets: Vec<u32>,
    pub values: Vec<TagId>,
}

impl TagColumn {
    pub fn empty(n: usize) -> Self {
        TagColumn { offsets: vec![0; n + 1], values: Vec::new() }
    }
    #[inline]
    pub fn get(&self, slot: Slot) -> &[TagId] {
        let s = slot as usize;
        &self.values[self.offsets[s] as usize..self.offsets[s + 1] as usize]
    }
    pub fn len(&self) -> usize {
        self.offsets.len() - 1
    }
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

/// A typed property column, indexed by slot.
#[derive(Debug, Clone)]
pub enum Column {
    /// number, date (epoch ms), color, width/height, folder ids. NaN = no value.
    Num(Arc<Vec<f64>>),
    /// checkbox: 0 / 1, 255 = no value.
    Bool(Arc<Vec<u8>>),
    Str(Arc<StrColumn>),
    Tags(Arc<TagColumn>),
}

impl Column {
    pub fn new(kind: ColumnKind, n: usize) -> Column {
        match kind {
            ColumnKind::Num => Column::Num(Arc::new(vec![f64::NAN; n])),
            ColumnKind::Bool => Column::Bool(Arc::new(vec![255; n])),
            ColumnKind::Str => Column::Str(Arc::new(StrColumn { codes: vec![0; n], dict: Arc::new(StrDict::new()) })),
            ColumnKind::Tags => Column::Tags(Arc::new(TagColumn::empty(n))),
        }
    }

    pub fn len(&self) -> usize {
        match self {
            Column::Num(v) => v.len(),
            Column::Bool(v) => v.len(),
            Column::Str(c) => c.codes.len(),
            Column::Tags(c) => c.len(),
        }
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

// ── identity ─────────────────────────────────────────────────────────────────

/// Instance identity columns + lookup indexes.
#[derive(Debug, Clone, Default)]
pub struct Identity {
    pub ids: Vec<InstanceId>,
    /// sha1 code per slot (0 = none) into `sha1_dict`.
    pub sha1: Vec<u32>,
    pub sha1_dict: Arc<StrDict>,
    pub file_ids: Vec<i32>,
    pub slot_of: FxHashMap<InstanceId, Slot>,
}

impl Identity {
    pub fn len(&self) -> usize {
        self.ids.len()
    }
    pub fn is_empty(&self) -> bool {
        self.ids.is_empty()
    }
    #[inline]
    pub fn sha1_of(&self, slot: Slot) -> Option<&str> {
        self.sha1_dict.get(self.sha1[slot as usize])
    }
}

// ── values written into the store ────────────────────────────────────────────

/// A cell value as written by a delta.
#[derive(Debug, Clone, PartialEq)]
pub enum CellValue {
    Null,
    Num(f64),
    Bool(bool),
    Str(String),
    Tags(Vec<TagId>),
}

impl CellValue {
    /// Coerce a decoded JSON value for a property of type `ptype`, the way the TS
    /// `columnStore.writeSlot` does: dates given as strings are parsed to epoch ms, numbers go
    /// through `Number(x)`, checkboxes through truthiness, a non-array tag value is "no value".
    pub fn from_json(ptype: PropertyType, v: &serde_json::Value) -> CellValue {
        use serde_json::Value as V;
        if v.is_null() {
            return CellValue::Null;
        }
        match ptype.kind() {
            ColumnKind::Num => {
                if ptype == PropertyType::Date {
                    if let V::String(s) = v {
                        return CellValue::Num(js::parse_date(s));
                    }
                }
                CellValue::Num(js::to_number(&js::Jv::from_json(v)))
            }
            ColumnKind::Bool => CellValue::Bool(js::Jv::from_json(v).truthy()),
            ColumnKind::Str => match v {
                V::String(s) => CellValue::Str(s.clone()),
                other => CellValue::Str(js::to_string(&js::Jv::from_json(other)).into_owned()),
            },
            ColumnKind::Tags => match v {
                V::Array(a) => CellValue::Tags(a.iter().filter_map(|x| x.as_f64()).map(|x| x as TagId).collect()),
                _ => CellValue::Null,
            },
        }
    }
}

/// How the cells of a value delta are addressed.
#[derive(Debug, Clone)]
pub enum ValueKeys {
    Instances(Vec<InstanceId>),
    Sha1s(Vec<String>),
    Files(Vec<i32>),
}

/// One change to apply to a snapshot.
#[derive(Debug, Clone)]
pub enum Delta {
    /// Append instances. Already-known ids are skipped (deltas can re-deliver rows).
    AddInstances { ids: Vec<InstanceId>, sha1s: Vec<Option<String>>, file_ids: Vec<i32> },
    /// Mark instances deleted (the slot stays; the mask hides it).
    DeleteInstances { ids: Vec<InstanceId> },
    /// Write values of one property. `values[i]` goes to `keys[i]`.
    SetValues { property_id: PropId, keys: ValueKeys, values: Vec<CellValue> },
    /// Clear cells of one property (a value removed by a delta).
    ClearValues { property_id: PropId, keys: ValueKeys },
    /// Replace the whole column of a property, slot-indexed (initial load).
    SetColumn { property_id: PropId, column: Column },
    /// Drop a property's column.
    DropColumn { property_id: PropId },
    /// Replace the schema (properties / tags / folders changed).
    SetSchema(Arc<Schema>),
    /// Scrub tag ids out of every tag column (a tag delete), as `columnStore.removeTagIds`.
    RemoveTagIds { tag_ids: Vec<TagId> },
}

/// What a delta batch changed — the input of an incremental recompute decision.
#[derive(Debug, Clone, Default)]
pub struct Changes {
    /// Instances whose values (or existence) changed.
    pub instances: FxHashSet<InstanceId>,
    pub properties: FxHashSet<PropId>,
    pub schema: bool,
    pub added: usize,
}

// ── snapshot ─────────────────────────────────────────────────────────────────

/// An immutable version of the store. Cheap to clone (all `Arc`s).
#[derive(Debug, Clone)]
pub struct Snapshot {
    pub schema: Arc<Schema>,
    pub identity: Arc<Identity>,
    pub deleted: Arc<Vec<bool>>,
    pub columns: Arc<FxHashMap<PropId, Column>>,
    /// Bumped by every applied delta batch.
    pub version: u64,
    /// Slot generation (changes only when slots are re-minted).
    pub epoch: u64,
}

/// Read access to one property's values, resolved once per pipeline step.
#[derive(Debug, Clone, Copy)]
pub enum ColRef<'a> {
    /// A regular numeric column (the TS `Float64Array` fast path).
    Num(&'a [f64]),
    /// Folder ids: numeric storage, generic (non-Float64Array) read semantics.
    FolderNum(&'a [f64]),
    Bool(&'a [u8]),
    Str(&'a StrColumn),
    Tags(&'a TagColumn),
    /// Identity integers (instance id / file id): generic semantics (TS `Int32Array`).
    Int(&'a [i32]),
    /// The identity sha1 column.
    Sha1(&'a Identity),
    /// No column was ever written for the property (TS `readSlot` → `undefined`).
    Missing,
}

impl<'a> ColRef<'a> {
    /// The value as the TS `readSlot` returns it.
    #[inline]
    pub fn read(&self, slot: Slot) -> js::Jv<'a> {
        use js::Jv;
        let s = slot as usize;
        match *self {
            ColRef::Num(v) | ColRef::FolderNum(v) => {
                let x = v[s];
                if x.is_nan() { Jv::Null } else { Jv::Num(x) }
            }
            ColRef::Bool(v) => match v[s] {
                255 => Jv::Null,
                b => Jv::Bool(b == 1),
            },
            ColRef::Str(c) => match c.get(slot) {
                Some(x) => Jv::Str(x),
                None => Jv::Null,
            },
            ColRef::Tags(c) => {
                let t = c.get(slot);
                if t.is_empty() { Jv::Null } else { Jv::Tags(t) }
            }
            ColRef::Int(v) => Jv::Num(v[s] as f64),
            ColRef::Sha1(id) => match id.sha1_of(slot) {
                Some(x) => Jv::Str(x),
                None => Jv::Null,
            },
            ColRef::Missing => Jv::Undef,
        }
    }
}

impl Snapshot {
    pub fn empty(schema: Arc<Schema>) -> Snapshot {
        Snapshot {
            schema,
            identity: Arc::new(Identity { sha1_dict: Arc::new(StrDict::new()), ..Default::default() }),
            deleted: Arc::new(Vec::new()),
            columns: Arc::new(FxHashMap::default()),
            version: 0,
            epoch: 0,
        }
    }

    /// Number of slots (deleted ones included).
    pub fn len(&self) -> usize {
        self.identity.len()
    }

    pub fn is_empty(&self) -> bool {
        self.identity.is_empty()
    }

    pub fn slot_of(&self, id: InstanceId) -> Option<Slot> {
        self.identity.slot_of.get(&id).copied()
    }

    #[inline]
    pub fn instance_id(&self, slot: Slot) -> InstanceId {
        self.identity.ids[slot as usize]
    }

    /// Slots that are not deleted, ascending — the input of every collection.
    pub fn active_slots(&self) -> Vec<Slot> {
        let d = &self.deleted;
        (0..self.len() as u32).filter(|&s| !d[s as usize]).collect()
    }

    /// Read access to a property's values.
    pub fn col(&self, prop: PropId) -> ColRef<'_> {
        let sys = &self.schema.system;
        if Some(prop) == sys.instance_id {
            return ColRef::Int(&self.identity.ids);
        }
        if Some(prop) == sys.sha1 {
            return ColRef::Sha1(&self.identity);
        }
        if Some(prop) == sys.file_id {
            return ColRef::Int(&self.identity.file_ids);
        }
        let folder = self.schema.property(prop).map(|p| p.ptype == PropertyType::Folder).unwrap_or(false);
        match self.columns.get(&prop) {
            None => ColRef::Missing,
            Some(Column::Num(v)) => {
                if folder { ColRef::FolderNum(v) } else { ColRef::Num(v) }
            }
            Some(Column::Bool(v)) => ColRef::Bool(v),
            Some(Column::Str(c)) => ColRef::Str(c),
            Some(Column::Tags(c)) => ColRef::Tags(c),
        }
    }

    /// Apply a batch of deltas, producing the next snapshot and what changed.
    pub fn apply(&self, deltas: &[Delta]) -> (Snapshot, Changes) {
        let mut b = Builder::from(self);
        let mut changes = Changes::default();
        for d in deltas {
            b.apply(d, &mut changes);
        }
        let mut next = b.finish();
        next.version = self.version + 1;
        (next, changes)
    }

    /// Instances with a given sha1 (not deleted), in slot order.
    pub fn instances_by_sha1(&self, sha1: &str) -> Vec<InstanceId> {
        let Some(code) = self.identity.sha1_dict.code_of(sha1) else { return vec![] };
        (0..self.len())
            .filter(|&s| self.identity.sha1[s] == code && !self.deleted[s])
            .map(|s| self.identity.ids[s])
            .collect()
    }
}

/// Copy-on-write builder behind [`Snapshot::apply`].
struct Builder {
    schema: Arc<Schema>,
    identity: Arc<Identity>,
    deleted: Arc<Vec<bool>>,
    columns: Arc<FxHashMap<PropId, Column>>,
    epoch: u64,
    /// Pending per-slot writes of tag columns, applied in one CSR rebuild at the end.
    tag_writes: FxHashMap<PropId, FxHashMap<Slot, Vec<TagId>>>,
    sha1_slots: Option<FxHashMap<u32, Vec<Slot>>>,
    file_slots: Option<FxHashMap<i32, Vec<Slot>>>,
}

impl Builder {
    fn from(s: &Snapshot) -> Builder {
        Builder {
            schema: s.schema.clone(),
            identity: s.identity.clone(),
            deleted: s.deleted.clone(),
            columns: s.columns.clone(),
            epoch: s.epoch,
            tag_writes: FxHashMap::default(),
            sha1_slots: None,
            file_slots: None,
        }
    }

    fn len(&self) -> usize {
        self.identity.ids.len()
    }

    fn sha1_index(&mut self) -> &FxHashMap<u32, Vec<Slot>> {
        if self.sha1_slots.is_none() {
            let mut m: FxHashMap<u32, Vec<Slot>> = FxHashMap::default();
            for (s, &c) in self.identity.sha1.iter().enumerate() {
                if c != 0 {
                    m.entry(c).or_default().push(s as Slot);
                }
            }
            self.sha1_slots = Some(m);
        }
        self.sha1_slots.as_ref().unwrap()
    }

    fn file_index(&mut self) -> &FxHashMap<i32, Vec<Slot>> {
        if self.file_slots.is_none() {
            let mut m: FxHashMap<i32, Vec<Slot>> = FxHashMap::default();
            for (s, &f) in self.identity.file_ids.iter().enumerate() {
                m.entry(f).or_default().push(s as Slot);
            }
            self.file_slots = Some(m);
        }
        self.file_slots.as_ref().unwrap()
    }

    /// Resolve value keys to slots: `out[i]` = the slots of `keys[i]`.
    fn resolve(&mut self, keys: &ValueKeys) -> Vec<Vec<Slot>> {
        match keys {
            ValueKeys::Instances(ids) => ids
                .iter()
                .map(|id| self.identity.slot_of.get(id).map(|&s| vec![s]).unwrap_or_default())
                .collect(),
            ValueKeys::Sha1s(sha1s) => {
                let codes: Vec<Option<u32>> = sha1s.iter().map(|h| self.identity.sha1_dict.code_of(h)).collect();
                let idx = self.sha1_index();
                codes.iter().map(|c| c.and_then(|c| idx.get(&c).cloned()).unwrap_or_default()).collect()
            }
            ValueKeys::Files(files) => {
                let idx = self.file_index();
                files.iter().map(|f| idx.get(f).cloned().unwrap_or_default()).collect()
            }
        }
    }

    fn kind_of(&self, prop: PropId) -> ColumnKind {
        self.schema.property(prop).map(|p| p.ptype.kind()).unwrap_or(ColumnKind::Str)
    }

    fn ensure_column(&mut self, prop: PropId) -> &mut Column {
        let n = self.len();
        let kind = self.kind_of(prop);
        let cols = Arc::make_mut(&mut self.columns);
        cols.entry(prop).or_insert_with(|| Column::new(kind, n))
    }

    fn write(&mut self, prop: PropId, slots: &[Slot], v: &CellValue) {
        if slots.is_empty() {
            return;
        }
        if self.kind_of(prop) == ColumnKind::Tags {
            self.ensure_column(prop);
            let w = self.tag_writes.entry(prop).or_default();
            let tags = match v {
                CellValue::Tags(t) => t.clone(),
                _ => Vec::new(),
            };
            for &s in slots {
                w.insert(s, tags.clone());
            }
            return;
        }
        let ptype = self.schema.property(prop).map(|p| p.ptype).unwrap_or(PropertyType::Text);
        match self.ensure_column(prop) {
            Column::Num(data) => {
                let x = match v {
                    CellValue::Null => f64::NAN,
                    CellValue::Num(x) => *x,
                    CellValue::Bool(b) => *b as i32 as f64,
                    CellValue::Str(s) => {
                        if ptype == PropertyType::Date { js::parse_date(s) } else { js::string_to_number(s) }
                    }
                    CellValue::Tags(_) => f64::NAN,
                };
                let d = Arc::make_mut(data);
                for &s in slots {
                    d[s as usize] = x;
                }
            }
            Column::Bool(data) => {
                let x = match v {
                    CellValue::Null => 255,
                    CellValue::Bool(b) => *b as u8,
                    CellValue::Num(x) => (*x != 0.0 && !x.is_nan()) as u8,
                    CellValue::Str(s) => (!s.is_empty()) as u8,
                    CellValue::Tags(_) => 1,
                };
                let d = Arc::make_mut(data);
                for &s in slots {
                    d[s as usize] = x;
                }
            }
            Column::Str(col) => {
                let c = Arc::make_mut(col);
                let code = match v {
                    CellValue::Null => 0,
                    CellValue::Str(s) => Arc::make_mut(&mut c.dict).intern(s),
                    CellValue::Num(x) => Arc::make_mut(&mut c.dict).intern(&js::number_to_string(*x)),
                    CellValue::Bool(b) => Arc::make_mut(&mut c.dict).intern(if *b { "true" } else { "false" }),
                    CellValue::Tags(t) => Arc::make_mut(&mut c.dict)
                        .intern(&t.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(",")),
                };
                for &s in slots {
                    c.codes[s as usize] = code;
                }
            }
            Column::Tags(_) => unreachable!(),
        }
    }

    fn apply(&mut self, d: &Delta, ch: &mut Changes) {
        match d {
            Delta::AddInstances { ids, sha1s, file_ids } => self.add_instances(ids, sha1s, file_ids, ch),
            Delta::DeleteInstances { ids } => {
                let mut del: Option<&mut Vec<bool>> = None;
                for id in ids {
                    if let Some(&s) = self.identity.slot_of.get(id) {
                        let dm = del.get_or_insert_with(|| Arc::make_mut(&mut self.deleted));
                        dm[s as usize] = true;
                        ch.instances.insert(*id);
                    }
                }
            }
            Delta::SetValues { property_id, keys, values } => {
                let resolved = self.resolve(keys);
                for (slots, v) in resolved.iter().zip(values) {
                    self.write(*property_id, slots, v);
                    for &s in slots {
                        ch.instances.insert(self.identity.ids[s as usize]);
                    }
                }
                ch.properties.insert(*property_id);
            }
            Delta::ClearValues { property_id, keys } => {
                if !self.columns.contains_key(property_id) {
                    return;
                }
                let resolved = self.resolve(keys);
                for slots in &resolved {
                    self.write(*property_id, slots, &CellValue::Null);
                    for &s in slots {
                        ch.instances.insert(self.identity.ids[s as usize]);
                    }
                }
                ch.properties.insert(*property_id);
            }
            Delta::SetColumn { property_id, column } => {
                assert_eq!(column.len(), self.len(), "SetColumn: column length must equal the slot count");
                self.tag_writes.remove(property_id);
                Arc::make_mut(&mut self.columns).insert(*property_id, column.clone());
                ch.properties.insert(*property_id);
            }
            Delta::DropColumn { property_id } => {
                self.tag_writes.remove(property_id);
                if self.columns.contains_key(property_id) {
                    Arc::make_mut(&mut self.columns).remove(property_id);
                }
                ch.properties.insert(*property_id);
            }
            Delta::SetSchema(schema) => {
                self.schema = schema.clone();
                ch.schema = true;
            }
            Delta::RemoveTagIds { tag_ids } => {
                let drop: FxHashSet<TagId> = tag_ids.iter().copied().collect();
                self.flush_tags();
                let props: Vec<PropId> = self
                    .columns
                    .iter()
                    .filter(|(_, c)| matches!(c, Column::Tags(_)))
                    .map(|(p, _)| *p)
                    .collect();
                for p in props {
                    let Some(Column::Tags(col)) = self.columns.get(&p) else { continue };
                    let col = col.clone();
                    let mut w: FxHashMap<Slot, Vec<TagId>> = FxHashMap::default();
                    for s in 0..col.len() as Slot {
                        let t = col.get(s);
                        if t.iter().any(|x| drop.contains(x)) {
                            w.insert(s, t.iter().copied().filter(|x| !drop.contains(x)).collect());
                            ch.instances.insert(self.identity.ids[s as usize]);
                        }
                    }
                    if !w.is_empty() {
                        self.tag_writes.insert(p, w);
                        ch.properties.insert(p);
                    }
                }
            }
        }
    }

    fn add_instances(&mut self, ids: &[InstanceId], sha1s: &[Option<String>], file_ids: &[i32], ch: &mut Changes) {
        self.flush_tags();
        let old = self.len();
        let fresh: Vec<usize> = (0..ids.len()).filter(|&i| !self.identity.slot_of.contains_key(&ids[i])).collect();
        // dedup within the batch too
        let mut seen = FxHashSet::default();
        let fresh: Vec<usize> = fresh.into_iter().filter(|&i| seen.insert(ids[i])).collect();
        if fresh.is_empty() {
            return;
        }
        let n = old + fresh.len();
        // Remember, per sha1 / file id, an existing slot to inherit sha1 / file-mode values from.
        let sha1_src = self.sha1_index().clone();
        let file_src = self.file_index().clone();
        {
            let idn = Arc::make_mut(&mut self.identity);
            let dict = Arc::make_mut(&mut idn.sha1_dict);
            for &i in &fresh {
                let s = idn.ids.len() as Slot;
                idn.ids.push(ids[i]);
                let code = match sha1s.get(i).and_then(|x| x.as_deref()) {
                    Some(h) => dict.intern(h),
                    None => 0,
                };
                idn.sha1.push(code);
                idn.file_ids.push(*file_ids.get(i).unwrap_or(&0));
                idn.slot_of.insert(ids[i], s);
                ch.instances.insert(ids[i]);
            }
        }
        Arc::make_mut(&mut self.deleted).resize(n, false);
        let cols = Arc::make_mut(&mut self.columns);
        for (prop, col) in cols.iter_mut() {
            let mode = self.schema.property(*prop).map(|p| p.mode).unwrap_or(PropertyMode::Id);
            let src_of = |slot: usize, identity: &Identity| -> Option<Slot> {
                match mode {
                    PropertyMode::Id => None,
                    PropertyMode::Sha1 => {
                        let c = identity.sha1[slot];
                        if c == 0 { None } else { sha1_src.get(&c).and_then(|v| v.first().copied()) }
                    }
                    PropertyMode::File => file_src.get(&identity.file_ids[slot]).and_then(|v| v.first().copied()),
                }
            };
            match col {
                Column::Num(d) => {
                    let d = Arc::make_mut(d);
                    d.resize(n, f64::NAN);
                    for s in old..n {
                        if let Some(src) = src_of(s, &self.identity) {
                            d[s] = d[src as usize];
                        }
                    }
                }
                Column::Bool(d) => {
                    let d = Arc::make_mut(d);
                    d.resize(n, 255);
                    for s in old..n {
                        if let Some(src) = src_of(s, &self.identity) {
                            d[s] = d[src as usize];
                        }
                    }
                }
                Column::Str(c) => {
                    let c = Arc::make_mut(c);
                    c.codes.resize(n, 0);
                    for s in old..n {
                        if let Some(src) = src_of(s, &self.identity) {
                            c.codes[s] = c.codes[src as usize];
                        }
                    }
                }
                Column::Tags(c) => {
                    let c = Arc::make_mut(c);
                    let mut extra: Vec<TagId> = Vec::new();
                    let mut offs = Vec::with_capacity(n - old);
                    let base = c.values.len() as u32;
                    for s in old..n {
                        if let Some(src) = src_of(s, &self.identity) {
                            let t = c.get(src);
                            extra.extend_from_slice(t);
                        }
                        offs.push(base + extra.len() as u32);
                    }
                    c.values.extend_from_slice(&extra);
                    c.offsets.extend_from_slice(&offs);
                }
            }
        }
        self.sha1_slots = None;
        self.file_slots = None;
        ch.added += fresh.len();
    }

    /// Apply pending tag writes (one CSR rebuild per touched column).
    fn flush_tags(&mut self) {
        if self.tag_writes.is_empty() {
            return;
        }
        let writes = std::mem::take(&mut self.tag_writes);
        let n = self.len();
        let cols = Arc::make_mut(&mut self.columns);
        for (prop, w) in writes {
            let Some(Column::Tags(col)) = cols.get_mut(&prop) else { continue };
            let old = col.clone();
            let mut offsets = Vec::with_capacity(n + 1);
            let mut values = Vec::with_capacity(old.values.len() + w.len());
            offsets.push(0u32);
            for s in 0..n as Slot {
                match w.get(&s) {
                    Some(t) => values.extend_from_slice(t),
                    None => values.extend_from_slice(old.get(s)),
                }
                offsets.push(values.len() as u32);
            }
            *col = Arc::new(TagColumn { offsets, values });
        }
    }

    fn finish(mut self) -> Snapshot {
        self.flush_tags();
        Snapshot {
            schema: self.schema,
            identity: self.identity,
            deleted: self.deleted,
            columns: self.columns,
            version: 0,
            epoch: self.epoch,
        }
    }
}

/// Helpers to build columns in bulk (initial load, tests, benchmarks).
pub mod build {
    use super::*;

    pub fn num(values: Vec<f64>) -> Column {
        Column::Num(Arc::new(values))
    }

    pub fn bools(values: impl IntoIterator<Item = Option<bool>>) -> Column {
        Column::Bool(Arc::new(values.into_iter().map(|v| v.map(|b| b as u8).unwrap_or(255)).collect()))
    }

    pub fn strings<S: AsRef<str>>(values: impl IntoIterator<Item = Option<S>>) -> Column {
        let mut dict = StrDict::new();
        let codes = values.into_iter().map(|v| v.map(|s| dict.intern(s.as_ref())).unwrap_or(0)).collect();
        Column::Str(Arc::new(StrColumn { codes, dict: Arc::new(dict) }))
    }

    pub fn tags<I: AsRef<[TagId]>>(values: impl IntoIterator<Item = I>) -> Column {
        let mut offsets = vec![0u32];
        let mut out = Vec::new();
        for v in values {
            out.extend_from_slice(v.as_ref());
            offsets.push(out.len() as u32);
        }
        Column::Tags(Arc::new(TagColumn { offsets, values: out }))
    }

    /// A snapshot from identity columns (no property values).
    pub fn snapshot(schema: Arc<Schema>, ids: Vec<InstanceId>, sha1s: Vec<Option<String>>, file_ids: Vec<i32>, epoch: u64) -> Snapshot {
        let mut dict = StrDict::new();
        let sha1 = sha1s.iter().map(|h| h.as_deref().map(|h| dict.intern(h)).unwrap_or(0)).collect();
        let slot_of = ids.iter().enumerate().map(|(s, &id)| (id, s as Slot)).collect();
        let n = ids.len();
        Snapshot {
            schema,
            identity: Arc::new(Identity { ids, sha1, sha1_dict: Arc::new(dict), file_ids, slot_of }),
            deleted: Arc::new(vec![false; n]),
            columns: Arc::new(FxHashMap::default()),
            version: 0,
            epoch,
        }
    }
}

/// The store root: the current snapshot, swapped atomically. Readers `load()` a snapshot and
/// keep it for the whole computation; writers build the next one and `publish` it.
pub struct Store {
    current: ArcSwap<Snapshot>,
    write_lock: std::sync::Mutex<()>,
}

impl Store {
    pub fn new(snapshot: Snapshot) -> Store {
        Store { current: ArcSwap::from_pointee(snapshot), write_lock: std::sync::Mutex::new(()) }
    }

    /// The current snapshot. Never blocks.
    pub fn load(&self) -> Arc<Snapshot> {
        self.current.load_full()
    }

    /// Apply deltas to the current snapshot and publish the result. Writers are serialised with
    /// each other, never with readers.
    pub fn apply(&self, deltas: &[Delta]) -> (Arc<Snapshot>, Changes) {
        let _g = self.write_lock.lock().unwrap();
        let cur = self.current.load_full();
        let (next, ch) = cur.apply(deltas);
        let next = Arc::new(next);
        self.current.store(next.clone());
        (next, ch)
    }

    /// Replace the snapshot wholesale (project reload: bump `epoch` on the new one).
    pub fn replace(&self, snapshot: Snapshot) {
        let _g = self.write_lock.lock().unwrap();
        self.current.store(Arc::new(snapshot));
    }
}

/// Convenience: the folder id stored for a slot in a folder column.
pub fn folder_of(col: &ColRef, slot: Slot) -> Option<FolderId> {
    match col.read(slot) {
        js::Jv::Num(x) => Some(x as FolderId),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::schema::PropertyDef;

    fn schema() -> Arc<Schema> {
        let p = |id, t, mode| PropertyDef { id, name: String::new(), ptype: t, mode, system_key: None, deleted: false };
        Arc::new(Schema::new(
            [
                p(1, PropertyType::Number, PropertyMode::Id),
                p(2, PropertyType::MultiTags, PropertyMode::Sha1),
                p(3, PropertyType::Text, PropertyMode::File),
            ],
            [],
            [],
        ))
    }

    #[test]
    fn deltas_resolve_modes_and_inherit() {
        let s = build::snapshot(schema(), vec![10, 11, 12], vec![Some("a".into()), Some("a".into()), Some("b".into())], vec![1, 2, 1], 1);
        let (s2, ch) = s.apply(&[
            Delta::SetValues { property_id: 2, keys: ValueKeys::Sha1s(vec!["a".into()]), values: vec![CellValue::Tags(vec![5, 6])] },
            Delta::SetValues { property_id: 3, keys: ValueKeys::Files(vec![1]), values: vec![CellValue::Str("x".into())] },
            Delta::SetValues { property_id: 1, keys: ValueKeys::Instances(vec![12]), values: vec![CellValue::Num(3.0)] },
        ]);
        assert_eq!(ch.instances.len(), 3);
        let ColRef::Tags(t) = s2.col(2) else { panic!() };
        assert_eq!(t.get(0), &[5, 6]);
        assert_eq!(t.get(1), &[5, 6]);
        assert!(t.get(2).is_empty());
        let ColRef::Str(c) = s2.col(3) else { panic!() };
        assert_eq!(c.get(0), Some("x"));
        assert_eq!(c.get(2), Some("x"));
        assert_eq!(c.get(1), None);
        // the old snapshot is untouched
        assert!(matches!(s.col(2), ColRef::Missing));
        // a new instance with sha1 "a" inherits the sha1-mode tags; file 2 inherits the text
        let (s3, _) = s2.apply(&[Delta::AddInstances { ids: vec![13, 10], sha1s: vec![Some("a".into()), None], file_ids: vec![2, 0] }]);
        assert_eq!(s3.len(), 4);
        let ColRef::Tags(t) = s3.col(2) else { panic!() };
        assert_eq!(t.get(3), &[5, 6]);
        let ColRef::Str(c) = s3.col(3) else { panic!() };
        assert_eq!(c.get(3), None);
        let (s4, _) = s3.apply(&[Delta::DeleteInstances { ids: vec![11] }, Delta::RemoveTagIds { tag_ids: vec![5] }]);
        assert_eq!(s4.active_slots(), vec![0, 2, 3]);
        let ColRef::Tags(t) = s4.col(2) else { panic!() };
        assert_eq!(t.get(0), &[6]);
    }
}
