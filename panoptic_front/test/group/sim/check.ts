/**
 * The invariants, checked after every single operation.
 *
 * Each check answers one question and tags its findings, so the shrinker can tell "the same
 * failure" from "a different one". Nothing here reads the implementation's own bookkeeping to
 * decide what is correct: membership comes from the reference model, order from the slot order
 * the last full group() was handed, and the structural rules are stated over the tree itself.
 */
import { Group, GroupType } from '@/core/group/types'
import { ClusterContainer } from '@/core/group/ClusterOverlay'
import { columnStub } from '../harness/stubs/columnStore'
import { invariantBreaches } from '../harness/console'
import { i2gProblems } from '../harness/world'
import { serPath } from './model'
import { World } from './world'

export interface Problem { tag: string, msg: string }

const p = (tag: string, msg: string): Problem => ({ tag, msg })

/** The nearest ancestor that is not a cluster pile: the grouping bucket a leaf belongs to. */
function bucketOf(leaf: Group): Group {
    let g = leaf
    while (g.type === GroupType.Cluster && g.parent) g = g.parent
    return g
}

const countMap = <K>(m: Map<K, number>, k: K) => m.set(k, (m.get(k) ?? 0) + 1)

// ── 1. membership ────────────────────────────────────────────────────────────

/**
 * Every present instance is displayed under exactly the bucket keys the model says, once each,
 * and nothing else is displayed at all.
 */
function checkMembership(w: World): Problem[] {
    const out: Problem[] = []
    const ids = columnStub.instanceIds()
    const expected = w.model.expectedMembership()
    // instanceId → key path → how many leaves of that bucket hold it.
    const actual = new Map<number, Map<string, number>>()

    for (const leaf of w.leaves()) {
        const path = serPath(bucketOf(leaf).key)
        for (const slot of leaf.slots) {
            const id = ids[slot]
            let paths = actual.get(id)
            if (!paths) { paths = new Map(); actual.set(id, paths) }
            countMap(paths, path)
        }
    }

    for (const [id, want] of expected) {
        const got = actual.get(id) ?? new Map<string, number>()
        for (const path of want) {
            const n = got.get(path) ?? 0
            if (n === 0) out.push(p('membership', `instance ${id} is missing from bucket [${path}]`))
            else if (n > 1) out.push(p('membership', `instance ${id} is in bucket [${path}] ${n} times`))
        }
        for (const [path, n] of got) {
            if (!want.has(path)) out.push(p('membership', `instance ${id} is displayed in bucket [${path}] (${n}x) but belongs to {${[...want].join(', ')}}`))
        }
    }
    for (const [id, got] of actual) {
        if (expected.has(id)) continue
        const inst = w.model.byId(id)
        const why = !inst ? 'unknown instance' : inst.deleted ? 'deleted' : 'filtered out'
        out.push(p('membership', `${why} instance ${id} is still displayed in [${[...got.keys()].join('], [')}]`))
    }
    return out
}

/** root.slots is the collection: every present slot once, nothing else. */
function checkRoot(w: World): Problem[] {
    const out: Problem[] = []
    const root = w.gm.result.root
    if (!root) return [p('root', 'there is no root')]
    const want = new Set(w.model.present().map(i => i.slot))
    const seen = new Map<number, number>()
    for (const s of root.slots) countMap(seen, s)
    for (const s of want) {
        const n = seen.get(s) ?? 0
        if (n !== 1) out.push(p('root', `present slot ${s} is in root.slots ${n} times`))
    }
    for (const [s, n] of seen) {
        if (!want.has(s)) out.push(p('root', `root.slots holds absent slot ${s} (${n}x)`))
    }
    return out
}

// ── 2. tree structure ────────────────────────────────────────────────────────

