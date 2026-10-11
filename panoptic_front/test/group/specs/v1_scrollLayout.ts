/**
 * V1 — ScrollLayout answers like a walk over every line would, at a cost per group, not per line.
 *
 * Each check compares the layout with a brute-force flattening of the same tree (every line, in
 * display order, with its offset), after random open/close toggles, measurements and refreshes.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { HEADER, LayoutSource, LineRef, ScrollLayout, lineKey } from '@/components/scrollers/virtual/scrollLayout'

interface TNode { id: number, children: TNode[], open: boolean, header: number, lines: number, est: number }

function rng(seed: number) {
    return () => {
        seed |= 0; seed = seed + 0x6D2B79F5 | 0
        let t = Math.imul(seed ^ seed >>> 15, 1 | seed)
        t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t
        return ((t ^ t >>> 14) >>> 0) / 4294967296
    }
}

/** A random tree: ids are sparse and not in display order, some headers are 0, some leaves empty. */
function randomTree(seed: number, maxDepth = 3) {
    const rand = rng(seed)
    const nodes = new Map<number, TNode>()
    let nextId = 7
    function make(depth: number): TNode {
        const id = nextId
        nextId += 1 + Math.floor(rand() * 5)
        const inner = depth === 0 || (depth < maxDepth && rand() < 0.6)
        const node: TNode = {
            id, children: [], open: rand() < 0.7,
            header: rand() < 0.15 ? 0 : 20 + Math.floor(rand() * 20),
            lines: 0, est: 10 + Math.floor(rand() * 50),
        }
        nodes.set(id, node)
        if (inner) {
            const k = 1 + Math.floor(rand() * 6)
            for (let i = 0; i < k; i++) node.children.push(make(depth + 1))
        } else {
            node.lines = rand() < 0.1 ? 0 : 1 + Math.floor(rand() * 12)
        }
        return node
    }
    const root = make(0)
    root.open = true
    return { root, nodes, rand }
}

/** The first tree from `seed` on with at least `leaves` leaves of 2+ lines and an inner node under an inner node. */
function richTree(seed: number, leaves = 2) {
    for (; ; seed++) {
        const t = randomTree(seed)
        const nodes = [...t.nodes.values()]
        const ok = nodes.filter(n => !n.children.length && n.lines > 1).length >= leaves
            && nodes.some(n => n !== t.root && n.children.some(c => c.children.length))
        if (ok) return t
    }
}

function sourceOf(root: TNode, nodes: Map<number, TNode>): LayoutSource {
    const n = (id: number) => nodes.get(id)!
    return {
        root: () => root.id,
        childCount: id => n(id).children.length,
        child: (id, i) => n(id).children[i].id,
        isOpen: id => n(id).open,
        headerSize: id => n(id).header,
        bodyLines: id => n(id).children.length ? 0 : n(id).lines,
        lineEstimate: id => n(id).est,
        lineType: (id, i) => i < 0 ? 'group' : 'line',
    }
}

interface Flat { ref: LineRef, top: number, size: number }

/** Every line in display order, with its offset. `measured` overrides body line sizes. */
function flatten(root: TNode, measured: Map<string, number>): Flat[] {
    const out: Flat[] = []
    let y = 0
    function visit(node: TNode) {
        if (node.header > 0) {
            out.push({ ref: { node: node.id, index: HEADER }, top: y, size: node.header })
            y += node.header
        }
        if (!node.open) return
        if (node.children.length) {
            for (const c of node.children) visit(c)
            return
        }
        for (let i = 0; i < node.lines; i++) {
            const size = measured.get(node.id + ':' + i) ?? node.est
            out.push({ ref: { node: node.id, index: i }, top: y, size })
            y += size
        }
    }
    visit(root)
    return out
}

function check(layout: ScrollLayout, root: TNode, measured: Map<string, number>, rand: () => number, what: string) {
    const flat = flatten(root, measured)
    const total = flat.length ? flat[flat.length - 1].top + flat[flat.length - 1].size : 0
    assert.equal(layout.height, total, `${what}: height`)
    for (const f of flat) {
        assert.equal(layout.offsetOf(f.ref), f.top, `${what}: offsetOf ${lineKey(f.ref)}`)
        assert.equal(layout.sizeOf(f.ref), f.size, `${what}: sizeOf ${lineKey(f.ref)}`)
    }
    // locate at line starts, ends and random points
    for (let k = 0; k < flat.length; k++) {
        const f = flat[k]
        for (const at of [f.top, f.top + f.size - 0.5, f.top + rand() * f.size]) {
            const got = layout.locate(at)!
            assert.equal(lineKey(got), lineKey(f.ref), `${what}: locate(${at})`)
            assert.equal(got.top, f.top, `${what}: locate(${at}).top`)
        }
        const next = layout.next(f.ref)
        assert.equal(next ? lineKey(next) : null, k + 1 < flat.length ? lineKey(flat[k + 1].ref) : null, `${what}: next of ${lineKey(f.ref)}`)
        const prev = layout.prev(f.ref)
        assert.equal(prev ? lineKey(prev) : null, k > 0 ? lineKey(flat[k - 1].ref) : null, `${what}: prev of ${lineKey(f.ref)}`)
    }
    if (flat.length) {
        assert.equal(lineKey(layout.locate(-50)!), lineKey(flat[0].ref), `${what}: locate clamps above`)
        assert.equal(lineKey(layout.locate(total + 50)!), lineKey(flat[flat.length - 1].ref), `${what}: locate clamps below`)
        const all = layout.between(flat[0].ref, flat[flat.length - 1].ref, 1e6)
        assert.deepEqual(all.map(lineKey), flat.map(f => lineKey(f.ref)), `${what}: between walks every line`)
    } else {
        assert.equal(layout.locate(0), null)
    }
}

