//! Lines benchmark — Rust side: the scroller layout of `panoptic_front/src/components/scrollers`
//! (virtual/scrollLayout.ts + tree/treeLines.ts + grid/gridLines.ts) done by an engine that owns
//! the group tree. Same numbers, same line objects, same checksums as `js/lines.js`.
//!
//! What differs from the front, on purpose (the engine way):
//! * nodes are the tree's own indices (children are already contiguous and after their parent),
//!   so there is no BFS re-indexing and no id → node map;
//! * open state, depth and positions per leaf are arrays, not `Group` objects;
//! * with several threads, reading the nodes, the bottom-up sums (one depth level at a time) and
//!   the all-lines materialization run in parallel on large trees.

use std::time::Instant;

use rayon::prelude::*;
use rustc_hash::FxHashMap;

use crate::data::{Data, Rng, SyncPtr};
use crate::group::{GKey, GroupManager, Level, Node, Tree};
use crate::data::Col;

// treeLines.ts / gridLines.ts / TreeScroller.vue / GridScroller.vue constants.
const MARGIN_STEP: f64 = 19.0;
const GAP: f64 = 8.0;
const BORDER: f64 = 2.0;
const GROUP_LINE_SIZE: f64 = 30.0;
const GRID_GROUP_LINE_SIZE: f64 = 35.0;
const WIDTH_OFFSET: f64 = 17.0;
const VH: f64 = 1000.0;
const OVERSCAN: f64 = 300.0;
const WIDTHS: [f64; 3] = [800.0, 1440.0, 2560.0];
const IMAGES: [f64; 2] = [100.0, 200.0];
const ROWS: [f64; 2] = [104.0, 28.0];
const PROPS: u32 = 2;
const PILE_PROPS: u32 = 1;
const PAR_NODES: usize = 1 << 14;
const PAR_LINES: usize = 1 << 16;

#[inline]
fn mix(h: u32, v: u32) -> u32 {
    h.wrapping_mul(31).wrapping_add(v)
}
#[inline]
fn lowbit(j: usize) -> usize {
    j & j.wrapping_neg()
}
fn highest_pow2(n: usize) -> usize {
    let mut p = 1;
    while p * 2 <= n {
        p *= 2;
    }
    p
}

// ── the result the layout reads ────────────────────────────────────────────────

/// A group tree as the engine would hold it for display.
pub struct Host {
    pub tree: Tree,
    pub depth: Vec<u32>,
    /// Positions of a leaf: its images, or its piles in sha1 mode.
    pub positions: Vec<u32>,
    /// Piled leaves: (first slot, size) of each pile, `pile_start[node]..` into `piles`.
    pub pile_start: Vec<u32>,
    pub piles: Vec<(u32, u32)>,
    pub piled: bool,
    pub closed: Vec<bool>,
    pub groups: usize,
    pub leaves: usize,
}

impl Host {
    fn new(tree: Tree, sha1: Option<&[u32]>) -> Host {
        let n = tree.nodes.len();
        let mut depth = vec![0u32; n];
        for i in 0..n {
            let nd = &tree.nodes[i];
            for c in nd.first_child..nd.first_child + nd.n_children {
                depth[c as usize] = depth[i] + 1;
            }
        }
        let mut positions = vec![0u32; n];
        let mut pile_start = vec![0u32; n + 1];
        let mut piles = Vec::new();
        let mut leaves = 0;
        let mut seen: FxHashMap<u32, u32> = FxHashMap::default();
        for i in 0..n {
            let nd = &tree.nodes[i];
            pile_start[i] = piles.len() as u32;
            if nd.n_children != 0 {
                continue;
            }
            leaves += 1;
            let slots = &tree.slots[nd.start as usize..(nd.start + nd.len) as usize];
            match sha1 {
                None => positions[i] = nd.len,
                Some(sha1) => {
                    // sha1Piles.computeSha1Piles: piles in first-seen order.
                    seen.clear();
                    let base = piles.len();
                    for &s in slots {
                        let k = *seen.entry(sha1[s as usize]).or_insert_with(|| {
                            piles.push((s, 0));
                            (piles.len() - 1 - base) as u32
                        });
                        piles[base + k as usize].1 += 1;
                    }
                    positions[i] = (piles.len() - base) as u32;
                }
            }
        }
        pile_start[n] = piles.len() as u32;
        Host { depth, positions, pile_start, piles, piled: sha1.is_some(), closed: vec![false; n], groups: n - 1, leaves, tree }
    }
    #[inline]
    fn node(&self, i: usize) -> &Node {
        &self.tree.nodes[i]
    }
    #[inline]
    fn is_leaf(&self, i: usize) -> bool {
        self.tree.nodes[i].n_children == 0
    }
    #[inline]
    fn has_slots(&self, i: usize) -> bool {
        self.tree.nodes[i].len > 0
    }
}

