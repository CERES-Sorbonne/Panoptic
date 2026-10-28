//! Synthetic columns, generated exactly like `js/bench.js` (same PRNG, same draw order) so both
//! sides hold identical data and their checksums can be compared.
//!
//! Layout is what a Rust column store would hold: `Vec<f64>` for numbers and dates (NaN = no
//! value), `Vec<u8>` for checkboxes (255 = no value), dictionary-encoded strings (code 0 = no
//! value) and CSR tag lists (an empty list = no value).

use rustc_hash::FxHashMap;

pub const N_WORDS: usize = 2000;
pub const N_LABELS: u32 = 300;
pub const N_TAGS: usize = 1000;
pub const DATE_BASE: f64 = 1_420_070_400_000.0; // Date.UTC(2015, 0, 1)
pub const DATE_SPAN: f64 = 10.0 * 365.25 * 86_400_000.0;
pub const LAST_STRING: &str = "zzzzzzzzzzzzzzzzzzzzzzzzzzzz";

const SYL: [&str; 32] = [
    "ka", "ro", "mi", "ta", "ne", "so", "lu", "vi", "po", "de", "ga", "fi", "zu", "be", "xo", "qui",
    "ar", "el", "on", "us", "ix", "ya", "we", "jo", "ha", "ci", "mo", "ru", "sa", "te", "li", "no",
];

/// mulberry32, bit-identical to the JS version.
pub struct Rng(u32);

impl Rng {
    pub fn new(seed: u32) -> Self {
        Rng(seed)
    }
    #[inline]
    pub fn next(&mut self) -> f64 {
        self.0 = self.0.wrapping_add(0x6D2B_79F5);
        let mut t = self.0;
        t = (t ^ (t >> 15)).wrapping_mul(t | 1);
        t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
        (t ^ (t >> 14)) as f64 / 4_294_967_296.0
    }
    #[inline]
    pub fn int(&mut self, k: u32) -> u32 {
        (self.next() * k as f64).floor() as u32
    }
}

/// Dictionary-encoded string column. `lower` is the lowercased dictionary, built once when the
/// column is loaded (the JS side lowercases on every filter / sort call instead).
pub struct StrCol {
    pub codes: Vec<u32>,
    pub dict: Vec<Box<str>>,
    pub lower: Vec<Box<str>>,
}

impl StrCol {
    fn build(values: Vec<Option<String>>) -> StrCol {
        let mut lookup: FxHashMap<Box<str>, u32> = FxHashMap::default();
        let mut dict: Vec<Box<str>> = vec!["".into()];
        let codes = values
            .into_iter()
            .map(|v| match v {
                None => 0,
                Some(s) => {
                    if let Some(&c) = lookup.get(s.as_str()) {
                        return c;
                    }
                    let c = dict.len() as u32;
                    let b: Box<str> = s.into_boxed_str();
                    dict.push(b.clone());
                    lookup.insert(b, c);
                    c
                }
            })
            .collect();
        let lower = dict.iter().map(|s| s.to_lowercase().into_boxed_str()).collect();
        StrCol { codes, dict, lower }
    }
}

pub struct TagCol {
    pub offsets: Vec<u32>,
    pub values: Vec<u32>,
}

impl TagCol {
    #[inline]
    pub fn get(&self, slot: u32) -> &[u32] {
        let s = slot as usize;
        &self.values[self.offsets[s] as usize..self.offsets[s + 1] as usize]
    }
}

pub struct TagDef {
    pub lower: String,
    pub all_parents: Vec<u32>,
    pub all_children: Vec<u32>,
}

pub struct Data {
    pub words: Vec<String>,
    pub text: StrCol,
    pub label: StrCol,
    pub number: Vec<f64>,
    pub score: Vec<f64>,
    pub date: Vec<f64>,
    pub check: Vec<u8>,
    pub tags: TagCol,
    /// Indexed by tag id; entry 0 is unused.
    pub tag_defs: Vec<TagDef>,
}