test('V1: offsets, sizes, locate, next/prev match a full walk, over random toggles', () => {
    for (const seed of [1, 2, 3, 4, 5]) {
        const { root, nodes, rand } = randomTree(seed)
        const layout = new ScrollLayout(sourceOf(root, nodes))
        layout.rebuild()
        const measured = new Map<string, number>()
        check(layout, root, measured, rand, `seed ${seed} built`)
        const ids = [...nodes.keys()].filter(id => id !== root.id)
        for (let step = 0; step < 60; step++) {
            const id = ids[Math.floor(rand() * ids.length)]
            nodes.get(id)!.open = !nodes.get(id)!.open
            assert.ok(layout.refreshNode(id))
            check(layout, root, measured, rand, `seed ${seed} step ${step} toggled ${id}`)
        }
    }
})

test('V1: measured lines change only their leaf, also while it is closed', () => {
    const { root, nodes, rand } = randomTree(11)
    const layout = new ScrollLayout(sourceOf(root, nodes))
    layout.rebuild()
    const measured = new Map<string, number>()
    const leaves = [...nodes.values()].filter(n => !n.children.length && n.lines > 0)
    for (let step = 0; step < 80; step++) {
        const leaf = leaves[Math.floor(rand() * leaves.length)]
        const i = Math.floor(rand() * leaf.lines)
        const px = 5 + Math.floor(rand() * 120)
        const changed = layout.setMeasured({ node: leaf.id, index: i }, px)
        const before = measured.get(leaf.id + ':' + i) ?? leaf.est
        assert.equal(changed, before !== px)
        if (px === leaf.est) measured.delete(leaf.id + ':' + i)
        else measured.set(leaf.id + ':' + i, px)
        if (step % 7 === 0) {
            const toggle = [...nodes.values()][Math.floor(rand() * nodes.size)]
            if (toggle !== root) { toggle.open = !toggle.open; layout.refreshNode(toggle.id) }
        }
        check(layout, root, measured, rand, `measured step ${step}`)
    }
    // No line, no header: nothing measured.
    assert.equal(layout.setMeasured({ node: leaves[0].id, index: HEADER }, 99), false)
    assert.equal(layout.setMeasured({ node: leaves[0].id, index: leaves[0].lines }, 99), false)
    assert.equal(layout.setMeasured({ node: -5, index: 0 }, 99), false)
})

test('V1: clearMeasured keeps only the lines asked for', () => {
    const { root, nodes, rand } = richTree(12)
    const layout = new ScrollLayout(sourceOf(root, nodes))
    layout.rebuild()
    const leaves = [...nodes.values()].filter(n => !n.children.length && n.lines > 1)
    const a = { node: leaves[0].id, index: 0 }, b = { node: leaves[1].id, index: 1 }
    layout.setMeasured(a, 333)
    layout.setMeasured(b, 444)
    layout.clearMeasured([a])
    const measured = new Map([[lineKey(a), 333]])
    check(layout, root, measured, rand, 'after clearMeasured')
})

test('V1: refresh re-reads sizes and open states; a changed shape rebuilds', () => {
    const { root, nodes, rand } = richTree(13)
    const layout = new ScrollLayout(sourceOf(root, nodes))
    layout.rebuild()
    for (const n of nodes.values()) { n.est += 3; if (n !== root && rand() < 0.3) n.open = !n.open; if (!n.children.length && rand() < 0.3) n.lines += 2 }
    layout.refresh()
    check(layout, root, new Map(), rand, 'after refresh')
    // A leaf gains children: refreshNode notices and rebuilds.
    const leaf = [...nodes.values()].find(n => !n.children.length && n !== root)!
    const kid: TNode = { id: 100000, children: [], open: true, header: 25, lines: 4, est: 17 }
    nodes.set(kid.id, kid)
    leaf.children.push(kid)
    leaf.open = true
    layout.refreshNode(leaf.id)
    for (let p = [...nodes.values()].find(n => n.children.includes(leaf)); p; p = [...nodes.values()].find(n => n.children.includes(p!))) p.open = true
    layout.refresh()
    check(layout, root, new Map(), rand, 'after a new child')
    assert.ok(layout.has(kid.id))
})