// ── the two sources ─────────────────────────────────────────────────────────────

#[derive(Clone, Copy, Default)]
struct Geo {
    per_line: u32,
    size: f64,
}

/// TreeGeometry.get: images per line and line height for (depth, piled).
fn tree_geo(content_width: f64, image: f64, depth: u32, piled: bool) -> Geo {
    let width = content_width - (depth as f64 + 1.0) * MARGIN_STEP;
    let per = (width / (image + BORDER + GAP)).floor().max(1.0);
    // fillWidths
    let card_area = width - GAP * (per - 1.0);
    let base_outer = (card_area / per).floor();
    let line_img = (base_outer - BORDER).max(1.0);
    // cardLineSize
    let pc = if piled { PILE_PROPS } else { PROPS };
    let mut off = 0.0;
    if pc > 0 {
        off += 28.0;
    }
    if pc > 1 {
        off += (pc - 1) as f64 * 26.0;
    }
    Geo { per_line: per as u32, size: line_img + off + 6.0 }
}

#[derive(Clone, Copy, PartialEq)]
enum View {
    Grid,
    Table,
}

struct Source {
    view: View,
    /// Grid: geometry per depth (piled or not, the host decides).
    geo: Vec<Geo>,
    row: f64,
    content_width: f64,
    image: f64,
}

impl Source {
    fn grid(host: &Host, w: f64, image: f64) -> Source {
        let mut s = Source { view: View::Grid, geo: Vec::new(), row: 0.0, content_width: 0.0, image: 0.0 };
        s.set_grid(host, w, image);
        s
    }
    fn table(row: f64) -> Source {
        Source { view: View::Table, geo: Vec::new(), row, content_width: 0.0, image: 0.0 }
    }
    /// TreeGeometry.setParams: false when nothing changed.
    fn set_grid(&mut self, host: &Host, w: f64, image: f64) -> bool {
        let cw = (w - WIDTH_OFFSET).max(0.0);
        if cw == self.content_width && image == self.image && !self.geo.is_empty() {
            return false;
        }
        self.content_width = cw;
        self.image = image;
        let max_depth = host.depth.iter().copied().max().unwrap_or(0);
        self.geo = (0..=max_depth).map(|d| tree_geo(cw, image, d, host.piled)).collect();
        true
    }
    #[inline]
    fn header(&self, host: &Host, i: usize) -> f64 {
        match self.view {
            View::Grid => GROUP_LINE_SIZE,
            View::Table => {
                if host.is_leaf(i) && i != 0 {
                    GRID_GROUP_LINE_SIZE
                } else {
                    0.0
                }
            }
        }
    }
    #[inline]
    fn body_lines(&self, host: &Host, i: usize) -> u32 {
        if !host.is_leaf(i) || !host.has_slots(i) {
            return 0;
        }
        match self.view {
            View::Grid => host.positions[i].div_ceil(self.geo[host.depth[i] as usize].per_line),
            View::Table => host.positions[i],
        }
    }
    #[inline]
    fn estimate(&self, host: &Host, i: usize) -> f64 {
        match self.view {
            View::Grid => self.geo[host.depth[i] as usize].size,
            View::Table => self.row,
        }
    }
}

// ── ScrollLayout ────────────────────────────────────────────────────────────────

struct MeasuredBody {
    sizes: FxHashMap<u32, f64>,
    fen: Vec<f64>,
    n: usize,
    est: f64,
    total: f64,
}

impl MeasuredBody {
    fn new(n: usize, est: f64) -> Self {
        let mut fen = vec![0.0; n + 1];
        for j in 1..=n {
            fen[j] = est * lowbit(j) as f64;
        }
        MeasuredBody { sizes: FxHashMap::default(), fen, n, est, total: n as f64 * est }
    }
    fn size(&self, i: u32) -> f64 {
        self.sizes.get(&i).copied().unwrap_or(self.est)
    }
    fn set(&mut self, i: u32, px: f64) -> f64 {
        let delta = px - self.size(i);
        if px == self.est {
            self.sizes.remove(&i);
        } else {
            self.sizes.insert(i, px);
        }
        if delta != 0.0 {
            let mut j = i as usize + 1;
            while j <= self.n {
                self.fen[j] += delta;
                j += lowbit(j);
            }
            self.total += delta;
        }
        delta
    }
    fn prefix(&self, i: usize) -> f64 {
        let mut s = 0.0;
        let mut j = i.min(self.n);
        while j > 0 {
            s += self.fen[j];
            j -= lowbit(j);
        }
        s
    }
    fn find(&self, off: f64) -> usize {
        if self.n == 0 {
            return 0;
        }
        let (mut pos, mut rem) = (0usize, off);
        let mut step = highest_pow2(self.n);
        while step > 0 {
            let q = pos + step;
            if q <= self.n && self.fen[q] <= rem {
                pos = q;
                rem -= self.fen[q];
            }
            step >>= 1;
        }
        pos.min(self.n - 1)
    }
}

