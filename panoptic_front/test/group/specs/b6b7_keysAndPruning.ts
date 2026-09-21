/**
 * B6 / B7 — the bookkeeping the incremental path leaves behind.
 *
 * B6: a group minted by addInstanceToGroups used to carry buildGroup's empty `key`, so
 *     removeChildren's `if (c.key.length)` skipped its valueIndex cleanup and the id leaked.
 * B7: GroupValueIndex.delete removed only the `null` leaf, keeping the whole chain of Maps
 *     alive; and imageToGroups kept an empty Set for every instance that ever left the tree.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { PropertyType } from '@/data/models'
import { GroupManager } from '@/core/GroupManager'
import { GroupValueIndex } from '@/core/group/valueIndex'
import { Group } from '@/core/group/types'
import { groupedBy, ungrouped, reset, i2gProblems, PROP } from '../harness/world'
import { setSlots, setColumn, setValue } from '../harness/stubs/columnStore'
import { setProperty } from '../harness/stubs/dataStore'

const P1 = 1
const P2 = 2

/** Two-level grouping over 4 slots; `present` selects which ones the build sees. */
async function nested(present: number[]) {
    reset()
    setSlots(4)
    setProperty(P1, PropertyType.number)
    setProperty(P2, PropertyType.number)
    setColumn(P1, [10, 10, 20, 30])
    setColumn(P2, [1, 2, 1, 3])
    const m = new GroupManager()
    m.setGroupOption(P1)
    m.setGroupOption(P2)
    await m.group(new Int32Array(present))
    return m
}

const byKey = (m: GroupManager, key: any[]): Group | undefined =>
    (Object.values(m.result.index) as Group[]).find(g => g.key.length === key.length
        && g.key.every((v, i) => v === key[i]))

// ── B6 ───────────────────────────────────────────────────────────────────────

test('B6: a group minted by the incremental path carries a non-empty key', async () => {
    const m = await nested([0, 1, 2])            // slot 3 (30, 3) is not in the tree yet
    assert.equal(byKey(m, [30]), undefined, 'precondition: the 30 branch does not exist')

    m.updateSelection(new Set([1003]), new Set())

    const level1 = byKey(m, [30])
    const leaf = byKey(m, [30, 3])
    assert.ok(level1, 'the incremental path minted the level-1 group')
    assert.ok(leaf, 'and its leaf')
    assert.deepEqual(level1!.key, [30], 'the level-1 key is recorded, not left empty')
    assert.deepEqual(leaf!.key, [30, 3], 'and so is the leaf key')
    assert.deepEqual(leaf!.slots, [3])
})

test('B6: the incremental key matches what the full build records for the same branch', async () => {
    const m = await nested([0, 1, 2])
    m.updateSelection(new Set([1003]), new Set())
    const incrementalIds = { l1: byKey(m, [30])!.id, leaf: byKey(m, [30, 3])!.id }
    const incrementalKeys = { l1: byKey(m, [30])!.key, leaf: byKey(m, [30, 3])!.key }

    await m.update()                              // full build from root.slots

    assert.ok(byKey(m, [30]), 'the full build has the branch')
    assert.deepEqual(byKey(m, [30])!.key, incrementalKeys.l1, 'same level-1 key')
    assert.deepEqual(byKey(m, [30, 3])!.key, incrementalKeys.leaf, 'same leaf key')
    assert.equal(byKey(m, [30])!.id, incrementalIds.l1, 'and the same stable id')
    assert.equal(byKey(m, [30, 3])!.id, incrementalIds.leaf)
})

test('B6: an incrementally minted group cleans up its valueIndex entry when it goes', async () => {
    const m = await nested([0, 1, 2])
    m.updateSelection(new Set([1003]), new Set())
    const branch = byKey(m, [30])!
    const mintedId = branch.id

    // The branch empties out: the whole subtree should be unregistered, key cleanup included.
    m.removeChildren(branch)
    assert.equal(m.result.index[byKey(m, [30, 3])?.id as number], undefined)
    // A rebuild of the same branch must mint the SAME id again (the key survives at level 1)
    // rather than leaking a dead one.
    await m.update()
    assert.equal(byKey(m, [30])!.id, mintedId)
})

// ── B7 · GroupValueIndex.delete prunes empty ancestors ───────────────────────

const nodeCount = (idx: Map<any, any>): number => {
    let n = 0
    for (const [k, v] of idx) { if (k === null) continue; n += 1 + nodeCount(v) }
    return n
}

