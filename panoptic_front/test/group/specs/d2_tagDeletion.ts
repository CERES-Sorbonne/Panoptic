/**
 * D2 — what a tag deletion does to a tree that is grouped by that tag.
 *
 * Soft delete exists because a hard one left a visible group naming a tag that was gone, and the
 * code that read it back crashed the view. These tests pin down the whole sequence: what each
 * deletion style leaves behind, which of them the engine survives, and what has to happen for
 * the tree to stop showing a tag that no longer exists.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { GroupManager } from '@/core/GroupManager'
import { PropertyType, deletedID } from '@/data/models'
import { reset, leafFor, emptyLeaf, leaves, i2gProblems, coverageProblems, PROP } from '../harness/world'
import { setSlots, setColumn, stripTagsInStub } from '../harness/stubs/columnStore'
import { setTagProperty, deleteTagInStub, dataStub } from '../harness/stubs/dataStore'
import { stripTagIds } from '@/data/lib/columns'

const REGISTRY = { 1: [], 2: [] }

async function taggedBy(values: (number[] | null)[]) {
    reset()
    setSlots(values.length)
    setTagProperty(PROP, PropertyType.multi_tags, REGISTRY)
    setColumn(PROP, values)
    const m = new GroupManager()
    m.setGroupOption(PROP)
    await m.group(new Int32Array(values.map((_, i) => i)))
    return m
}

/**
 * The column half of a safe delete, through the store's own `stripTagIds`. Returns the instance
 * ids it reports as changed — exactly what removeTagIds feeds dataStore's dirty set.
 */
const scrubTag = (tagId: number) => stripTagsInStub(PROP, [tagId])

test('D2: a soft delete alone leaves the deleted tag on screen as a live group', async () => {
    const m = await taggedBy([[1], [1], [2]])
    assert.deepEqual(leafFor(m, 1)?.slots, [0, 1])

    deleteTagInStub(PROP, 1)

    // Nothing recomputed, so the group is still there, still holding its images.
    assert.deepEqual(leafFor(m, 1)?.slots, [0, 1], 'the group outlives the tag')
    // And it still resolves to a label, because the tombstone keeps the id as a key in
    // property.tags. That is the whole reason the delete is soft: the readers below look the
    // value up by id, and a missing entry is what used to take them down.
    assert.equal(dataStub.properties[PROP].tags[1].id, deletedID)
    assert.deepEqual(coverageProblems(m), [])
})

test('D2: the engine survives the window — neither delete style throws while the group is stale', async () => {
    for (const hard of [false, true]) {
        const m = await taggedBy([[1], [1], [2]])
        deleteTagInStub(PROP, 1, hard)

        // Everything the view can trigger before the recompute lands.
        assert.doesNotThrow(() => m.sortGroups(true), `sortGroups (hard=${hard})`)
        assert.doesNotThrow(() => m.updateSelection(new Set([1002]), new Set()), `updateSelection (hard=${hard})`)
        await assert.doesNotReject(() => m.update(), `update (hard=${hard})`)
    }
})

test('D2: scrub + incremental update retires the group and moves its images to "no value"', async () => {
    const m = await taggedBy([[1], [1], [2]])

    deleteTagInStub(PROP, 1)
    m.updateSelection(new Set(scrubTag(1)), new Set())

    assert.equal(leafFor(m, 1), undefined, 'the deleted tag no longer names a group')
    assert.deepEqual(emptyLeaf(m)?.slots, [0, 1], 'its images are under "no value"')
    assert.deepEqual(leafFor(m, 2)?.slots, [2], 'the surviving tag is untouched')
    assert.equal(m.result.root.slots.length, 3, 'no image was lost')
    assert.deepEqual(coverageProblems(m), [])
    assert.deepEqual(i2gProblems(m), [])
})

test('D2: a scrubbed image that still has another tag just loses the one', async () => {
    const m = await taggedBy([[1, 2], [1], [2]])
    assert.deepEqual(leafFor(m, 1)?.slots, [0, 1])

    deleteTagInStub(PROP, 1)
    m.updateSelection(new Set(scrubTag(1)), new Set())

    assert.equal(leafFor(m, 1), undefined)
    assert.deepEqual(leafFor(m, 2)?.slots, [0, 2], 'slot 0 kept its other tag')
    assert.deepEqual(emptyLeaf(m)?.slots, [1], 'slot 1 had nothing left')
    assert.deepEqual(coverageProblems(m), [])
    assert.deepEqual(i2gProblems(m), [])
})

test('D2: the incremental result equals a full regroup — no stale group either way', async () => {
    const m = await taggedBy([[1], [1], [2]])
    deleteTagInStub(PROP, 1)
    m.updateSelection(new Set(scrubTag(1)), new Set())
    const incremental = leaves(m).map(g => [g.meta?.propertyValues?.[0]?.value, g.slots.join()].join(':')).sort()

    await m.update()

    const full = leaves(m).map(g => [g.meta?.propertyValues?.[0]?.value, g.slots.join()].join(':')).sort()
    assert.deepEqual(full, incremental)
    assert.equal(leafFor(m, 1), undefined)
})

test('D2: without the scrub, a recompute alone already retires the group', async () => {
    // The D1 registry rule does half the job on its own: the ids are still in the column, but
    // neither bucketing path will key a group on one the registry does not name. The scrub is
    // what makes the stored data honest — and what gives the update a set of dirty instances
    // to run on in the first place.
    const m = await taggedBy([[1], [1], [2]])
    deleteTagInStub(PROP, 1)

    await m.update()

    assert.equal(leafFor(m, 1), undefined)
    assert.deepEqual(emptyLeaf(m)?.slots, [0, 1])
    assert.deepEqual(coverageProblems(m), [])
})

test('D2: stripTagIds reports exactly the slots it changed, and empties become "no value"', () => {
    const sparse = [[1, 2], [1], [2], null, [1, 3]]
    const changed = stripTagIds(sparse as any, sparse.length, new Set([1]))

    assert.deepEqual(changed, [0, 1, 4], 'only the slots carrying the id')
    assert.deepEqual(sparse[0], [2])
    assert.equal(sparse[1], null, 'nothing left -> null, not []')
    assert.deepEqual(sparse[2], [2], 'untouched')
    assert.equal(sparse[3], null)
    assert.deepEqual(sparse[4], [3])
})

test('D2: stripTagIds with nothing to drop touches nothing', () => {
    const sparse = [[1], [2]]
    assert.deepEqual(stripTagIds(sparse as any, 2, new Set()), [])
    assert.deepEqual(stripTagIds(sparse as any, 2, new Set([9])), [])
    assert.deepEqual(sparse, [[1], [2]])
})