#[derive(Clone, Copy)]
struct Located {
    node: u32,
    index: i32,
    top: f64,
}

struct Layout {
    header: Vec<f64>,
    lines: Vec<u32>,
    est: Vec<f64>,
    open: Vec<u8>,
    height: Vec<f64>,
    child_sum: Vec<f64>,
    fen: Vec<f64>,
    measured: FxHashMap<u32, MeasuredBody>,
    /// Node indices by depth, for the parallel bottom-up sums.
    levels: Vec<Vec<u32>>,
    par: bool,
}

impl Layout {
    fn new(host: &Host) -> Layout {
        let n = host.tree.nodes.len();
        let max_depth = host.depth.iter().copied().max().unwrap_or(0) as usize;
        let mut levels = vec![Vec::new(); max_depth + 1];
        for i in 0..n {
            levels[host.depth[i] as usize].push(i as u32);
        }
        Layout {
            header: vec![0.0; n],
            lines: vec![0; n],
            est: vec![1.0; n],
            open: vec![0; n],
            height: vec![0.0; n],
            child_sum: vec![0.0; n],
            fen: vec![0.0; n],
            measured: FxHashMap::default(),
            levels,
            par: rayon::current_num_threads() > 1 && n >= PAR_NODES,
        }
    }

    fn total(&self) -> f64 {
        self.height.first().copied().unwrap_or(0.0)
    }

    #[inline]
    fn read_one(src: &Source, host: &Host, i: usize) -> (u8, f64, u32, f64) {
        let open = !host.closed[i] as u8;
        let header = src.header(host, i).round().max(0.0);
        let lines = if host.is_leaf(i) { src.body_lines(host, i) } else { 0 };
        let est = if lines > 0 { src.estimate(host, i).round().max(1.0) } else { 1.0 };
        (open, header, lines, est)
    }

    fn read_all(&mut self, src: &Source, host: &Host) {
        let n = host.tree.nodes.len();
        if self.par {
            let (open, (header, (lines, est))): (Vec<u8>, (Vec<f64>, (Vec<u32>, Vec<f64>))) = (0..n)
                .into_par_iter()
                .with_min_len(4096)
                .map(|i| {
                    let (o, h, l, e) = Self::read_one(src, host, i);
                    (o, (h, (l, e)))
                })
                .unzip();
            self.open = open;
            self.header = header;
            self.lines = lines;
            self.est = est;
        } else {
            for i in 0..n {
                let (o, h, l, e) = Self::read_one(src, host, i);
                self.open[i] = o;
                self.header[i] = h;
                self.lines[i] = l;
                self.est[i] = e;
            }
        }
        // ScrollLayout.readNode: a measured body whose line count or estimate changed is redone.
        let stale: Vec<u32> = self
            .measured
            .iter()
            .filter(|(i, b)| b.n != self.lines[**i as usize] as usize || b.est != self.est[**i as usize])
            .map(|(i, _)| *i)
            .collect();
        for i in stale {
            let (l, e) = (self.lines[i as usize] as usize, self.est[i as usize]);
            if l > 0 {
                let old = self.measured.remove(&i).unwrap();
                let mut b = MeasuredBody::new(l, e);
                for (&k, &px) in &old.sizes {
                    if (k as usize) < l {
                        b.set(k, px);
                    }
                }
                self.measured.insert(i, b);
            } else {
                self.measured.remove(&i);
            }
        }
    }

    #[inline]
    fn body_height(&self, i: usize) -> f64 {
        self.measured.get(&(i as u32)).map_or(self.lines[i] as f64 * self.est[i], |b| b.total)
    }

    #[inline]
    fn own_height(&self, host: &Host, i: usize) -> f64 {
        if self.open[i] == 0 {
            return self.header[i];
        }
        self.header[i] + if host.is_leaf(i) { self.body_height(i) } else { self.child_sum[i] }
    }

