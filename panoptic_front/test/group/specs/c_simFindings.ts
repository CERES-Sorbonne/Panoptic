/**
 * C — the bugs the randomised simulation found (see ../sim/).
 *
 * Each one is kept here as a plain, named test so it fails loudly rather than only when a seed
 * happens to hit it again. The simulation's own repro is in the comment above each test.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { SortDirection } from '@/core/SortManager'
import { groupedBy, ungrouped, leafFor, pile, i2gProblems, PROP } from '../harness/world'
import { selectedSlots } from '../harness/stubs/columnStore'

const VALUES = [10, 10, 10, 10, 20, 20, 20, 20, 30, 30, 30, 30]

/** Instance ids in DFS display order, read from the tree rather than from orderedIds. */
const dfsIds = (m: any): number[] => {
    const out: number[] = []
    const walk = (g: any) => {
        if (!g.children.length) for (const s of g.slots) out.push(1000 + s)
        else g.children.forEach(walk)
    }
    walk(m.result.root)
    return out
}

// ── C1 ───────────────────────────────────────────────────────────────────────
// sim: seed 1, one `groupOption` op on a one-level grouping.
// sortGroups() re-ordered the children and stopped there: `order` (what the iterators compare),
// orderedIds and every start/end still described the previous arrangement.

test('C1: sortGroups re-derives the display order it just changed', async () => {
    const m = await groupedBy(VALUES)
    assert.deepEqual(Array.from(m.result.orderedIds), dfsIds(m), 'precondition')

    m.setGroupOption(PROP, { direction: SortDirection.Descending })
    m.sortGroups(true)

    assert.deepEqual(m.result.root.children.map(c => c.meta.propertyValues[0].value), [30, 20, 10],
        'the children really were re-ordered')
    assert.deepEqual(Array.from(m.result.orderedIds), dfsIds(m), 'orderedIds followed')
    const first = m.result.root.children[0]
    assert.equal(first.start, 0, 'start/end followed too')
    assert.equal(first.end, first.slots.length)
    assert.deepEqual(m.result.root.children.map(c => c.order), [1, 2, 3], 'so did the DFS order')
})

test('C1: sortGroups on an empty manager is a no-op, not a crash', async () => {
    const m = await groupedBy(VALUES)
    m.clear()
    m.sortGroups(true)
})

// ── C2 ───────────────────────────────────────────────────────────────────────
// sim: seed 2, `clusterLeaf` then `clearCustom`.
// resync drops a bucket's imageToGroups entries at the one point where it stops being a leaf
// (its piles are grafted). Nothing put them back when the piles went away, so an un-clustered
// bucket sat in the tree while its images named no group at all — and an instance that names no
// group reads as "new to the tree", so the next update appended it to the root a second time.

test('C2: clearCustomGroups gives the bucket its imageToGroups entries back', async () => {
    const m = await groupedBy(VALUES)
    const bucket = leafFor(m, 20)!
    m.clusters.addCustomGroups(bucket.id, [pile(9101, [4, 5])], false)
    assert.deepEqual(i2gProblems(m), [], 'precondition: the piles name themselves')
    assert.ok(!m.result.imageToGroups.get(1004)?.has(bucket.id as number), 'the bucket is not a leaf')

    m.clusters.clearCustomGroups(false)

    assert.equal(m.result.index[bucket.id as number].children.length, 0, 'the bucket is a leaf again')
    assert.deepEqual(i2gProblems(m), [])
    assert.ok(m.result.imageToGroups.get(1004)?.has(bucket.id as number), 'and it names itself again')
})

test('C2: delCustomGroups does the same for the one bucket', async () => {
    const m = await groupedBy(VALUES)
    const bucket = leafFor(m, 20)!
    m.clusters.addCustomGroups(bucket.id, [pile(9102, [4, 5])], false)
    m.clusters.delCustomGroups(bucket.id, false)

    assert.equal(m.result.index[bucket.id as number].children.length, 0)
    assert.deepEqual(i2gProblems(m), [])
    for (const id of [1004, 1005, 1006, 1007]) {
        assert.ok(m.result.imageToGroups.get(id)?.has(bucket.id as number), `${id} names the bucket`)
    }
})

