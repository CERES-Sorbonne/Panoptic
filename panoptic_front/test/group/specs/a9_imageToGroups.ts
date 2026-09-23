/**
 * A9 — imageToGroups holds ONLY leaf groups.
 *
 * A clustered bucket is not a leaf: its children are the piles. If the bucket stayed in the map,
 * every reader that asks "which card shows this image" got a card that shows nothing, and the
 * dirty-set derivation marked the wrong node.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { groupedBy, leafFor, pile, i2gProblems, coverageProblems, PROP } from '../harness/world'
import { setValue } from '../harness/stubs/columnStore'

const VALUES = [10, 10, 10, 10, 20, 20, 20, 20, 30, 30, 30, 30]
const ALL = VALUES.map((_, i) => i)

test('A9: after group(), imageToGroups holds only leaves — the clustered bucket is not one', async () => {
    const m = await groupedBy(VALUES)
    const bucket = leafFor(m, 20)!
    assert.deepEqual(bucket.slots, [4, 5, 6, 7])
    m.clusters.addCustomGroups(bucket.id, [pile(9001, [4, 5])], false)
    assert.equal(m.result.index[bucket.id].children.length, 2, 'pile + leftover')

    await m.group(new Int32Array(ALL))

    assert.deepEqual(i2gProblems(m), [], 'the leaf-only meaning holds after a full rebuild')
    const membership = [...(m.result.imageToGroups.get(1004) ?? [])]
    assert.ok(!membership.includes(bucket.id as number), 'the clustered bucket is NOT named')
    assert.ok(membership.includes(9001), 'the pile IS named')
})

test('A9: after a structural cluster op, imageToGroups holds only leaves', async () => {
    const m = await groupedBy(VALUES)
    const bucket = leafFor(m, 20)!
    m.clusters.addCustomGroups(bucket.id, [pile(9001, [4, 5])], false)
    assert.deepEqual(i2gProblems(m), [])
    m.clusters.split(9001, [pile(9011, [4]), pile(9012, [5])], false)
    assert.deepEqual(i2gProblems(m), [], 'a sub-clustered pile stops being named too')
    const membership = [...(m.result.imageToGroups.get(1004) ?? [])]
    assert.ok(!membership.includes(9001), 'the sub-clustered pile is no longer a leaf')
    assert.ok(membership.includes(9011))
})

test('A9: after updateSelection, a clustered image keeps the same membership shape', async () => {
    const m = await groupedBy(VALUES)
    const bucket = leafFor(m, 20)!
    m.clusters.addCustomGroups(bucket.id, [pile(9001, [4, 5])], false)
    await m.group(new Int32Array(ALL))
    const before = [...(m.result.imageToGroups.get(1004) ?? [])].sort().join()

    setValue(PROP, 0, 30)
    m.updateSelection(new Set([1000]), new Set())

    assert.deepEqual(i2gProblems(m), [], 'the same predicate holds after the incremental path')
    assert.equal([...(m.result.imageToGroups.get(1004) ?? [])].sort().join(), before)
    assert.deepEqual(coverageProblems(m), [])
})

test('A9: an image whose bucket left the tree names no group at all', async () => {
    const m = await groupedBy(VALUES)
    const bucket = leafFor(m, 20)!
    m.clusters.addCustomGroups(bucket.id, [pile(9101, [4, 5])], false)

    // The whole bucket is filtered away: the container detaches instead of dying.
    m.updateSelection(new Set(), new Set([1004, 1005, 1006, 1007]))
    assert.equal(m.result.index[bucket.id], undefined, 'the bucket left the tree')
    assert.ok(m.clusters.overlay.container(bucket.id as number), 'its container is still held')
    const stale = [1004, 1005, 1006, 1007].flatMap(id => [...(m.result.imageToGroups.get(id) ?? [])])
    assert.deepEqual(stale, [], 'no stale membership is left behind')
    assert.deepEqual(i2gProblems(m), [])
})

test('A9: when the bucket comes back the piles are named again, the bucket is not', async () => {
    const m = await groupedBy(VALUES)
    const bucket = leafFor(m, 20)!
    m.clusters.addCustomGroups(bucket.id, [pile(9101, [4, 5])], false)
    const leftoverId = m.result.index[bucket.id].children.find(c => c.isLeftover)!.id

    m.updateSelection(new Set(), new Set([1004, 1005, 1006, 1007]))
    m.updateSelection(new Set([1004, 1005, 1006, 1007]), new Set())

    assert.deepEqual(m.result.index[bucket.id]?.slots, [4, 5, 6, 7], 'the bucket is back')
    assert.deepEqual(m.result.index[9101]?.slots, [4, 5], 'the pile refilled')
    assert.deepEqual(m.result.index[leftoverId]?.slots, [6, 7], 'the leftover took the rest')
    assert.deepEqual(i2gProblems(m), [])
    assert.ok(![...(m.result.imageToGroups.get(1004) ?? [])].includes(bucket.id as number))
    assert.deepEqual(coverageProblems(m), [])
})
