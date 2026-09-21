/**
 * E1 — appending a grouping level moves the clusters down instead of clearing them.
 *
 * The group view lets a user cluster the flat collection first and choose the property that
 * labels the piles afterwards. Choosing it appends a group-by level, and setGroupOption used to
 * clear every cluster when it did. Now each clustered bucket's container follows its undecided
 * images into the bucket's "no value" child on the next rebuild, with the same pile ids; the
 * images that already have a value on the new level leave the piles the way a drain does.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { PropertyType } from '@/data/models'
import { Group, GroupType } from '@/core/group/types'
import { GroupManager } from '@/core/GroupManager'
import { setProperty } from '../harness/stubs/dataStore'
import { setColumn, setValue } from '../harness/stubs/columnStore'
import { actionStub, releaseAction } from '../harness/stubs/actionStore'
import {
    groupedBy, ungrouped, leafFor, emptyLeaf, pile, slotsOf, i2gProblems, coverageProblems,
} from '../harness/world'

// The property appended as the new leaf level.
const NEXT = 2
const ALL12 = Array.from({ length: 12 }, (_, i) => i)
const U = undefined

/** The group reached from the root by following these bucket values, level by level. */
function at(m: GroupManager, ...values: any[]): Group | undefined {
    let g: Group | undefined = m.result.root
    for (const v of values) {
        g = g?.children.find(c => c.type === GroupType.Property && c.meta.propertyValues?.[0]?.value === v)
    }
    return g
}

function sound(m: GroupManager) {
    assert.deepEqual(i2gProblems(m), [], 'imageToGroups names exactly the leaves')
    assert.deepEqual(coverageProblems(m), [], 'every root slot is shown by one leaf')
}

/** Append `propId` (a number property with column `values`) and rebuild, as the collection does. */
async function append(m: GroupManager, propId: number, values: any[], present = ALL12) {
    setProperty(propId, PropertyType.number)
    setColumn(propId, values)
    m.setGroupOption(propId)
    await m.group(new Int32Array(present), true)
}

test('E1: clusters on the ungrouped root move into the new level\'s "no value" group', async () => {
    const m = await ungrouped(12)
    m.clusters.addCustomGroups(0, [pile(9001, [0, 1, 2, 3]), pile(9002, [4, 5, 6])], true)
    sound(m)

    // Slots 1, 5 and 8 already have a value on the property the user picks.
    await append(m, NEXT, [U, 7, U, U, U, 7, U, U, 9, U, U, U])

    const empty = at(m, U)!
    assert.ok(empty, 'the "no value" group exists')
    assert.equal(m.clusters.overlay.container(0), undefined, 'the root holds no container any more')
    assert.ok(m.clusters.overlay.container(empty.id as number), 'the empty bucket does')
    assert.equal(m.result.index[9001]?.parent, empty, 'same pile id, now under the empty bucket')
    assert.deepEqual(slotsOf(m, 9001), [0, 2, 3], 'the image with a value left its pile')
    assert.deepEqual(slotsOf(m, 9002), [4, 6])
    assert.equal(m.result.index[9001].meta.maskedCount, undefined, 'and is not counted as hidden')
    const leftover = empty.children.find(c => c.isLeftover)!
    assert.deepEqual(leftover.slots, [7, 9, 10, 11], 'the leftover holds the rest of the bucket')
    assert.deepEqual(at(m, 7)!.slots, [1, 5], 'the valued images are in their value groups')
    assert.equal(at(m, 7)!.children.length, 0)
    sound(m)
})

test('E1: an image released by the move returns to its pile when its value is cleared', async () => {
    const m = await ungrouped(12)
    m.clusters.addCustomGroups(0, [pile(9001, [0, 1, 2, 3])], true)
    await append(m, NEXT, [U, 7, U, U, U, U, U, U, U, U, U, U])
    assert.deepEqual(slotsOf(m, 9001), [0, 2, 3])

    setValue(NEXT, 1, undefined)
    m.updateSelection(new Set([1001]), new Set())
    assert.deepEqual(slotsOf(m, 9001), [0, 1, 2, 3], 'the drain record brought it back')
    sound(m)
})

test('E1: with every image valued the container is dropped, not left waiting', async () => {
    const m = await ungrouped(4)
    m.clusters.addCustomGroups(0, [pile(9001, [0, 1])], true)
    setProperty(NEXT, PropertyType.number)
    setColumn(NEXT, [1, 1, 2, 2])
    m.setGroupOption(NEXT)
    await m.group(new Int32Array([0, 1, 2, 3]), true)

    assert.equal(m.clusters.overlay.byGroup.size, 0)
    assert.equal(m.result.index[9001], undefined)
    sound(m)
})

test('E1: a clustered leaf of an existing grouping moves down one level too', async () => {
    const m = await groupedBy([10, 10, 10, 10, 20, 20, 20, 20, NaN, NaN, NaN, NaN])
    const twenty = leafFor(m, 20)!
    const none = emptyLeaf(m)!
    m.clusters.addCustomGroups(twenty.id as number, [pile(9101, [4, 5])], true)
    m.clusters.clusterEmptyBucket(none.id as number, [pile(9102, [8, 9, 10])], true)

    await append(m, NEXT, [U, U, U, U, U, 3, U, U, U, 3, U, U])

    assert.equal(m.result.index[9101]?.parent, at(m, 20, U), 'under 20 / no value')
    assert.deepEqual(slotsOf(m, 9101), [4])
    assert.equal(m.result.index[9102]?.parent, at(m, U, U), 'under no value / no value')
    assert.deepEqual(slotsOf(m, 9102), [8, 10])
    assert.equal(m.clusters.emptyBucketId, at(m, U, U)!.id, 'the empty bucket id followed its piles')
    assert.equal(at(m, 10, U)!.children.length, 0, 'an unclustered leaf gains nothing')
    sound(m)
})