function checkTree(w: World): Problem[] {
    const out: Problem[] = []
    const result = w.gm.result
    const root = result.root
    if (!root) return out

    const reachable = new Set<number | string>()
    const seenNodes = new Set<Group>()
    const walk = (g: Group, depth: number) => {
        if (seenNodes.has(g)) { out.push(p('tree', `group ${g.id} is reachable twice (cycle or shared node)`)); return }
        seenNodes.add(g)
        reachable.add(g.id)
        if (result.index[g.id] !== g) out.push(p('tree', `group ${g.id} is in the tree but not the node registered under its id`))
        if (g.depth !== depth) out.push(p('tree', `group ${g.id} has depth ${g.depth}, expected ${depth}`))
        const slotSeen = new Set<number>()
        for (const s of g.slots) {
            if (slotSeen.has(s)) out.push(p('tree', `group ${g.id} holds slot ${s} twice`))
            slotSeen.add(s)
        }
        if (g.children.length === 0) {
            if (g !== root && g.slots.length === 0) out.push(p('tree', `leaf ${g.id} is attached but holds nothing`))
        } else {
            const types = new Set(g.children.map(c => c.type))
            const want = types.size === 1 ? g.children[0].type : undefined
            if (g.subGroupType !== want) {
                out.push(p('tree', `group ${g.id} says subGroupType=${g.subGroupType} but its children are ${[...types].join('+')}`))
            }
        }
        g.children.forEach((c, i) => {
            if (c.parent !== g) out.push(p('tree', `child ${c.id} of ${g.id} points at parent ${c.parent?.id}`))
            if (c.parentIdx !== i) out.push(p('tree', `child ${c.id} of ${g.id} sits at ${i} but says parentIdx=${c.parentIdx}`))
            walk(c, depth + 1)
        })
    }
    if (root.parent) out.push(p('tree', 'the root has a parent'))
    walk(root, 0)

    for (const key of Object.keys(result.index)) {
        const g = result.index[key]
        if (!reachable.has(g.id)) out.push(p('tree', `group ${g.id} is registered but unreachable from the root (orphan)`))
    }
    return out
}

// ── 3. imageToGroups ─────────────────────────────────────────────────────────

function checkImageToGroups(w: World): Problem[] {
    return i2gProblems(w.gm).map(msg => p('i2g', msg))
}

// ── 4. display order ─────────────────────────────────────────────────────────

function checkOrder(w: World): Problem[] {
    const out: Problem[] = []
    const result = w.gm.result
    if (!result.root) return out
    const ids = columnStub.instanceIds()
    const ordered = Array.from(result.orderedIds)   // materialises start/end too

    // The reference DFS: every leaf's images, in pile order where a pile exists.
    const want: number[] = []
    const walk = (g: Group) => {
        if (g.children.length === 0) {
            const pile = result.pileIndex.get(g.id as number)
            for (const s of (pile ? pile.order : g.slots)) want.push(ids[s])
        } else g.children.forEach(walk)
    }
    walk(result.root)

    if (ordered.length !== want.length) {
        out.push(p('order', `orderedIds has ${ordered.length} entries, the leaves hold ${want.length}`))
    } else if (ordered.join() !== want.join()) {
        out.push(p('order', `orderedIds is not the DFS walk of the leaves`))
    }

    // start/end bound each group's own subtree.
    const bounds = (g: Group): void => {
        if (g.children.length === 0) {
            const pile = result.pileIndex.get(g.id as number)
            const n = pile ? pile.order.length : g.slots.length
            if (g.end - g.start !== n) out.push(p('order', `leaf ${g.id} spans ${g.start}..${g.end} for ${n} images`))
        } else {
            g.children.forEach(bounds)
            const first = g.children[0]
            const last = g.children[g.children.length - 1]
            if (g.start !== first.start || g.end !== last.end) {
                out.push(p('order', `group ${g.id} spans ${g.start}..${g.end} but its children span ${first.start}..${last.end}`))
            }
            for (let i = 1; i < g.children.length; i++) {
                if (g.children[i].start !== g.children[i - 1].end) {
                    out.push(p('order', `group ${g.id}: children ${g.children[i - 1].id} and ${g.children[i].id} are not contiguous`))
                }
            }
        }
        if (g.start < 0 || g.end > ordered.length) out.push(p('order', `group ${g.id} spans ${g.start}..${g.end}, outside 0..${ordered.length}`))
    }
    bounds(result.root)

    // Every group's slots follow the display order the last full group() established.
    for (const g of w.dfsGroups()) {
        for (let i = 1; i < g.slots.length; i++) {
            if (w.position(g.slots[i]) <= w.position(g.slots[i - 1])) {
                out.push(p('order', `group ${g.id} is out of display order at index ${i} (slots ${g.slots[i - 1]}, ${g.slots[i]})`))
                break
            }
        }
    }
    return out
}

