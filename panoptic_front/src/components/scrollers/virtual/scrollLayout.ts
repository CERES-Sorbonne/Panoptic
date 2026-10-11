/**
 * The layout of a virtual scroller: which line is at a pixel, where a line starts, how tall the
 * whole list is. No line objects: the content is described by a tree of nodes (a LayoutSource),
 * and the layout keeps a few numbers per node.
 *
 * A node is a group. It may have a header line (headerSize > 0). An open leaf has a body of
 * `bodyLines` lines that share one estimated height; an open inner node shows its children. A
 * flat list (image wall, cluster cards) is a single root node without a header.
 *
 * Storage, all in typed arrays indexed by an internal node index (BFS order, so the children of a
 * node are a contiguous index range and every child comes after its parent):
 *  - `height[i]`: what node i takes on screen — its header, plus its body (open leaf) or the sum of
 *    its children (open inner node);
 *  - `childSum[i]`: the sum of its children's heights, kept up to date even while i is closed;
 *  - `fen`: one Fenwick tree per inner node over its children's heights, stored at the children's
 *    own indices, so the whole forest is one array.
 * Body lines measured on screen (grid rows) live in a per-leaf Fenwick tree over that leaf's line
 * sizes (MeasuredBody), created on the first measurement; other leaves use division.
 *
 * Costs: rebuild and refresh O(groups); locate, offsetOf, refreshNode and setMeasured
 * O(depth · log siblings) (+ log lines for a measured leaf); nothing is ever O(images).
 *
 * Pure on purpose (no Vue, no DOM): the scroller component drives it, the tests check it against a
 * brute-force walk.
 */

export type NodeId = number

export interface LayoutSource {
    // The root node, or undefined when there is nothing to show.
    root(): NodeId | undefined
    childCount(node: NodeId): number
    child(node: NodeId, i: number): NodeId
    isOpen(node: NodeId): boolean
    // Px of the node's header line; 0 = no header line.
    headerSize(node: NodeId): number
    // Lines in a leaf's body (0 for inner nodes, which show their children instead).
    bodyLines(node: NodeId): number
    // Px of every body line of the leaf until it is measured. At least 1.
    lineEstimate(node: NodeId): number
    // Slot pool type of a line (index -1 = the header). Slots are only reused within a type.
    lineType(node: NodeId, index: number): string
}

export interface LineRef {
    node: NodeId
    // -1 = the node's header, 0..bodyLines-1 = a body line.
    index: number
}

export interface LocatedLine extends LineRef {
    // Virtual offset of the line's top.
    top: number
}

export const HEADER = -1

export function lineKey(ref: LineRef): string {
    return ref.node + ':' + ref.index
}

const lowbit = (j: number) => j & -j

function highestPow2(n: number): number {
    let p = 1
    while (p * 2 <= n) p *= 2
    return p
}

/**
 * The line sizes of one measured leaf, as a Fenwick tree (1-based) over its lines: lines never
 * measured count their estimate. O(lines) to create, O(log lines) per change or query.
 */
export class MeasuredBody {
    readonly sizes = new Map<number, number>()
    private fen: Float64Array
    total: number

    constructor(readonly n: number, readonly est: number, from?: MeasuredBody) {
        this.fen = new Float64Array(n + 1)
        // Every node j of a uniform tree covers lowbit(j) lines.
        for (let j = 1; j <= n; j++) this.fen[j] = est * lowbit(j)
        this.total = n * est
        if (from) for (const [i, px] of from.sizes) if (i < n) this.set(i, px)
    }

    size(i: number): number {
        return this.sizes.get(i) ?? this.est
    }

    // The change in the body's total.
    set(i: number, px: number): number {
        const delta = px - this.size(i)
        if (px === this.est) this.sizes.delete(i)
        else this.sizes.set(i, px)
        if (delta) {
            for (let j = i + 1; j <= this.n; j += lowbit(j)) this.fen[j] += delta
            this.total += delta
        }
        return delta
    }

    // Total size of lines [0, i).
    prefix(i: number): number {
        let s = 0
        for (let j = Math.min(i, this.n); j > 0; j -= lowbit(j)) s += this.fen[j]
        return s
    }

    // The line holding body offset `off` (clamped to the last line).
    find(off: number): number {
        if (this.n <= 0) return 0
        let pos = 0, rem = off
        for (let step = highestPow2(this.n); step > 0; step >>= 1) {
            const q = pos + step
            if (q <= this.n && this.fen[q] <= rem) { pos = q; rem -= this.fen[q] }
        }
        return Math.min(pos, this.n - 1)
    }
}

// Growable typed arrays, one slot per node.
class NodeArrays {
    cap = 0
    ids = new Float64Array(0)
    parent = new Int32Array(0)
    first = new Int32Array(0)
    count = new Int32Array(0)
    header = new Float64Array(0)
    lines = new Float64Array(0)
    est = new Float64Array(0)
    open = new Uint8Array(0)
    height = new Float64Array(0)
    childSum = new Float64Array(0)
    fen = new Float64Array(0)