pub fn generate(n: usize) -> Data {
    let mut r = Rng::new(1);
    let mut words: Vec<String> = Vec::with_capacity(N_WORDS);
    let mut seen = rustc_hash::FxHashSet::default();
    while words.len() < N_WORDS {
        let len = 2 + r.int(3);
        let mut w = String::new();
        for _ in 0..len {
            w.push_str(SYL[r.int(32) as usize]);
        }
        if seen.insert(w.clone()) {
            words.push(w);
        }
    }

    let mut r = Rng::new(2);
    let text: Vec<Option<String>> = (0..n)
        .map(|_| {
            if r.next() < 0.08 {
                return None;
            }
            let a = &words[r.int(N_WORDS as u32) as usize];
            let b = &words[r.int(N_WORDS as u32) as usize];
            let c = &words[r.int(N_WORDS as u32) as usize];
            let num = r.int(10000);
            let cap = a[..1].to_uppercase() + &a[1..];
            Some(format!("{cap}_{b}_{c}_{num}.jpg"))
        })
        .collect();
    let mut r = Rng::new(3);
    let label: Vec<Option<String>> =
        (0..n).map(|_| if r.next() < 0.1 { None } else { Some(words[r.int(N_LABELS) as usize].clone()) }).collect();

    let mut r = Rng::new(4);
    let number = (0..n).map(|_| if r.next() < 0.05 { f64::NAN } else { r.int(10000) as f64 }).collect();
    let mut r = Rng::new(5);
    let score = (0..n).map(|_| if r.next() < 0.05 { f64::NAN } else { r.next() * 1000.0 }).collect();
    let mut r = Rng::new(6);
    let date = (0..n).map(|_| if r.next() < 0.05 { f64::NAN } else { DATE_BASE + (r.next() * DATE_SPAN).floor() }).collect();
    let mut r = Rng::new(7);
    let check = (0..n).map(|_| if r.next() < 0.1 { 255 } else if r.next() < 0.5 { 1 } else { 0 }).collect();

    let mut r = Rng::new(9);
    let mut parent = vec![0u32; N_TAGS + 1];
    for id in 1..=N_TAGS as u32 {
        parent[id as usize] = if id > 50 && r.next() < 0.6 { 1 + r.int(id - 1) } else { 0 };
    }
    let mut tag_defs: Vec<TagDef> = (0..=N_TAGS)
        .map(|id| {
            let mut all_parents = Vec::new();
            let mut p = if id == 0 { 0 } else { parent[id] };
            while p != 0 {
                all_parents.push(p);
                p = parent[p as usize];
            }
            let value = if id == 0 { String::new() } else { words[N_WORDS - N_TAGS + id - 1].clone() };
            TagDef { lower: value.to_lowercase(), all_parents, all_children: Vec::new() }
        })
        .collect();
    for id in 1..=N_TAGS {
        for p in tag_defs[id].all_parents.clone() {
            tag_defs[p as usize].all_children.push(id as u32);
        }
    }

    let mut r = Rng::new(8);
    let mut offsets = Vec::with_capacity(n + 1);
    let mut values = Vec::new();
    offsets.push(0u32);
    let mut arr: Vec<u32> = Vec::with_capacity(6);
    for _ in 0..n {
        arr.clear();
        let k = r.int(6);
        for _ in 0..k {
            let x = r.next();
            let id = 1 + (x * x * N_TAGS as f64).floor() as u32;
            if !arr.contains(&id) {
                arr.push(id);
            }
        }
        values.extend_from_slice(&arr);
        offsets.push(values.len() as u32);
    }

    Data {
        words,
        text: StrCol::build(text),
        label: StrCol::build(label),
        number,
        score,
        date,
        check,
        tags: TagCol { offsets, values },
        tag_defs,
    }
}

/// The ways an op can refer to a column.
#[derive(Clone, Copy, Debug)]
pub enum Col {
    Text,
    Label,
    Number,
    Score,
    Date,
    Check,
    Tags,
}

impl Data {
    pub fn f64_col(&self, c: Col) -> &[f64] {
        match c {
            Col::Number => &self.number,
            Col::Score => &self.score,
            Col::Date => &self.date,
            _ => panic!("{c:?} is not numeric"),
        }
    }
    pub fn str_col(&self, c: Col) -> &StrCol {
        match c {
            Col::Text => &self.text,
            Col::Label => &self.label,
            _ => panic!("{c:?} is not a string column"),
        }
    }
}

/// Order-preserving map of an f64 onto a u64 (NaN must be replaced before).
#[inline]
pub fn f64_key(v: f64) -> u64 {
    let b = v.to_bits();
    if b >> 63 == 1 { !b } else { b | (1 << 63) }
}

/// Wrapper to share a raw output pointer across rayon tasks that write disjoint ranges.
#[derive(Clone, Copy)]
pub struct SyncPtr<T>(pub *mut T);
unsafe impl<T> Send for SyncPtr<T> {}
unsafe impl<T> Sync for SyncPtr<T> {}
impl<T> SyncPtr<T> {
    /// # Safety
    /// `i` must be in bounds and no other task may write the same index.
    #[inline]
    pub unsafe fn write(self, i: usize, v: T) {
        unsafe { self.0.add(i).write(v) }
    }
}
