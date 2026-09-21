/**
 * A12 — with grouping active, an instance new to the tree reaches root.slots.
 *
 * addInstanceToGroups only reaches value-key groups, so the root gained nothing there; a newly
 * imported instance, or one a lifted filter brought back, sat in its leaf while the root
 * understated the collection — and the next update(), which re-groups from root.slots, dropped
 * it for good.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
    groupedBy, ungrouped, leafFor, countOf, PROP,
    i2gProblems, coverageProblems, displayOrdered,
} from '../harness/world'
import { setValue } from '../harness/stubs/columnStore'

const VALUES = [10, 10, 10, 10, 20, 20, 20, 20, 30, 30, 30, 30]

test('A12: an arrival lands in root.slots exactly once, in display order', async () => {
    const present = [0, 1, 2, 3, 4, 5, 6, 7]                 // the 30-value slots are filtered out
    const m = await groupedBy(VALUES, present)
    assert.deepEqual(m.result.root.slots, present)
    assert.equal(leafFor(m, 30), undefined, 'no 30-bucket yet')

    m.updateSelection(new Set([1008, 1009]), new Set())

    const root = m.result.root.slots
    assert.equal(countOf(root, 8), 1, 'slot 8 is in root exactly once')
    assert.equal(countOf(root, 9), 1, 'slot 9 is in root exactly once')
    assert.equal(root.length, 10)
    assert.deepEqual(leafFor(m, 30)?.slots, [8, 9], 'and they are in their value leaf')
    assert.ok(displayOrdered(root, present).ok, 'root stays in display order')
    assert.deepEqual(i2gProblems(m), [])
    assert.deepEqual(coverageProblems(m), [])
})

test('A12: update() — which re-groups from root.slots — retains every instance', async () => {
    const present = [0, 1, 2, 3, 4, 5, 6, 7]
    const m = await groupedBy(VALUES, present)
    m.updateSelection(new Set([1008, 1009]), new Set())

    await m.update()

    const after = m.result.root.slots
    assert.equal(after.length, 10, 'the re-group kept the arrivals')
    assert.ok(after.includes(8) && after.includes(9))
    assert.deepEqual(coverageProblems(m), [])
    assert.deepEqual(i2gProblems(m), [])
})

test('A12: a value change moves a slot between leaves without duplicating it in root', async () => {
    const present = VALUES.map((_, i) => i)
    const m = await groupedBy(VALUES)
    setValue(PROP, 0, 20)
    m.updateSelection(new Set([1000]), new Set())

    const root = m.result.root.slots
    assert.equal(root.length, 12, 'root length unchanged')
    assert.equal(countOf(root, 0), 1, 'the moved slot is in root exactly once')
    assert.ok(!leafFor(m, 10)?.slots.includes(0), 'it left its old leaf')
    assert.ok(leafFor(m, 20)?.slots.includes(0), 'it joined its new leaf')
    assert.ok(displayOrdered(root, present).ok, 'root is still in display order')
    assert.deepEqual(i2gProblems(m), [])
})

test('A12: a removal and an arrival in the same update both land correctly', async () => {
    const present = [0, 1, 2, 3, 4, 5, 6, 7]
    const m = await groupedBy(VALUES, present)
    m.updateSelection(new Set([1008]), new Set([1000]))

    const root = m.result.root.slots
    assert.ok(!root.includes(0), 'the removed slot is gone')
    assert.equal(countOf(root, 8), 1, 'the arrival is there once')
    assert.equal(root.length, 8)
    assert.ok(displayOrdered(root, present).ok)
    assert.deepEqual(i2gProblems(m), [])
    assert.deepEqual(coverageProblems(m), [])
})

test('A12: with no grouping the root is the leaf and still takes each updated slot once', async () => {
    const present = [0, 1, 2, 3, 4, 5, 6, 7]
    const m = await ungrouped(12, present)
    m.updateSelection(new Set([1008, 1000]), new Set([1001]))

    const root = m.result.root.slots
    assert.equal(countOf(root, 8), 1, 'arrival added once')
    assert.equal(countOf(root, 0), 1, 're-added slot not duplicated')
    assert.ok(!root.includes(1), 'removed slot dropped')
    assert.equal(root.length, 8)
    assert.ok(displayOrdered(root, present).ok)
    assert.deepEqual(i2gProblems(m), [])
})
