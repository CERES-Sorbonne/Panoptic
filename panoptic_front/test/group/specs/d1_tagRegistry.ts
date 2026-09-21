/**
 * D1 — an id the property's tag registry does not name is not a value.
 *
 * A tag delete tombstones the tag (dataStore.applyCommit `emptyTags`) but leaves the session's
 * column holding the id, so until a reload an image can carry a tag the registry no longer
 * names. The two bucketing paths read that id differently:
 *
 *   - the full rebuild (computePropertySubGroup) skipped it, and with no other tag on the slot
 *     the slot joined NO bucket at all — it vanished from the tree;
 *   - the incremental path (addInstanceToGroups) kept it, minting a group for a tag that no
 *     longer exists.
 *
 * Both now drop the id and let the slot fall into the empty bucket, so the image stays visible
 * under "no value" and no group is ever keyed on an unregistered tag.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { GroupManager } from '@/core/GroupManager'
import { PropertyType } from '@/data/models'
import { reset, leafFor, emptyLeaf, leaves, i2gProblems, coverageProblems, PROP } from '../harness/world'
import { setSlots, setColumn, setValue } from '../harness/stubs/columnStore'
import { setTagProperty, dataStub } from '../harness/stubs/dataStore'
import { sortGroupByProperty } from '@/core/group/sort'
import { buildGroup, buildRoot } from '@/core/group/builders'
import { GroupType } from '@/core/group/types'

// Tags 1 and 2 are registered; 9 is not (its tag was deleted this session).
const REGISTRY = { 1: [], 2: [] }

async function taggedBy(values: (number[] | null)[], registry: any = REGISTRY) {
    reset()
    setSlots(values.length)
    setTagProperty(PROP, PropertyType.multi_tags, registry)
    setColumn(PROP, values)
    const m = new GroupManager()
    m.setGroupOption(PROP)
    await m.group(new Int32Array(values.map((_, i) => i)))
    return m
}

test('D1: a slot whose only tag is unregistered lands in the empty bucket, not nowhere', async () => {
    const m = await taggedBy([[1], [1], [9], [2]])

    assert.deepEqual(emptyLeaf(m)?.slots, [2], 'slot 2 is under "no value"')
    assert.equal(leafFor(m, 9), undefined, 'no group is keyed on the unregistered id')
    assert.deepEqual(leafFor(m, 1)?.slots, [0, 1])
    assert.deepEqual(leafFor(m, 2)?.slots, [3])
    assert.deepEqual(coverageProblems(m), [])
    assert.deepEqual(i2gProblems(m), [])
})

test('D1: an unregistered id alongside a registered one just drops out', async () => {
    const m = await taggedBy([[1, 9], [9, 2]])

    assert.equal(leafFor(m, 9), undefined)
    assert.deepEqual(leafFor(m, 1)?.slots, [0])
    assert.deepEqual(leafFor(m, 2)?.slots, [1])
    assert.equal(emptyLeaf(m), undefined, 'neither slot lost its value')
    assert.deepEqual(coverageProblems(m), [])
})

test('D1: the incremental path reads an unregistered id the same way', async () => {
    const m = await taggedBy([[1], [1], [2], [2]])
    assert.equal(emptyLeaf(m), undefined)

    // Slot 2's tag is deleted while the session runs: the column still holds the id.
    setValue(PROP, 2, [9])
    m.updateSelection(new Set([1002]), new Set())

    assert.equal(leafFor(m, 9), undefined, 'the incremental path mints no group for it either')
    assert.deepEqual(emptyLeaf(m)?.slots, [2], 'it moved to "no value", not out of the tree')
    assert.deepEqual(coverageProblems(m), [])
    assert.deepEqual(i2gProblems(m), [])
})

test('D1: the two paths agree — a regroup after the incremental move changes nothing', async () => {
    const m = await taggedBy([[1], [1], [2], [2]])
    setValue(PROP, 2, [9])
    m.updateSelection(new Set([1002]), new Set())
    const before = leaves(m).map(g => [g.meta?.propertyValues?.[0]?.value, g.slots.join()].join(':')).sort()

    await m.update()

    const after = leaves(m).map(g => [g.meta?.propertyValues?.[0]?.value, g.slots.join()].join(':')).sort()
    assert.deepEqual(after, before, 'the full rebuild lands on the same tree')
    assert.equal(m.result.root.slots.length, 4, 'no image was dropped by the regroup')
    assert.deepEqual(coverageProblems(m), [])
})

test('D1: with no registry at all the column collapses to "no value" — it does not throw', async () => {
    // The old carve-out ("no registry -> every id is its own bucket") minted groups keyed on
    // raw tag ids, and sortGroupByProperty then handed a number to the tag sort parser:
    // TypeError, taking the whole view down. Unresolvable is better than fatal.
    const m = await taggedBy([[1], [9], [9]], {})

    assert.equal(leafFor(m, 9), undefined)
    assert.equal(leafFor(m, 1), undefined)
    assert.deepEqual(emptyLeaf(m)?.slots, [0, 1, 2])
    assert.deepEqual(coverageProblems(m), [])
    assert.deepEqual(i2gProblems(m), [])
})

test('D1: sortGroupByProperty survives a bucket keyed on an unregistered tag', () => {
    // Belt and braces for the crash above: build the illegal bucket by hand and sort it.
    reset()
    setTagProperty(PROP, PropertyType.multi_tags, REGISTRY)
    const parent = buildRoot([0, 1])
    const a = buildGroup(1, [0], GroupType.Property)
    a.meta.propertyValues = [{ propertyId: PROP, value: 9 } as any]
    const b = buildGroup(2, [1], GroupType.Property)
    b.meta.propertyValues = [{ propertyId: PROP, value: 1 } as any]
    parent.children = [a, b]

    assert.doesNotThrow(() => sortGroupByProperty(parent, 1, dataStub.properties, {} as any))
})