    /// Heights + Fenwick trees of node i's children; i's own height. Children are done.
    #[inline]
    unsafe fn sum_node(&self, host: &Host, i: usize, fen: SyncPtr<f64>, child_sum: SyncPtr<f64>, height: SyncPtr<f64>) {
        let nd = host.node(i);
        let k = nd.n_children as usize;
        let mut cs = 0.0;
        if k > 0 {
            let b = nd.first_child as usize - 1;
            for j in 1..=k {
                let h = self.height[b + j];
                unsafe { fen.write(b + j, h) };
                cs += h;
            }
            for j in 1..=k {
                let q = j + lowbit(j);
                if q <= k {
                    unsafe {
                        let v = *fen.0.add(b + j);
                        *fen.0.add(b + q) += v;
                    }
                }
            }
        }
        unsafe { child_sum.write(i, cs) };
        let h = if self.open[i] == 0 {
            self.header[i]
        } else {
            self.header[i] + if k == 0 { self.body_height(i) } else { cs }
        };
        unsafe { height.write(i, h) };
    }

    fn sum_all(&mut self, host: &Host) {
        let fen = SyncPtr(self.fen.as_mut_ptr());
        let child_sum = SyncPtr(self.child_sum.as_mut_ptr());
        let height = SyncPtr(self.height.as_mut_ptr());
        if self.par {
            for d in (0..self.levels.len()).rev() {
                let me = &*self;
                // SAFETY: a node writes its own height / child_sum and the fen slots of its own
                // children, which no other node of the level owns; it reads the level below only.
                me.levels[d].par_iter().with_min_len(1024).for_each(|&i| unsafe { me.sum_node(host, i as usize, fen, child_sum, height) });
            }
        } else {
            for i in (0..host.tree.nodes.len()).rev() {
                // SAFETY: single thread.
                unsafe { self.sum_node(host, i, fen, child_sum, height) };
            }
        }
    }

    /// ScrollLayout.rebuild (minus re-indexing: the tree's indices are the layout's).
    fn rebuild(&mut self, src: &Source, host: &Host) {
        self.measured.clear();
        self.read_all(src, host);
        self.sum_all(host);
    }

    /// ScrollLayout.refresh: same shape, every node read again.
    fn refresh(&mut self, src: &Source, host: &Host) {
        self.read_all(src, host);
        self.sum_all(host);
    }

    fn parent(host: &Host, i: usize, parents: &[u32]) -> Option<usize> {
        let _ = host;
        if i == 0 { None } else { Some(parents[i] as usize) }
    }

    /// ScrollLayout.refreshNode.
    fn refresh_node(&mut self, src: &Source, host: &Host, parents: &[u32], i: usize) {
        let (o, h, l, e) = Self::read_one(src, host, i);
        self.open[i] = o;
        self.header[i] = h;
        self.lines[i] = l;
        self.est[i] = e;
        let delta = self.own_height(host, i) - self.height[i];
        self.propagate(host, parents, i, delta, false);
    }

    fn propagate(&mut self, host: &Host, parents: &[u32], i: usize, delta: f64, body_only: bool) {
        if delta == 0.0 || (body_only && self.open[i] == 0) {
            return;
        }
        self.height[i] += delta;
        let mut c = i;
        while let Some(p) = Self::parent(host, c, parents) {
            let nd = host.node(p);
            let (k, b) = (nd.n_children as usize, nd.first_child as usize - 1);
            let mut j = c - b;
            while j <= k {
                self.fen[b + j] += delta;
                j += lowbit(j);
            }
            self.child_sum[p] += delta;
            if self.open[p] == 0 {
                return;
            }
            self.height[p] += delta;
            c = p;
        }
    }

    fn set_measured(&mut self, host: &Host, parents: &[u32], node: u32, index: i32, px: f64) -> bool {
        let i = node as usize;
        if index < 0 || index as u32 >= self.lines[i] {
            return false;
        }
        let px = px.round().max(1.0);
        if !self.measured.contains_key(&node) {
            if px == self.est[i] {
                return false;
            }
            self.measured.insert(node, MeasuredBody::new(self.lines[i] as usize, self.est[i]));
        }
        let delta = self.measured.get_mut(&node).unwrap().set(index as u32, px);
        if delta == 0.0 {
            return false;
        }
        if self.open[i] != 0 {
            self.propagate(host, parents, i, delta, true);
        }
        true
    }

    fn clear_measured(&mut self, host: &Host) {
        if self.measured.is_empty() {
            return;
        }
        self.measured.clear();
        self.sum_all(host);
    }