test('B7: delete prunes the empty ancestor Maps it minted', () => {
    const vi = new GroupValueIndex()
    vi.get(['a', 'b'])
    assert.equal(nodeCount(vi.index), 2, 'a -> b')
    vi.delete(['a', 'b'])
    assert.equal(nodeCount(vi.index), 0, 'the whole chain is gone, not just the null leaf')
    assert.equal(vi.index.size, 0)
})

test('B7: pruning one key never disturbs a sibling sharing its prefix', () => {
    const vi = new GroupValueIndex()
    const ab = vi.get(['a', 'b'])
    const ac = vi.get(['a', 'c'])
    assert.notEqual(ab, ac)

    vi.delete(['a', 'b'])
    assert.ok(vi.index.has('a'), 'the shared prefix survives')
    assert.equal(vi.index.get('a').has('b'), false, 'the deleted branch is gone')
    assert.equal(vi.index.get('a').has('c'), true, 'the sibling is untouched')
    assert.equal(vi.get(['a', 'c']), ac, 'and it still resolves to the same id')

    vi.delete(['a', 'c'])
    assert.equal(vi.index.size, 0, 'the prefix goes once nothing is left under it')
})

test('B7: a deeper key below the deleted one keeps the prefix alive', () => {
    const vi = new GroupValueIndex()
    const xy = vi.get(['x', 'y'])
    const xyz = vi.get(['x', 'y', 'z'])
    vi.delete(['x', 'y'])
    assert.ok(vi.index.has('x') && vi.index.get('x').has('y'), 'y stays: z lives under it')
    assert.equal(vi.get(['x', 'y', 'z']), xyz, 'the deeper key is untouched')
    assert.notEqual(vi.get(['x', 'y']), xy, 'while the deleted key mints a fresh id')
})

test('B7: deleting an unknown key is a no-op', () => {
    const vi = new GroupValueIndex()
    const ab = vi.get(['a', 'b'])
    vi.delete(['a', 'zzz'])
    vi.delete(['nope'])
    assert.equal(vi.get(['a', 'b']), ab)
})

// ── B7 · imageToGroups leaves no empty Set behind ────────────────────────────

test('B7: an instance leaving the tree leaves no empty membership Set', async () => {
    const m = await groupedBy([10, 10, 20, 20])
    assert.ok(m.result.imageToGroups.get(1002)?.size, 'precondition: 1002 is in a leaf')

    m.updateSelection(new Set(), new Set([1002]))

    assert.equal(m.result.imageToGroups.has(1002), false,
        'the entry is deleted, not left as an empty Set')
    assert.deepEqual(i2gProblems(m), [])
})

test('B7: the same holds on the ungrouped path and through removeChildren', async () => {
    const m = await ungrouped(4)
    m.updateSelection(new Set(), new Set([1001]))
    assert.equal(m.result.imageToGroups.has(1001), false)

    const g = await groupedBy([10, 10, 20, 20])
    g.removeChildren(g.result.root)
    for (const id of [1000, 1001, 1002, 1003]) {
        const set = g.result.imageToGroups.get(id)
        assert.ok(set === undefined || set.size > 0, `1000..1003: no empty Set for ${id}`)
    }
})

// ── B7 · newToTree classifies both spellings of "not in the tree" ────────────

test('B7: newToTree treats an ABSENT membership entry as new to the tree', async () => {
    const m = await groupedBy([10, 10, 20, 20], [0, 1, 2])
    assert.equal(m.result.imageToGroups.has(1003), false, 'precondition: absent entry')
    m.updateSelection(new Set([1003]), new Set())
    assert.equal(m.result.root.slots.filter(s => s === 3).length, 1, 'added to root exactly once')
})

test('B7: newToTree treats an EMPTY membership entry as new to the tree too', async () => {
    const m = await groupedBy([10, 10, 20, 20], [0, 1, 2])
    // The spelling the old code could leave behind: present but empty.
    m.result.imageToGroups.set(1003, new Set())
    m.updateSelection(new Set([1003]), new Set())
    assert.equal(m.result.root.slots.filter(s => s === 3).length, 1,
        'an empty Set must not read as "already in the tree"')
    assert.deepEqual(i2gProblems(m), [])
})

test('B7: an instance that IS in the tree is not re-appended to root', async () => {
    const m = await groupedBy([10, 10, 20, 20])
    setValue(PROP, 0, 20)
    m.updateSelection(new Set([1000]), new Set())
    assert.equal(m.result.root.slots.filter(s => s === 0).length, 1)
    assert.equal(m.result.root.slots.length, 4)
})
