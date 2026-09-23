/**
 * A10 — a killed pile is gone for good; a detached one is only waiting.
 *
 * nodeOf/targetOf used to resolve a dead node, so an op naming a deleted pile was silently
 * rerouted (a move fell into the leftover, a merge went ahead with the survivors) instead of
 * being refused. A detached node is the opposite case and must stay resolvable.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { GroupType } from '@/core/group/types'
import { buildGroup } from '@/core/group/builders'
import { handTree, pile, slotsOf } from '../harness/world'

test('A10: a deleted pile is unresolvable through nodeOf/targetOf', () => {
    const { m, b } = handTree()
    const overlay = m.clusters.overlay
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    assert.ok(overlay.nodeOf(101), 'resolves before the delete')

    m.clusters.deletePile(101, false)
    assert.equal(overlay.nodeOf(101), undefined, 'nodeOf no longer resolves a dead pile')
    assert.equal(overlay.targetOf(101), undefined, 'targetOf no longer resolves a dead pile')
    assert.equal(m.result.index[101], undefined, 'and it is out of the tree index')
    const leftover = m.result.index[b.id].children.find(g => g.isLeftover)
    assert.deepEqual(leftover?.slots, [4, 5], 'its images fell through to the leftover')
})

test('A10: moveImagesToGroup into a dead pile is rejected, not rerouted', () => {
    const { m, b } = handTree()
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    m.clusters.deletePile(101, false)
    const before102 = slotsOf(m, 102)
    const leftoverBefore = m.result.index[b.id].children.find(g => g.isLeftover)!.slots.slice()

    m.clusters.moveImagesToGroup(102, 101, [1006], false)

    assert.deepEqual(slotsOf(m, 102), before102, 'the source pile is untouched')
    assert.deepEqual(m.result.index[b.id].children.find(g => g.isLeftover)!.slots, leftoverBefore,
        'and nothing was rerouted into the leftover')
})

test('A10: merge with a dead id is rejected, while a live merge still works', () => {
    const { m, b } = handTree()
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6]), pile(103, [7])], false)
    m.clusters.deletePile(101, false)
    const before = m.result.index[b.id].children.map(g => g.id).join()

    m.clusters.merge([101, 102], false)
    assert.equal(m.result.index[b.id].children.map(g => g.id).join(), before, 'refused')

    m.clusters.merge([102, 103], false)
    const merged = m.result.index[b.id].children.find(g => g.name === 'Merged')
    assert.deepEqual(merged?.slots, [6, 7], 'two live piles still merge')
})

test('A10: deleting an already dead pile a second time changes nothing', () => {
    const { m, b } = handTree()
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    m.clusters.deletePile(101, false)
    const snap = () => m.result.index[b.id].children.map(g => `${g.id}:${g.slots.join('|')}`).join()
    const before = snap()
    m.clusters.deletePile(101, false)
    assert.equal(snap(), before)
})

test('A10: a DETACHED node (bucket gone from the tree) stays resolvable and comes back', () => {
    const { m, b } = handTree()
    const overlay = m.clusters.overlay
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    const container = overlay.container(b.id as number)!
    const bucket = m.result.index[b.id]

    delete m.result.index[b.id]
    assert.equal(overlay.resync(container), true, 'the detach pass reports a change')
    assert.ok(overlay.nodeOf(101) && overlay.nodeOf(102), 'a waiting node is NOT dead')
    assert.equal(slotsOf(m, 101).length, 0, 'it holds nothing while detached')

    m.result.index[b.id] = bucket
    overlay.resync(container)
    assert.deepEqual(slotsOf(m, 101), [4, 5], 'the images come back when the bucket does')
    assert.deepEqual(slotsOf(m, 102), [6, 7])
})

test('A10: a node detached by a grouping level below the bucket stays resolvable too', () => {
    const { m, b } = handTree()
    const overlay = m.clusters.overlay
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    const container = overlay.container(b.id as number)!
    const bucket = m.result.index[b.id]

    // A property level appeared below the bucket, so its children are foreign now.
    const sub = buildGroup(301, [4, 5, 6, 7], GroupType.Property)
    bucket.children = [sub]
    m.regsiterGroup(sub)
    assert.equal(overlay.resync(container), true, 'the foreign-children pass reports a change')
    assert.ok(overlay.nodeOf(101) && overlay.nodeOf(102), 'the piles are waiting, not dead')
    assert.equal(m.result.index[101], undefined, 'and they are out of the tree meanwhile')

    delete m.result.index[301]
    bucket.children = []
    overlay.resync(container)
    assert.deepEqual(slotsOf(m, 101), [4, 5], 'they come back when the level goes')
    assert.deepEqual(slotsOf(m, 102), [6, 7])
})