    fn fen_prefix(&self, host: &Host, p: usize, j0: usize) -> f64 {
        let b = host.node(p).first_child as usize - 1;
        let mut s = 0.0;
        let mut j = j0;
        while j > 0 {
            s += self.fen[b + j];
            j -= lowbit(j);
        }
        s
    }

    fn fen_find(&self, host: &Host, p: usize, off: f64) -> (usize, f64) {
        let nd = host.node(p);
        let (k, b) = (nd.n_children as usize, nd.first_child as usize - 1);
        let (mut pos, mut rem) = (0usize, off);
        let mut step = highest_pow2(k);
        while step > 0 {
            let q = pos + step;
            if q <= k && self.fen[b + q] <= rem {
                pos = q;
                rem -= self.fen[b + q];
            }
            step >>= 1;
        }
        if pos < k {
            return (pos, rem);
        }
        for j in (0..k).rev() {
            let h = self.height[b + 1 + j];
            if h > 0.0 {
                return (j, (rem + h).min(h - 1e-6).max(0.0));
            }
        }
        (0, 0.0)
    }

    fn locate(&self, host: &Host, offset: f64) -> Option<Located> {
        let total = self.total();
        if self.height.is_empty() || total <= 0.0 {
            return None;
        }
        let mut off = offset.max(0.0).min(total - 1e-6);
        let (mut i, mut top) = (0usize, 0.0);
        loop {
            let h = self.header[i];
            if off < h || self.open[i] == 0 {
                return Some(Located { node: i as u32, index: -1, top });
            }
            off -= h;
            top += h;
            if host.is_leaf(i) {
                let lines = self.lines[i] as f64;
                let k = if let Some(b) = self.measured.get(&(i as u32)) {
                    let k = b.find(off);
                    top += b.prefix(k);
                    k as f64
                } else {
                    let k = (lines - 1.0).min((off / self.est[i]).floor());
                    top += k * self.est[i];
                    k
                };
                return Some(Located { node: i as u32, index: k.max(0.0) as i32, top });
            }
            let (j, rem) = self.fen_find(host, i, off);
            top += off - rem;
            off = rem;
            i = host.node(i).first_child as usize + j;
        }
    }

    fn offset_of(&self, host: &Host, parents: &[u32], node: u32, index: i32) -> f64 {
        let i = node as usize;
        let mut top = 0.0;
        if index >= 0 {
            top += self.header[i]
                + self.measured.get(&node).map_or(index as f64 * self.est[i], |b| b.prefix(index as usize));
        }
        let mut c = i;
        while let Some(p) = Self::parent(host, c, parents) {
            top += self.header[p] + self.fen_prefix(host, p, c - host.node(p).first_child as usize);
            c = p;
        }
        top
    }

    fn size_of(&self, l: &Located) -> f64 {
        let i = l.node as usize;
        if l.index < 0 {
            return self.header[i];
        }
        self.measured.get(&l.node).map_or(self.est[i], |b| b.size(l.index as u32))
    }
}

// ── line objects ──────────────────────────────────────────────────────────────

/// What the front's leafLine / group line / gridRow / gridGroupLine hold, minus the strings.
#[derive(Clone, Copy, Default)]
struct Line {
    kind: u8, // 1 header, 2 image/pile line (grid), 3 image row, 4 pile row (table)
    node: u32,
    depth: u32,
    start: u32,
    count: u32,
    size: f64,
    id: u32,
    pile: u32,
}

fn make_line(src: &Source, host: &Host, node: u32, index: i32) -> Line {
    let i = node as usize;
    if index < 0 {
        return Line { kind: 1, node, depth: host.depth[i], size: src.header(host, i), ..Default::default() };
    }
    let k = index as u32;
    match src.view {
        View::Grid => {
            let g = src.geo[host.depth[i] as usize];
            let start = k * g.per_line;
            let count = g.per_line.min(host.positions[i].saturating_sub(start));
            Line { kind: 2, node, depth: host.depth[i] + 1, start, count, size: g.size, ..Default::default() }
        }
        View::Table => {
            if host.piled {
                let (first, size) = host.piles[(host.pile_start[i] + k) as usize];
                Line { kind: 4, node, id: first + 1, pile: size, ..Default::default() }
            } else {
                let s = host.tree.slots[(host.node(i).start + k) as usize];
                Line { kind: 3, node, id: s + 1, start: k, ..Default::default() }
            }
        }
    }
}