test('E1: two appends before one rebuild move the clusters two levels down', async () => {
    const m = await ungrouped(6)
    m.clusters.addCustomGroups(0, [pile(9001, [0, 1, 2])], true)
    setProperty(NEXT, PropertyType.number)
    setColumn(NEXT, [U, 1, U, U, U, U])
    setProperty(3, PropertyType.number)
    setColumn(3, [U, U, 4, U, U, U])
    m.setGroupOption(NEXT)
    m.setGroupOption(3)
    await m.group(new Int32Array([0, 1, 2, 3, 4, 5]), true)

    assert.equal(m.result.index[9001]?.parent, at(m, U, U))
    assert.deepEqual(slotsOf(m, 9001), [0])
    sound(m)
})

test('E1: removing a level still clears the clusters', async () => {
    const m = await ungrouped(6)
    m.clusters.addCustomGroups(0, [pile(9001, [0, 1, 2])], true)
    await append(m, NEXT, [U, U, U, U, U, U], [0, 1, 2, 3, 4, 5])
    assert.ok(m.result.index[9001])

    m.delGroupOption(NEXT)
    await m.group(new Int32Array([0, 1, 2, 3, 4, 5]), true)
    assert.equal(m.clusters.overlay.byGroup.size, 0)
    assert.equal(m.result.index[9001], undefined)
    sound(m)
})

test('E1: a rebuild after the move does not move the clusters again', async () => {
    const m = await ungrouped(6)
    m.clusters.addCustomGroups(0, [pile(9001, [0, 1, 2])], true)
    await append(m, NEXT, [U, U, U, U, U, U], [0, 1, 2, 3, 4, 5])
    const bucket = at(m, U)!.id
    await m.group(new Int32Array([0, 1, 2, 3, 4, 5]), true)
    assert.equal(m.result.index[9001]?.parent?.id, bucket)
    assert.deepEqual(slotsOf(m, 9001), [0, 1, 2])
    sound(m)
})

test('E1: a filtered-out owned image stays in its pile as a hidden member', async () => {
    const m = await ungrouped(6)
    m.clusters.addCustomGroups(0, [pile(9001, [0, 1, 2])], true)
    // Slot 2 is filtered out of the rebuild that applies the new level.
    await append(m, NEXT, [U, 5, U, U, U, U], [0, 1, 3, 4, 5])
    assert.deepEqual(slotsOf(m, 9001), [0])
    assert.equal(m.result.index[9001].meta.maskedCount, 1, 'slot 2 is hidden, slot 1 has left')

    await m.group(new Int32Array([0, 1, 2, 3, 4, 5]), true)
    assert.deepEqual(slotsOf(m, 9001), [0, 2], 'the filter lifted: it is back')
    sound(m)
})

test('E1: a bucket filtered away during the append follows the level and comes back', async () => {
    const m = await groupedBy([10, 10, 10, 10, 20, 20, 20, 20, 30, 30, 30, 30])
    const twenty = leafFor(m, 20)!.id as number
    m.clusters.addCustomGroups(twenty, [pile(9101, [4, 5])], true)
    const without20 = [0, 1, 2, 3, 8, 9, 10, 11]
    await append(m, NEXT, new Array(12).fill(U), without20)
    assert.equal(m.result.index[9101], undefined, 'nothing to show while the bucket is away')

    await m.group(new Int32Array(ALL12), true)
    assert.equal(m.result.index[9101]?.parent, at(m, 20, U), 'it waited under 20 / no value')
    assert.deepEqual(slotsOf(m, 9101), [4, 5])
    sound(m)
})

test('E1: a run on the root that lands after the append is rejected, not grafted', async () => {
    const m = await ungrouped(6)
    actionStub.defer = true
    const run = m.clusters.cluster(0, { funcId: 'f', inputs: [] })
    assert.equal(m.clusters.isClustering(0), true)

    await append(m, NEXT, [U, U, U, 1, U, U], [0, 1, 2, 3, 4, 5])
    releaseAction([pile(9201, [0, 1])])
    await run

    assert.equal(m.clusters.clusterError(0), 'not-a-leaf')
    assert.equal(m.clusters.overlay.byGroup.size, 0, 'no container opened on the grouped root')
    assert.equal(m.result.index[9201], undefined)
    sound(m)
})

test('E1: a run on a pile that lands after the append grafts under the moved pile', async () => {
    const m = await ungrouped(6)
    m.clusters.addCustomGroups(0, [pile(9001, [0, 1, 2, 3])], true)
    actionStub.defer = true
    const run = m.clusters.cluster(9001, { funcId: 'f', inputs: [] })

    await append(m, NEXT, [U, U, U, U, U, U], [0, 1, 2, 3, 4, 5])
    releaseAction([pile(9301, [0, 1])])
    await run

    assert.equal(m.clusters.clusterError(9001), undefined)
    assert.equal(m.result.index[9301]?.parent, m.result.index[9001], 'the sub-pile sits in the moved pile')
    assert.equal(m.result.index[9001].parent, at(m, U))
    sound(m)
})