    reserve(n: number) {
        if (n <= this.cap) return
        let cap = Math.max(16, this.cap)
        while (cap < n) cap *= 2
        const grow = <T extends Float64Array | Int32Array | Uint8Array>(a: T): T => {
            const b = new (a.constructor as any)(cap) as T
            b.set(a)
            return b
        }
        this.ids = grow(this.ids)
        this.parent = grow(this.parent)
        this.first = grow(this.first)
        this.count = grow(this.count)
        this.header = grow(this.header)
        this.lines = grow(this.lines)
        this.est = grow(this.est)
        this.open = grow(this.open)
        this.height = grow(this.height)
        this.childSum = grow(this.childSum)
        this.fen = grow(this.fen)
        this.cap = cap
    }
}

export class ScrollLayout {
    private a = new NodeArrays()
    private n = 0
    private index = new Map<NodeId, number>()
    private measured = new Map<number, MeasuredBody>()

    constructor(private source: LayoutSource) { }

    /** Virtual px of the whole list. */
    get height(): number {
        return this.n ? this.a.height[0] : 0
    }

    /** Number of nodes indexed. */
    get nodeCount(): number {
        return this.n
    }

    setSource(source: LayoutSource) {
        this.source = source
    }

    // ── Changes ──────────────────────────────────────────────────────────────

    /**
     * Reads the whole tree again: call it when the tree itself changed (regroup, filter, sort,
     * another manager). O(groups). Measurements are kept for the leaves whose line count and
     * estimate did not change.
     */
    rebuild() {
        const src = this.source
        const a = this.a
        const oldMeasured = new Map<NodeId, MeasuredBody>()
        for (const [i, body] of this.measured) oldMeasured.set(a.ids[i], body)
        this.measured = new Map()
        this.index = new Map()
        this.n = 0

        const root = src.root()
        if (root === undefined || root === null) return
        a.reserve(1)
        this.index.set(root, 0)
        a.ids[0] = root
        a.parent[0] = -1
        let n = 1
        // BFS: the children of node i get the next free indices, so they are contiguous.
        for (let i = 0; i < n; i++) {
            const id = a.ids[i]
            const k = src.childCount(id)
            a.first[i] = n
            a.count[i] = 0
            if (!k) continue
            a.reserve(n + k)
            let added = 0
            for (let j = 0; j < k; j++) {
                const c = src.child(id, j)
                // A node met twice (a cycle, or a shared child) is shown once, at its first place.
                if (this.index.has(c)) continue
                this.index.set(c, n + added)
                a.ids[n + added] = c
                a.parent[n + added] = i
                added++
            }
            a.count[i] = added
            n += added
        }
        this.n = n

        for (let i = 0; i < n; i++) this.readNode(i)
        for (const [id, body] of oldMeasured) {
            const i = this.index.get(id)
            if (i === undefined || a.count[i] || !a.lines[i]) continue
            this.measured.set(i, body.n === a.lines[i] && body.est === a.est[i] ? body : new MeasuredBody(a.lines[i], a.est[i], body))
        }
        this.sumAll()
    }

    /** Shows nothing until the next rebuild. */
    clear() {
        this.n = 0
        this.index = new Map()
        this.measured = new Map()
    }

    /**
     * Reads every node's open state, header, line count and estimate again, keeping the tree's
     * shape: call it after a change of size for every line (image size, properties shown, width).
     * Rebuilds instead when a node's child count changed. O(groups).
     */
    refresh() {
        const a = this.a
        for (let i = 0; i < this.n; i++) {
            if (this.source.childCount(a.ids[i]) !== a.count[i]) return this.rebuild()
        }
        for (let i = 0; i < this.n; i++) this.readNode(i)
        this.sumAll()
    }

    /**
     * One node was opened or closed, or its header, line count or estimate changed. Its ancestors
     * are updated on the way up. O(depth · log siblings). Rebuilds when its children changed.
     * False when the node is unknown.
     */
    refreshNode(node: NodeId): boolean {
        const i = this.index.get(node)
        if (i === undefined) return false
        if (this.source.childCount(node) !== this.a.count[i]) {
            this.rebuild()
            return true
        }
        this.readNode(i)
        // An inner node's children may have changed their open state too (open/close all): their
        // sums are not re-read here — refreshNode them first, or call refresh().
        this.propagate(i, this.ownHeight(i) - this.a.height[i])
        return true
    }