fn hash_line(h: u32, l: &Line, src: &Source) -> u32 {
    match l.kind {
        1 => mix(mix(mix(h, 1), l.depth), if src.view == View::Grid { GROUP_LINE_SIZE as u32 } else { GRID_GROUP_LINE_SIZE as u32 }),
        2 => mix(mix(mix(mix(mix(h, 2), l.depth), l.start), l.count), l.size as u32),
        3 => mix(mix(h, 3), l.id),
        _ => mix(mix(mix(h, 4), l.id), l.pile),
    }
}

/// Visible nodes in display order with their line counts (header? + body if open).
fn display_nodes(src: &Source, host: &Host, lay: &Layout) -> (Vec<u32>, Vec<u64>) {
    let mut order = Vec::new();
    let mut starts = Vec::new();
    let mut total = 0u64;
    let mut stack = vec![0u32];
    while let Some(i) = stack.pop() {
        let iu = i as usize;
        let nd = host.node(iu);
        let header = (src.header(host, iu) > 0.0) as u64;
        let open = lay.open[iu] != 0;
        let body = if open && nd.n_children == 0 { lay.lines[iu] as u64 } else { 0 };
        if header + body > 0 {
            order.push(i);
            starts.push(total);
            total += header + body;
        }
        if open && nd.n_children > 0 {
            stack.extend((nd.first_child..nd.first_child + nd.n_children).rev());
        }
    }
    starts.push(total);
    (order, starts)
}

/// Every line object of the list, in display order.
fn all_lines(src: &Source, host: &Host, lay: &Layout) -> Vec<Line> {
    let (order, starts) = display_nodes(src, host, lay);
    let total = *starts.last().unwrap() as usize;
    let mut out: Vec<Line> = Vec::with_capacity(total);
    let fill = |k: usize, ptr: SyncPtr<Line>| {
        let i = order[k];
        let iu = i as usize;
        let mut at = starts[k] as usize;
        if src.header(host, iu) > 0.0 {
            // SAFETY: node k owns lines [starts[k], starts[k + 1]).
            unsafe { ptr.write(at, make_line(src, host, i, -1)) };
            at += 1;
        }
        if lay.open[iu] != 0 && host.is_leaf(iu) {
            for j in 0..lay.lines[iu] {
                unsafe { ptr.write(at, make_line(src, host, i, j as i32)) };
                at += 1;
            }
        }
    };
    let ptr = SyncPtr(out.as_mut_ptr());
    if rayon::current_num_threads() > 1 && total >= PAR_LINES {
        (0..order.len()).into_par_iter().with_min_len(256).for_each(|k| fill(k, ptr));
    } else {
        (0..order.len()).for_each(|k| fill(k, ptr));
    }
    // SAFETY: every index below `total` was written exactly once above.
    unsafe { out.set_len(total) };
    out
}

fn window_at(src: &Source, host: &Host, lay: &Layout, y: f64) -> Vec<(Located, Line)> {
    let (from, to) = ((y - OVERSCAN).max(0.0), y + VH + OVERSCAN);
    let mut items = Vec::new();
    let mut line = lay.locate(host, from);
    while let Some(l) = line {
        if l.top >= to {
            break;
        }
        items.push((l, make_line(src, host, l.node, l.index)));
        let end = l.top + lay.size_of(&l);
        line = if end < lay.total() { lay.locate(host, end) } else { None }.filter(|n| n.top > l.top);
    }
    items
}

// ── driver ─────────────────────────────────────────────────────────────────────

fn median_ms(mut t: Vec<f64>) -> (f64, f64) {
    t.sort_by(|a, b| a.partial_cmp(b).unwrap());
    (t[t.len() / 2], t[0])
}

fn time(warmup: usize, reps: usize, mut f: impl FnMut()) -> (f64, f64) {
    for _ in 0..warmup {
        f();
    }
    let mut t = Vec::with_capacity(reps);
    for _ in 0..reps {
        let t0 = Instant::now();
        f();
        t.push(t0.elapsed().as_secs_f64() * 1000.0);
    }
    median_ms(t)
}

struct Emit<'a> {
    imp: &'a str,
    n: usize,
}

impl Emit<'_> {
    fn line(&self, view: View, tree: &str, cfg: &str, op: &str, (ms, min): (f64, f64), extra: &str) {
        let v = if view == View::Grid { "grid" } else { "table" };
        println!(
            r#"{{"impl":"{}","n":{},"view":"{v}","tree":"{tree}","cfg":"{cfg}","op":"{op}","ms":{ms:.6},"min_ms":{min:.6}{extra}}}"#,
            self.imp, self.n
        );
    }
}