// ── 5. sha1 piles ────────────────────────────────────────────────────────────

function checkPiles(w: World): Problem[] {
    const out: Problem[] = []
    const result = w.gm.result
    const sha1s = columnStub.sha1s()

    if (!w.gm.state.sha1Mode) {
        if (result.pileIndex.size) out.push(p('piles', `sha1Mode is off but ${result.pileIndex.size} pile entries remain`))
        return out
    }
    for (const leaf of w.leaves()) {
        if (leaf.slots.length && !result.pileIndex.has(leaf.id as number)) {
            out.push(p('piles', `leaf ${leaf.id} (${leaf.slots.length} slots) has no pile layout in sha1Mode`))
        }
    }
    for (const [gid, pile] of result.pileIndex) {
        const g = result.index[gid]
        if (!g) { out.push(p('piles', `pileIndex names group ${gid}, absent from the index`)); continue }
        if (g.children.length) { out.push(p('piles', `pileIndex names ${gid}, which has children`)); continue }
        if (pile.order.length !== g.slots.length || [...pile.order].sort((a, b) => a - b).join() !== [...g.slots].sort((a, b) => a - b).join()) {
            out.push(p('piles', `pile order of ${gid} is not a permutation of its slots`))
            continue
        }
        const b = pile.bounds
        if (b[0] !== 0 || b[b.length - 1] !== pile.order.length) {
            out.push(p('piles', `pile bounds of ${gid} do not span its order`))
            continue
        }
        for (let k = 1; k < b.length; k++) {
            if (b[k] <= b[k - 1]) { out.push(p('piles', `pile bounds of ${gid} are not increasing`)); break }
        }
        for (let k = 0; k + 1 < b.length; k++) {
            const run = pile.order.slice(b[k], b[k + 1])
            const sha1 = sha1s[run[0]]
            if (run.length > 1 && run.some(s => sha1s[s] !== sha1)) {
                out.push(p('piles', `pile ${k} of ${gid} mixes sha1s`))
            }
        }
    }
    return out
}

// ── 6. clusters ──────────────────────────────────────────────────────────────

/** Live children per node index, 0 holding the container's top level. */
function liveKids(c: ClusterContainer): number[][] {
    const kids: number[][] = c.table.map(() => [])
    for (let i = 1; i < c.table.length; i++) {
        const node = c.table[i]
        if (!node || node.dead) continue
        kids[node.up].push(i)
    }
    return kids
}