    /**
     * A body line was measured on screen at `px`. False when that is its size already (or the
     * line does not exist). O(depth · log siblings + log lines).
     */
    setMeasured(ref: LineRef, px: number): boolean {
        const i = this.index.get(ref.node)
        const a = this.a
        if (i === undefined || ref.index < 0 || ref.index >= a.lines[i]) return false
        px = Math.max(1, Math.round(px))
        let body = this.measured.get(i)
        if (!body) {
            if (px === a.est[i]) return false
            body = new MeasuredBody(a.lines[i], a.est[i])
            this.measured.set(i, body)
        }
        const delta = body.set(ref.index, px)
        if (!delta) return false
        if (a.open[i]) this.propagate(i, delta, true)
        return true
    }

    /**
     * Forgets the measured sizes (the rows' layout changed), except those of `keep` — the lines on
     * screen, which report again if their size changes. O(groups + kept).
     */
    clearMeasured(keep: Iterable<LineRef> = []) {
        const kept: [LineRef, number][] = []
        for (const ref of keep) {
            const i = this.index.get(ref.node)
            const body = i === undefined ? undefined : this.measured.get(i)
            const px = body?.sizes.get(ref.index)
            if (px !== undefined) kept.push([ref, px])
        }
        if (!this.measured.size) return
        this.measured.clear()
        this.sumAll()
        for (const [ref, px] of kept) this.setMeasured(ref, px)
    }

    // ── Queries ──────────────────────────────────────────────────────────────

    has(node: NodeId): boolean {
        return this.index.has(node)
    }

    /** Whether every ancestor of the node is open (the node itself may be closed). */
    isVisible(node: NodeId): boolean {
        const a = this.a
        let i = this.index.get(node)
        if (i === undefined) return false
        for (let p = a.parent[i]; p >= 0; p = a.parent[p]) if (!a.open[p]) return false
        return true
    }

    /** The node itself when visible, otherwise its outermost closed ancestor. */
    visibleAncestor(node: NodeId): NodeId | undefined {
        const a = this.a
        const i = this.index.get(node)
        if (i === undefined) return undefined
        let out = i
        for (let p = a.parent[i]; p >= 0; p = a.parent[p]) if (!a.open[p]) out = p
        return a.ids[out]
    }

    /** Lines in the node's body, as last read. */
    bodyLines(node: NodeId): number {
        const i = this.index.get(node)
        return i === undefined ? 0 : this.a.lines[i]
    }

    /** Whether the line exists and is shown. */
    isShown(ref: LineRef): boolean {
        const i = this.index.get(ref.node)
        if (i === undefined || !this.isVisible(ref.node)) return false
        if (ref.index < 0) return this.a.header[i] > 0
        return !!this.a.open[i] && ref.index < this.a.lines[i]
    }

    /** The line at virtual offset `offset` (clamped to the list), and where it starts. */
    locate(offset: number): LocatedLine | null {
        const a = this.a
        if (!this.n || a.height[0] <= 0) return null
        let off = Math.min(Math.max(0, offset), a.height[0] - 1e-6)
        let i = 0, top = 0
        for (; ;) {
            const h = a.header[i]
            if (off < h || !a.open[i]) return { node: a.ids[i], index: HEADER, top }
            off -= h
            top += h
            if (!a.count[i]) {
                const lines = a.lines[i]
                const body = this.measured.get(i)
                let k: number
                if (body) {
                    k = body.find(off)
                    top += body.prefix(k)
                } else {
                    k = Math.min(lines - 1, Math.floor(off / a.est[i]))
                    top += k * a.est[i]
                }
                return { node: a.ids[i], index: Math.max(0, k), top }
            }
            const [j, rem] = this.fenFind(i, off)
            top += off - rem
            off = rem
            i = a.first[i] + j
        }
    }

    /** Virtual offset of the line's top. A node's header offset is the node's own top. */
    offsetOf(ref: LineRef): number {
        const a = this.a
        const i = this.index.get(ref.node)
        if (i === undefined) return 0
        let top = 0
        if (ref.index >= 0) top += a.header[i] + this.bodyPrefix(i, ref.index)
        for (let c = i; a.parent[c] >= 0; c = a.parent[c]) {
            const p = a.parent[c]
            top += a.header[p] + this.fenPrefix(p, c - a.first[p])
        }
        return top
    }

    sizeOf(ref: LineRef): number {
        const i = this.index.get(ref.node)
        if (i === undefined) return 0
        if (ref.index < 0) return this.a.header[i]
        return this.measured.get(i)?.size(ref.index) ?? this.a.est[i]
    }

    lineType(ref: LineRef): string {
        return this.source.lineType(ref.node, ref.index)
    }

    /** The next line in display order, skipping closed groups. O(depth · log siblings). */
    next(ref: LineRef): LocatedLine | null {
        const top = this.offsetOf(ref)
        const end = top + this.sizeOf(ref)
        const line = end < this.height ? this.locate(end) : null
        return line && line.top > top ? line : null
    }