fn run_view(e: &Emit, tree: &str, host: &mut Host, view: View, reps: usize, warmup: usize) {
    let parents: Vec<u32> = {
        let mut p = vec![0u32; host.tree.nodes.len()];
        for (i, nd) in host.tree.nodes.iter().enumerate() {
            for c in nd.first_child..nd.first_child + nd.n_children {
                p[c as usize] = i as u32;
            }
        }
        p
    };
    let (def_w, def_i, def_row) = (1440.0, 200.0, 104.0);
    let mut src = if view == View::Grid { Source::grid(host, def_w, def_i) } else { Source::table(def_row) };
    let mut lay = Layout::new(host);
    lay.rebuild(&src, host);
    let base = if view == View::Grid { format!("w{def_w} i{def_i}") } else { format!("row{def_row}") };
    let t = time(warmup, reps, || lay.rebuild(&src, host));
    let extra = format!(r#","nodes":{},"groups":{},"leaves":{},"height":{}"#, host.tree.nodes.len(), host.groups, host.leaves, lay.total());
    e.line(view, tree, &base, "build", t, &extra);

    let configs: Vec<(f64, f64)> = if view == View::Grid {
        WIDTHS.iter().flat_map(|&w| IMAGES.iter().map(move |&i| (w, i))).collect()
    } else {
        ROWS.iter().map(|&r| (r, 0.0)).collect()
    };
    for c in configs {
        let name = if view == View::Grid { format!("w{} i{}", c.0, c.1) } else { format!("row{}", c.0) };
        let other = if name == base { if view == View::Grid { (800.0, 100.0) } else { (28.0, 0.0) } } else if view == View::Grid { (def_w, def_i) } else { (def_row, 0.0) };
        let apply = |src: &mut Source, lay: &mut Layout, host: &Host, cc: (f64, f64)| {
            if view == View::Grid {
                src.set_grid(host, cc.0, cc.1);
            } else {
                src.row = cc.0;
            }
            lay.refresh(src, host);
        };
        let mut ts = Vec::new();
        for r in 0..warmup + reps {
            apply(&mut src, &mut lay, host, other);
            let t0 = Instant::now();
            apply(&mut src, &mut lay, host, c);
            if r >= warmup {
                ts.push(t0.elapsed().as_secs_f64() * 1000.0);
            }
        }
        e.line(view, tree, &name, if view == View::Grid { "resize" } else { "row size" }, median_ms(ts), &format!(r#","height":{}"#, lay.total()));
        let lines = all_lines(&src, host, &lay);
        let (mut h, mut height) = (0u32, 0.0);
        for l in &lines {
            h = hash_line(h, l, &src);
            height += if l.kind == 1 { l.size } else { lay.est[l.node as usize] };
        }
        let check = format!(r#","lines":{},"height":{height},"hash":{h},"layout_height":{}"#, lines.len(), lay.total());
        drop(lines);
        let t = time(warmup.min(1), reps.min(3), || drop(all_lines(&src, host, &lay)));
        e.line(view, tree, &name, "all lines", t, &check);
    }
    if view == View::Grid {
        src.set_grid(host, def_w, def_i);
    } else {
        src.row = def_row;
    }
    lay.refresh(&src, host);

    let root = host.node(0).clone();
    if root.n_children > 0 {
        let g = (root.first_child + root.n_children / 2) as usize;
        let t = time(warmup, reps * 4, || {
            for _ in 0..100 {
                host.closed[g] = true;
                lay.refresh_node(&src, host, &parents, g);
                host.closed[g] = false;
                lay.refresh_node(&src, host, &parents, g);
            }
        });
        e.line(view, tree, &base, "toggle one", (t.0 / 100.0, t.1 / 100.0), r#","per":"close+open""#);
        let (mut tc, mut to, mut closed_h) = (Vec::new(), Vec::new(), 0.0);
        let n = host.closed.len();
        for r in 0..warmup + reps {
            let t0 = Instant::now();
            host.closed[1..n].fill(true);
            lay.refresh(&src, host);
            let c = t0.elapsed().as_secs_f64() * 1000.0;
            if r == 0 {
                closed_h = lay.total();
            }
            let t0 = Instant::now();
            host.closed[1..n].fill(false);
            lay.refresh(&src, host);
            let o = t0.elapsed().as_secs_f64() * 1000.0;
            if r >= warmup {
                tc.push(c);
                to.push(o);
            }
        }
        e.line(view, tree, &base, "close all", median_ms(tc), &format!(r#","height":{closed_h}"#));
        e.line(view, tree, &base, "open all", median_ms(to), &format!(r#","height":{}"#, lay.total()));
    }

    const Q: usize = 10_000;
    let mut rng = Rng::new(42);
    let ys: Vec<f64> = (0..Q).map(|_| (rng.next() * lay.total()).floor()).collect();
    let mut refs = vec![Located { node: 0, index: 0, top: 0.0 }; Q];
    let t = time(warmup, reps, || {
        for (r, &y) in refs.iter_mut().zip(&ys) {
            *r = lay.locate(host, y).unwrap();
        }
    });
    let hl = refs.iter().fold(0u32, |h, r| mix(mix(h, r.top as u64 as u32), r.index as u32));
    e.line(view, tree, &base, "locate", (t.0 / Q as f64, t.1 / Q as f64), &format!(r#","per":"call","hash":{hl}"#));
    let mut offs = vec![0.0; Q];
    let t = time(warmup, reps, || {
        for (o, r) in offs.iter_mut().zip(&refs) {
            *o = lay.offset_of(host, &parents, r.node, r.index);
        }
    });
    let ho = offs.iter().fold(0u32, |h, &o| mix(h, o as u64 as u32));
    e.line(view, tree, &base, "offsetOf", (t.0 / Q as f64, t.1 / Q as f64), &format!(r#","per":"call","hash":{ho}"#));

    let (mut wt, mut hw, mut nw) = (Vec::new(), 0u32, 0usize);
    for i in 0..220 {
        let y = ys[i % Q];
        let t0 = Instant::now();
        let items = window_at(&src, host, &lay, y);
        let dt = t0.elapsed().as_secs_f64() * 1000.0;
        if i >= 20 {
            wt.push(dt);
            for (l, it) in &items {
                hw = hash_line(mix(hw, l.top as u64 as u32), it, &src);
                nw += 1;
            }
        }
    }
    e.line(view, tree, &base, "window", median_ms(wt), &format!(r#","lines":{},"hash":{hw}"#, (nw as f64 / 200.0).round()));

    if view == View::Table {
        let screen: Vec<Located> = window_at(&src, host, &lay, ys[0]).into_iter().map(|(l, _)| l).filter(|l| l.index >= 0).collect();
        let mut tm = Vec::new();
        for r in 0..warmup + reps {
            lay.clear_measured(host);
            let t0 = Instant::now();
            for l in &screen {
                lay.set_measured(host, &parents, l.node, l.index, src.row + 7.0);
            }
            if r >= warmup {
                tm.push(t0.elapsed().as_secs_f64() * 1000.0);
            }
        }
        e.line(view, tree, &base, "measure screen", median_ms(tm), &format!(r#","rows":{},"height":{}"#, screen.len(), lay.total()));
        lay.clear_measured(host);
    }
}

pub fn build_host(d: &Data, n: usize, tree: &str) -> Host {
    let all: Vec<u32> = (0..n as u32).collect();
    let lv = |key| Level { key, dir: 1 };
    let levels = match tree {
        "flat" => None,
        "label-year" | "label-year-piles" => Some(vec![lv(GKey::Str(Col::Label)), lv(GKey::DateYear)]),
        "tags" => Some(vec![lv(GKey::Tags)]),
        "text" => Some(vec![lv(GKey::Str(Col::Text))]),
        _ => panic!("unknown tree {tree}"),
    };
    let t = match levels {
        None => Tree {
            nodes: vec![Node { len: n as u32, ..Default::default() }],
            root_slots: Vec::new(),
            slots: all.clone(),
            member_offsets: Vec::new(),
            member_values: Vec::new(),
        },
        Some(l) => GroupManager::new(l).group(d, &all),
    };
    let sha1: Option<Vec<u32>> = tree.ends_with("-piles").then(|| {
        let m = ((n as f64 * 0.7).floor() as u32).max(1);
        (0..n as u32).map(|s| s.wrapping_mul(2_654_435_761) % m).collect()
    });
    Host::new(t, sha1.as_deref())
}

pub fn run(d: &Data, n: usize, trees: &[String], views: &[String], threads: &[usize], reps: usize, warmup: usize) {
    for tree in trees {
        let mut host = build_host(d, n, tree);
        for &t in threads {
            let pool = rayon::ThreadPoolBuilder::new().num_threads(t).build().unwrap();
            let imp = format!("rust-{t}t");
            pool.install(|| {
                let e = Emit { imp: &imp, n };
                for v in views {
                    let view = if v == "grid" { View::Grid } else { View::Table };
                    host.closed.fill(false);
                    run_view(&e, tree, &mut host, view, reps, warmup);
                }
            });
        }
    }
}