function checkClusters(w: World): Problem[] {
    const out: Problem[] = []
    const overlay = w.gm.clusters.overlay
    const index = w.gm.result.index

    for (const c of overlay.byGroup.values()) {
        // I3 — the authored totals and the owner array agree.
        let owned = 0
        for (const node of c.table) if (node) owned += node.owned
        let counted = 0
        for (let s = 0; s < c.owner.length; s++) if (c.owner[s]) counted++
        if (owned !== counted) out.push(p('cluster', `bucket ${c.parentId}: authored total ${owned} but ${counted} slots are owned`))

        // I2 — every owner value names a node of this container.
        for (let s = 0; s < c.owner.length; s++) {
            if (c.owner[s] && !c.table[c.owner[s]]) {
                out.push(p('cluster', `bucket ${c.parentId}: slot ${s} owned by unknown node ${c.owner[s]}`))
                break
            }
        }

        // A dead node is unaddressable and undrawn.
        for (const node of c.table) {
            if (!node || !node.dead) continue
            if (overlay.nodeOf(node.group.id)) out.push(p('cluster', `bucket ${c.parentId}: dead node ${node.group.id} still resolves through nodeOf`))
            if (index[node.group.id] === node.group) out.push(p('cluster', `bucket ${c.parentId}: dead node ${node.group.id} is still in the tree index`))
        }

        const parent = index[c.parentId]
        if (!parent) continue
        const mine = new Set<number | string>()
        for (const node of c.table) if (node) mine.add(node.group.id)
        const active = parent.children.length > 0 && parent.children.every(ch => mine.has(ch.id))
        if (!active) continue

        // Every level that has been split ends on a leftover, so routing always has a home.
        const kids = liveKids(c)
        for (let i = 0; i < kids.length; i++) {
            if (i > 0 && (!c.table[i] || c.table[i]!.dead)) continue
            if (!kids[i].length) continue
            if (!kids[i].some(k => c.table[k]!.leftover)) {
                out.push(p('cluster', `bucket ${c.parentId}: level below node ${i} has no leftover`))
            }
        }

        // I1 — every image of the bucket lands in exactly one pile.
        const seen = new Map<number, number>()
        const walk = (g: Group) => {
            if (!g.children.length) { for (const s of g.slots) countMap(seen, s) }
            else g.children.forEach(walk)
        }
        parent.children.forEach(walk)
        for (const s of parent.slots) {
            const n = seen.get(s) ?? 0
            if (n !== 1) out.push(p('cluster', `bucket ${c.parentId}: slot ${s} is in ${n} piles`))
        }
        for (const [s, n] of seen) {
            if (!parent.slots.includes(s)) out.push(p('cluster', `bucket ${c.parentId}: pile holds foreign slot ${s} (${n}x)`))
        }
    }
    return out
}

// ── 7. iterators ─────────────────────────────────────────────────────────────

/**
 * The iterators are the display order.
 *
 *  - walking the whole tree with `nextImages` (ignoring open/closed) visits every image
 *    exactly once, in orderedIds order, and each position reports its own global index
 *  - walking back from the end retraces the same order
 *  - the default (closed-aware) walk visits exactly the images an open path leads to
 *  - `collectRange` between two positions is the slice between them
 */
