/**
 * A11 — a cluster run has a lifetime and a readable failure.
 *
 * A failure used to leave nothing a view could read, and a run entry outlived both the group it
 * targeted and the run that replaced it.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { GroupType } from '@/core/group/types'
import { buildGroup } from '@/core/group/builders'
import { handTree, pile } from '../harness/world'
import { actionStub } from '../harness/stubs/actionStore'
import { capturedWarnings } from '../harness/console'

const REQ = { funcId: 'f', inputs: [] }

test('A11: a failed run is readable through clusterError and is not "clustering"', async () => {
    const { m, root } = handTree()
    await m.clusters.cluster(root.id as number, REQ)          // the root is divided by a property
    assert.equal(m.clusters.clusterError(root.id as number), 'not-a-leaf')
    assert.equal(m.clusterError(root.id as number), 'not-a-leaf', 'exposed on GroupManager too')
    assert.equal(m.isClustering(root.id as number), false)
    assert.ok(capturedWarnings().some(w => w.includes('already divided by a property')),
        'and the failure is logged')
})

test('A11: the next run clears the previous error', async () => {
    const { m, b } = handTree()
    // First make it fail: give the bucket a property child, so it is not a leaf.
    const sub = buildGroup(401, [4, 5], GroupType.Property)
    m.setChildGroup(m.result.index[b.id], [sub])
    await m.clusters.cluster(b.id as number, REQ)
    assert.equal(m.clusters.clusterError(b.id as number), 'not-a-leaf')

    m.removeChildren(m.result.index[b.id])
    actionStub.next = [pile(501, [4, 5])]
    await m.clusters.cluster(b.id as number, REQ)
    assert.equal(m.clusters.clusterError(b.id as number), undefined, 'the successful run cleared it')
    assert.equal((m.clusters.runs as any)[b.id], undefined, 'and left no stale entry')
    assert.ok(m.result.index[501], 'the run really grafted its pile')
})

test('A11: an empty result is reported, and the run after it clears that too', async () => {
    const { m, b } = handTree()
    actionStub.next = []
    await m.clusters.cluster(b.id as number, REQ)
    assert.equal(m.clusters.clusterError(b.id as number), 'no-groups')

    actionStub.next = [pile(502, [6])]
    await m.clusters.cluster(b.id as number, REQ)
    assert.equal(m.clusters.clusterError(b.id as number), undefined)
})

test('A11: a thrown run is reported rather than swallowed', async () => {
    const { m, b } = handTree()
    actionStub.throws = true
    await m.clusters.cluster(b.id as number, REQ)
    assert.ok(m.clusters.clusterError(b.id as number), 'some error code is readable')
    assert.equal(m.clusters.isClustering(b.id as number), false, 'and the run is not left running')
})

test('A11: the entry of a group that left the tree is pruned, and clear() wipes the rest', async () => {
    const { m, b } = handTree()
    actionStub.next = []
    await m.clusters.cluster(b.id as number, REQ)
    assert.equal(m.clusters.clusterError(b.id as number), 'no-groups', 'entry present before the prune')

    const bucket = m.result.index[b.id]
    delete m.result.index[b.id]
    m.clusters.resyncAll()
    assert.equal((m.clusters.runs as any)[b.id], undefined, 'a vanished group leaks no entry')
    m.result.index[b.id] = bucket

    await m.clusters.cluster(b.id as number, REQ)
    m.clusters.clear()
    assert.deepEqual(Object.keys(m.clusters.runs), [], 'clear() wipes the runs')
})
