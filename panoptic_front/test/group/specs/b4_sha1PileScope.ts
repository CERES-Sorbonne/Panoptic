/**
 * B4 — the scoped applySha1Piles(only) agrees with a full rebuild.
 *
 * Every structural cluster op recomputes the pile overlay for the leaves it touched instead of
 * sweeping the whole index. The scoped result must be byte-for-byte the full one, and a group
 * that stopped being a leaf must leave no entry behind.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { GroupManager } from '@/core/GroupManager'
import { handTree, pile } from '../harness/world'

/** The pile overlay, key-sorted so two runs compare directly. */
const snapshot = (m: GroupManager) => JSON.stringify(
    [...m.result.pileIndex.keys()].sort((a, b) => a - b).map(k => [k, m.result.pileIndex.get(k)]))

/** The scoped overlay the op just produced, against a full sweep of the same tree. */
function assertScopedEqualsFull(m: GroupManager, label: string) {
    const scoped = snapshot(m)
    m.applySha1Piles()                       // full sweep over result.index
    assert.equal(scoped, snapshot(m), `${label}: scoped overlay differs from the full rebuild`)
}

function sha1Tree() {
    const t = handTree()
    t.m.state.sha1Mode = true
    t.m.applySha1Piles()
    return t
}

test('B4: a full rebuild is idempotent (the reference)', () => {
    const { m } = sha1Tree()
    assertScopedEqualsFull(m, 'baseline')
})

test('B4: addCustomGroups — the clustered bucket stops being a leaf and loses its entry', () => {
    const { m, b } = sha1Tree()
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6])], false)
    assert.equal(m.result.pileIndex.has(b.id as number), false, 'bucket B kept a stale pile entry')
    assertScopedEqualsFull(m, 'addCustomGroups')
})

test('B4: split — a sub-clustered pile stops being a leaf and loses its entry', () => {
    const { m, b } = sha1Tree()
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5, 6]), pile(102, [7])], false)
    m.clusters.split(101, [pile(111, [4]), pile(112, [5])], false)
    assert.equal(m.result.pileIndex.has(101), false, 'sub-clustered pile 101 kept a stale entry')
    assertScopedEqualsFull(m, 'split')
})

test('B4: moveImagesToGroup between two piles of the same container', () => {
    const { m, b } = sha1Tree()
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    m.clusters.moveImagesToGroup(101, 102, [1004], false)
    assertScopedEqualsFull(m, 'moveImagesToGroup (same container)')
})

test('B4: moveImagesToGroup into a value group, and across two containers', () => {
    const { m, a, b, c } = sha1Tree()
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    m.clusters.addCustomGroups(c.id, [pile(201, [8, 9]), pile(202, [10, 11])], false)
    m.clusters.moveImagesToGroup(101, a.id as number, [1004], false)
    assertScopedEqualsFull(m, 'moveImagesToGroup (pile -> value group)')
    m.clusters.moveImagesToGroup(102, 201, [1006], false)
    assertScopedEqualsFull(m, 'moveImagesToGroup (across containers)')
})

test('B4: merge — the merged-away piles leave no entry', () => {
    const { m, b } = sha1Tree()
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6]), pile(103, [7])], false)
    m.clusters.merge([101, 102], false)
    assert.equal(m.result.pileIndex.has(101) || m.result.pileIndex.has(102), false,
        'merged-away piles kept entries')
    assertScopedEqualsFull(m, 'merge')
})

test('B4: delete — the deleted pile leaves no entry', () => {
    const { m, b } = sha1Tree()
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    m.clusters.deletePile(101, false)
    assert.equal(m.result.pileIndex.has(101), false, 'deleted pile kept an entry')
    assertScopedEqualsFull(m, 'delete')
})

test('B4: delCustomGroups — the bucket is a leaf again and gets its entry back', () => {
    const { m, b } = sha1Tree()
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    m.clusters.delCustomGroups(b.id as number, false)
    assert.ok(m.result.pileIndex.has(b.id as number), 'un-clustered bucket B got no entry back')
    assertScopedEqualsFull(m, 'delCustomGroups')
})

test('B4: drain', () => {
    const { m, b } = sha1Tree()
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    // The drained instances also leave the bucket, as the value write would do.
    const bucket = m.result.index[b.id]
    bucket.slots = bucket.slots.filter(s => s !== 4)
    m.clusters.drain(101, [1004], false)
    assertScopedEqualsFull(m, 'drain')
})

test('B4: clearCustomGroups', () => {
    const { m, b, c } = sha1Tree()
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    m.clusters.addCustomGroups(c.id, [pile(201, [8, 9]), pile(202, [10, 11])], false)
    m.clusters.clearCustomGroups(false)
    assertScopedEqualsFull(m, 'clearCustomGroups')
})