function checkIterators(w: World): Problem[] {
    const out: Problem[] = []
    const result = w.gm.result
    const ordered = Array.from(result.orderedIds)
    if (!ordered.length) return out
    const ids = columnStub.instanceIds()

    // ── forward, every image ────────────────────────────────────────────────
    const steps: { groupId: number, imageIdx: number, slots: number[] }[] = []
    const walked: number[] = []
    let it = w.gm.getImageIterator(0, 0, { ignoreClosed: true })
    let guard = ordered.length + 8
    while (it && guard-- > 0) {
        if (!it.isValid) { out.push(p('iter', 'the forward walk reached an invalid iterator')); return out }
        if (it.getImageOrder() !== walked.length) {
            out.push(p('iter', `position ${walked.length} reports getImageOrder() === ${it.getImageOrder()}`))
            return out
        }
        steps.push({ groupId: it.groupId, imageIdx: it.imageIdx, slots: it.slots.slice() })
        for (const s of it.slots) walked.push(ids[s])
        it = it.nextImages()
    }
    if (guard <= 0) { out.push(p('iter', 'the forward walk did not terminate')); return out }
    if (walked.join() !== ordered.join()) {
        out.push(p('iter', `the nextImages walk visited ${walked.length} images, orderedIds has ${ordered.length}`
            + (walked.length === ordered.length ? ' (same length, different order)' : '')))
        return out
    }

    // ── backward, from the last position ────────────────────────────────────
    const last = steps[steps.length - 1]
    const back: number[] = []
    let rit = w.gm.getImageIterator(last.groupId, last.imageIdx, { ignoreClosed: true })
    guard = steps.length + 8
    while (rit && guard-- > 0) {
        back.unshift(...rit.slots.map(s => ids[s]))   // a pile keeps its own internal order
        rit = rit.prevImages()
    }
    if (guard <= 0) out.push(p('iter', 'the backward walk did not terminate'))
    else if (back.join() !== ordered.join()) {
        out.push(p('iter', `the prevImages walk retraced ${back.length} images, orderedIds has ${ordered.length}`))
    }

    // ── the closed-aware walk shows exactly what an open path leads to ──────
    const root = result.root
    if (!(root.view.closed && root.children.length === 0)) {
        const visibleWant: number[] = []
        const walkVisible = (g: Group) => {
            if (g.view.closed) return
            if (g.children.length === 0) {
                const pile = result.pileIndex.get(g.id as number)
                for (const s of (pile ? pile.order : g.slots)) visibleWant.push(ids[s])
            } else g.children.forEach(walkVisible)
        }
        walkVisible(root)

        const visibleGot: number[] = []
        let vit = w.gm.getImageIterator(0, 0)
        guard = ordered.length + 8
        while (vit && vit.isValid && guard-- > 0) {
            for (const s of vit.slots) visibleGot.push(ids[s])
            vit = vit.nextImages()
        }
        if (guard <= 0) out.push(p('iter', 'the closed-aware walk did not terminate'))
        else if (visibleGot.join() !== visibleWant.join()) {
            out.push(p('iter', `the closed-aware walk shows ${visibleGot.length} images, the open leaves hold ${visibleWant.length}`))
        }
    }

    // ── collectRange is the slice between two positions ─────────────────────
    if (steps.length >= 2) {
        const a = Math.floor(steps.length / 3)
        const b = Math.floor((steps.length * 2) / 3)
        const from = w.gm.getImageIterator(steps[a].groupId, steps[a].imageIdx, { ignoreClosed: true })
        const to = w.gm.getImageIterator(steps[b].groupId, steps[b].imageIdx, { ignoreClosed: true })
        const want: number[] = []
        for (let i = Math.min(a, b); i <= Math.max(a, b); i++) want.push(...steps[i].slots)
        const got = from.collectRange(to)
        if (got.join() !== want.join()) {
            out.push(p('iter', `collectRange over positions ${a}..${b} gave ${got.length} slots, the walk gives ${want.length}`))
        }
    }
    return out
}

// ── 8. selection ─────────────────────────────────────────────────────────────

function checkSelection(w: World): Problem[] {
    const out: Problem[] = []
    const count = columnStub.slotCount()
    for (const s of w.selectedSlots()) {
        if (!Number.isInteger(s) || s < 0 || s >= count) {
            out.push(p('select', `the selection mask holds ${s}, not a slot of this store`))
        }
    }
    return out
}

// ── all of them ──────────────────────────────────────────────────────────────

export function checkAll(w: World): Problem[] {
    const out: Problem[] = []
    // The DEV checks inside ClusterOverlay report through console.error, which the harness
    // captures; anything there is a breach the step itself provoked.
    for (const breach of invariantBreaches()) out.push(p('dev', breach))
    out.push(...checkRoot(w))
    out.push(...checkTree(w))
    out.push(...checkMembership(w))
    out.push(...checkImageToGroups(w))
    out.push(...checkOrder(w))
    out.push(...checkPiles(w))
    out.push(...checkClusters(w))
    out.push(...checkIterators(w))
    out.push(...checkSelection(w))
    return out
}