test('V1: a rebuild keeps the measurements of the leaves whose lines did not change', () => {
    const { root, nodes, rand } = richTree(14)
    const layout = new ScrollLayout(sourceOf(root, nodes))
    layout.rebuild()
    const leaves = [...nodes.values()].filter(n => !n.children.length && n.lines > 1)
    const kept = { node: leaves[0].id, index: 1 }, lost = { node: leaves[1].id, index: 0 }
    layout.setMeasured(kept, 77)
    layout.setMeasured(lost, 88)
    leaves[1].lines = 1  // still has line 0, at the new count: the size carries over
    leaves[1].est += 1   // a new estimate: kept too, the measured sizes are not estimates
    layout.rebuild()
    check(layout, root, new Map([[lineKey(kept), 77], [lineKey(lost), 88]]), rand, 'after rebuild')
})

test('V1: visibility, hidden nodes resolve to their closed ancestor', () => {
    const { root, nodes } = richTree(15)
    const layout = new ScrollLayout(sourceOf(root, nodes))
    const inner = [...nodes.values()].find(n => n !== root && n.children.length && n.children.some(c => c.children.length))!
    inner.open = false
    const deep = inner.children.find(c => c.children.length)!.children[0]
    layout.rebuild()
    assert.equal(layout.isVisible(deep.id), false)
    assert.equal(layout.visibleAncestor(deep.id), layout.isVisible(inner.id) ? inner.id : layout.visibleAncestor(inner.id))
    assert.equal(layout.isShown({ node: deep.id, index: HEADER }), false)
})

test('V1: an empty tree, a lone root, a cycle', () => {
    const empty = new ScrollLayout({ root: () => undefined } as unknown as LayoutSource)
    empty.rebuild()
    assert.equal(empty.height, 0)
    assert.equal(empty.locate(10), null)

    const flat: LayoutSource = {
        root: () => 0, childCount: () => 0, child: () => 0, isOpen: () => true, headerSize: () => 0,
        bodyLines: () => 1000, lineEstimate: () => 50, lineType: () => 'images',
    }
    const layout = new ScrollLayout(flat)
    layout.rebuild()
    assert.equal(layout.height, 50000)
    assert.deepEqual(layout.locate(1234), { node: 0, index: 24, top: 1200 })

    // 1 -> 2 -> 1: the second visit is dropped, no infinite loop.
    const cyc: LayoutSource = {
        root: () => 1, childCount: id => id === 3 ? 0 : 1, child: id => id === 1 ? 2 : 1,
        isOpen: () => true, headerSize: () => 10, bodyLines: () => 0, lineEstimate: () => 1, lineType: () => 'g',
    }
    const c = new ScrollLayout(cyc)
    c.rebuild()
    assert.equal(c.nodeCount, 2)
    assert.equal(c.height, 20)
})

test('V1: a million groups build in O(groups) and answer in O(log)', () => {
    const N = 1_000_000
    const src: LayoutSource = {
        root: () => 0, childCount: id => id === 0 ? N : 0, child: (_, i) => i + 1, isOpen: () => true,
        headerSize: id => id === 0 ? 0 : 30, bodyLines: id => id === 0 ? 0 : 1 + (id % 3), lineEstimate: () => 52,
        lineType: (_, i) => i < 0 ? 'group' : 'images',
    }
    const layout = new ScrollLayout(src)
    const t0 = performance.now()
    layout.rebuild()
    const built = performance.now() - t0
    let total = 0
    for (let id = 1; id <= N; id++) total += 30 + (1 + (id % 3)) * 52
    assert.equal(layout.height, total)
    const t1 = performance.now()
    for (let k = 0; k < 10000; k++) layout.locate((k * 7919 * 1013) % total)
    const located = performance.now() - t1
    // Generous bounds (CI machines): the point is no per-line work.
    assert.ok(built < 3000, `rebuild took ${built}ms`)
    assert.ok(located < 500, `10k locates took ${located}ms`)
    // Closing a group far down is O(log): the total drops by its body.
    const id = 765_432
    const before = layout.offsetOf({ node: id + 1, index: HEADER })
    src.isOpen = (n: number) => n !== id
    layout.refreshNode(id)
    assert.equal(layout.offsetOf({ node: id + 1, index: HEADER }), before - (1 + (id % 3)) * 52)
})

test('V1: a fractional estimate (the grid at a slider image size) still walks line by line', () => {
    // 63.7 + 4: k * est + est could floor back to line k, and the scroller walked in place forever.
    const src: LayoutSource = {
        root: () => 0, childCount: () => 0, child: () => 0, isOpen: () => true, headerSize: () => 0,
        bodyLines: () => 20000, lineEstimate: () => 67.7, lineType: () => 'image',
    }
    const layout = new ScrollLayout(src)
    layout.rebuild()
    assert.equal(layout.sizeOf({ node: 0, index: 0 }), 68, 'whole pixels')
    let line = layout.locate(0), steps = 0
    while (line && steps < 30000) {
        const next = layout.next(line)
        if (next) assert.equal(next.index, line.index + 1)
        line = next
        steps++
    }
    assert.equal(steps, 20000)
    assert.equal(layout.setMeasured({ node: 0, index: 3 }, 90.4), true)
    assert.equal(layout.sizeOf({ node: 0, index: 3 }), 90)
})