test('C2: an instance whose bucket was un-clustered is NOT treated as new to the tree', async () => {
    const m = await groupedBy(VALUES)
    const bucket = leafFor(m, 20)!
    m.clusters.addCustomGroups(bucket.id, [pile(9103, [4, 5])], false)
    m.clusters.clearCustomGroups(false)

    m.updateSelection(new Set([1004]), new Set())

    assert.equal(m.result.root.slots.filter(s => s === 4).length, 1, 'slot 4 is in the root once')
    assert.equal(m.result.root.slots.length, 12)
})

// ── C3 ───────────────────────────────────────────────────────────────────────
// sim: seed 1412919463 — selectImage, groupAdd, selectImage with shift.
// The shift anchor is the one iterator that outlives the click that set it. A rebuild in between
// left it pointing at a node of the previous tree, and the range walked from there crossed two
// trees: it threw on the first hop out of the stale node.

test('C3: a shift-select whose anchor predates a rebuild selects only the new image', async () => {
    const m = await groupedBy(VALUES)
    const leaf = leafFor(m, 10)!
    m.selectImageIterator(m.getImageIterator(leaf.id as number, 0))
    assert.deepEqual(selectedSlots(), [0])

    await m.group(new Int32Array(VALUES.map((_, i) => i)))   // the anchor's tree is gone

    const other = leafFor(m, 30)!
    m.selectImageIterator(m.getImageIterator(other.id as number, 1), true)

    assert.deepEqual(selectedSlots(), [0, 9], 'the clicked image only — no range, and no crash')
})

test('C3: a shift-select with a live anchor still collects the range', async () => {
    const m = await groupedBy(VALUES)
    const a = leafFor(m, 10)!
    const b = leafFor(m, 20)!
    m.selectImageIterator(m.getImageIterator(a.id as number, 2))
    m.selectImageIterator(m.getImageIterator(b.id as number, 1), true)

    assert.deepEqual(selectedSlots(), [2, 3, 4, 5])
})

// ── C4 ───────────────────────────────────────────────────────────────────────
// sim: seed 200055 — an anchor taken on a leaf that was clustered afterwards.
// A clustered bucket is the SAME node with the SAME slots, so isCurrent's identity check passed
// while the position it described had stopped being displayed at all: the images are in the
// piles now. collectRange then walked off the tree and threw.

test('C4: isCurrent is false once the anchor group has gained children', async () => {
    const m = await ungrouped(8)
    const it = m.getImageIterator(0, 2)
    assert.equal(it.isCurrent, true, 'precondition: the root is the leaf')

    m.clusters.addCustomGroups(0, [pile(9201, [0, 1, 2])], false)

    assert.equal(m.result.index[0], it.group, 'the same node, with the same slots')
    assert.equal(it.isCurrent, false, 'but it no longer displays images itself')
})

test('C4: a shift-select anchored on a since-clustered group selects only the new image', async () => {
    const m = await ungrouped(8)
    m.selectImageIterator(m.getImageIterator(0, 0))          // anchor while the root is the leaf
    m.clusters.addCustomGroups(0, [pile(9202, [0, 1, 2])], false)

    const leftover = m.result.root.children.find(c => c.isLeftover)!
    m.selectImageIterator(m.getImageIterator(leftover.id as number, 0), true)

    assert.deepEqual(selectedSlots(), [0, 3], 'no range walked from a position that is gone')
})

test('C4: collectRange ends at a hop that resolves to nothing', async () => {
    const m = await ungrouped(8)
    const from = m.getImageIterator(0, 0)
    const to = m.getImageIterator(0, 7)
    assert.deepEqual(from.collectRange(to), [0, 1, 2, 3, 4, 5, 6, 7], 'precondition')

    // The same walk once the root has become a closed parent: `from` still describes position 0
    // of a node that no longer shows images, and every hop out of it lands on nothing.
    m.clusters.addCustomGroups(0, [pile(9203, [0, 1, 2])], false)
    m.closeGroup(9203)
    m.result.root.children.forEach(c => m.closeGroup(c.id as number))
    assert.deepEqual(from.collectRange(to), [0], 'it stops instead of throwing')
})