    prev(ref: LineRef): LocatedLine | null {
        const top = this.offsetOf(ref)
        const line = top > 0 ? this.locate(top - 0.5) : null
        return line && line.top < top ? line : null
    }

    key(ref: LineRef): string {
        return lineKey(ref)
    }

    /** The lines from `from` to `to` included, in display order, at most `max` of them. */
    between(from: LineRef, to: LineRef, max = 1000): LocatedLine[] {
        const out: LocatedLine[] = []
        const end = this.offsetOf(to)
        let line = this.locate(this.offsetOf(from))
        while (line && line.top <= end && out.length < max) {
            out.push(line)
            const next = line.top + this.sizeOf(line)
            const after: LocatedLine | null = next < this.height ? this.locate(next) : null
            // Never step back onto a line already walked (a layout read mid-change).
            line = after && after.top > line.top ? after : null
        }
        return out
    }

    // ── Internals ────────────────────────────────────────────────────────────

    private readNode(i: number) {
        const a = this.a, src = this.source, id = a.ids[i]
        a.open[i] = src.isOpen(id) ? 1 : 0
        // Whole pixels only: every offset is then an exact integer sum, and a line's end is exactly
        // the next line's start (with a fractional estimate, k * est + est could floor back to k).
        a.header[i] = Math.max(0, Math.round(src.headerSize(id) || 0))
        const lines = a.count[i] ? 0 : Math.max(0, Math.floor(src.bodyLines(id) || 0))
        const est = lines ? Math.max(1, Math.round(src.lineEstimate(id) || 1)) : 1
        const body = this.measured.get(i)
        if (body && (body.n !== lines || body.est !== est)) {
            if (lines) this.measured.set(i, new MeasuredBody(lines, est, body))
            else this.measured.delete(i)
        }
        a.lines[i] = lines
        a.est[i] = est
    }

    private bodyHeight(i: number): number {
        return this.measured.get(i)?.total ?? this.a.lines[i] * this.a.est[i]
    }

    private bodyPrefix(i: number, k: number): number {
        const body = this.measured.get(i)
        return body ? body.prefix(k) : k * this.a.est[i]
    }

    private ownHeight(i: number): number {
        const a = this.a
        if (!a.open[i]) return a.header[i]
        return a.header[i] + (a.count[i] ? a.childSum[i] : this.bodyHeight(i))
    }

    // Every height and Fenwick tree, bottom-up (children come after their parent).
    private sumAll() {
        const a = this.a
        for (let i = this.n - 1; i >= 0; i--) {
            const k = a.count[i]
            if (k) {
                const b = a.first[i] - 1
                let sum = 0
                for (let j = 1; j <= k; j++) {
                    a.fen[b + j] = a.height[b + j]
                    sum += a.height[b + j]
                }
                for (let j = 1; j <= k; j++) {
                    const q = j + lowbit(j)
                    if (q <= k) a.fen[b + q] += a.fen[b + j]
                }
                a.childSum[i] = sum
            } else {
                a.childSum[i] = 0
            }
            a.height[i] = this.ownHeight(i)
        }
    }

    // Node i's height changed by `delta` (bodyOnly: only its body did, so a closed i hides it).
    private propagate(i: number, delta: number, bodyOnly = false) {
        const a = this.a
        if (!delta) return
        if (bodyOnly && !a.open[i]) return
        a.height[i] += delta
        for (let c = i; a.parent[c] >= 0; c = a.parent[c]) {
            const p = a.parent[c]
            const k = a.count[p], b = a.first[p] - 1
            for (let j = c - b; j <= k; j += lowbit(j)) a.fen[b + j] += delta
            a.childSum[p] += delta
            // A closed parent's height is its header alone: the change stops there.
            if (!a.open[p]) return
            a.height[p] += delta
        }
    }

    // Sum of the heights of node p's first `j0` children.
    private fenPrefix(p: number, j0: number): number {
        const a = this.a, b = a.first[p] - 1
        let s = 0
        for (let j = j0; j > 0; j -= lowbit(j)) s += a.fen[b + j]
        return s
    }

    // The child of p holding offset `off` (from the top of p's children), and the offset left in it.
    private fenFind(p: number, off: number): [number, number] {
        const a = this.a, k = a.count[p], b = a.first[p] - 1
        let pos = 0, rem = off
        for (let step = highestPow2(k); step > 0; step >>= 1) {
            const q = pos + step
            if (q <= k && a.fen[b + q] <= rem) { pos = q; rem -= a.fen[b + q] }
        }
        if (pos < k) return [pos, rem]
        // Past the end (rounding): the last child that takes any room.
        for (let j = k - 1; j >= 0; j--) {
            const h = a.height[b + 1 + j]
            if (h > 0) return [j, Math.max(0, Math.min(rem + h, h - 1e-6))]
        }
        return [0, 0]
    }
}
