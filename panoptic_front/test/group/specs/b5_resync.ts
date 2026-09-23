/**
 * B5 — resync reports a change only when something really changed.
 *
 * The return value drives whether updateSelection emits, so a resync that always claimed a
 * change made every unrelated value write redraw the whole tree.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { handTree, pile, slotsOf } from '../harness/world'

test('B5: a no-op resync returns false', () => {
    const { m, b } = handTree()
    const overlay = m.clusters.overlay
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    const c = overlay.container(b.id as number)!
    assert.equal(overlay.resync(c), false, 'first no-op pass')
    assert.equal(overlay.resync(c), false, 'and it stays quiet')
})

test('B5: a membership change is reported, and the next pass is quiet again', () => {
    const { m, b } = handTree()
    const overlay = m.clusters.overlay
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    const c = overlay.container(b.id as number)!
    overlay.resync(c)

    overlay.own(c, [6], overlay.nodeOf(101)!.idx)
    assert.equal(overlay.resync(c), true)
    assert.deepEqual(slotsOf(m, 101), [4, 5, 6], 'and the pass really moved it')
    assert.equal(overlay.resync(c), false)
})

test('B5: an ordering-only change is reported', () => {
    const { m, b } = handTree()
    const overlay = m.clusters.overlay
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    const c = overlay.container(b.id as number)!
    overlay.resync(c)

    m.result.index[b.id].slots = [6, 5, 4, 7]
    assert.equal(overlay.resync(c), true)
    assert.deepEqual(slotsOf(m, 101), [5, 4], 'the pile follows the new display order')
    assert.equal(overlay.resync(c), false)
})

test('B5: a deleted pile is reported', () => {
    const { m, b } = handTree()
    const overlay = m.clusters.overlay
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    const c = overlay.container(b.id as number)!
    overlay.resync(c)

    overlay.kill(c, overlay.nodeOf(102)!.idx)
    assert.equal(overlay.resync(c), true)
    assert.equal(overlay.resync(c), false)
})

test('B5: a masked-count-only change is reported', () => {
    const { m, b } = handTree()
    const overlay = m.clusters.overlay
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5]), pile(102, [6, 7])], false)
    const c = overlay.container(b.id as number)!
    const bucket = m.result.index[b.id]
    overlay.resync(c)

    // A slot leaves the bucket but its pile keeps owning it: membership shrinks, badge grows.
    bucket.slots = [4, 5, 6]
    assert.equal(overlay.resync(c), true)
    assert.equal(overlay.resync(c), false)
    bucket.slots = [4, 5, 6, 7]
    assert.equal(overlay.resync(c), true, 'the image coming back is reported too')
})

test('B5: a card that disappears (all its images masked) is reported', () => {
    const { m, b } = handTree()
    const overlay = m.clusters.overlay
    m.clusters.addCustomGroups(b.id, [pile(201, [4]), pile(202, [5, 6])], false)
    const c = overlay.container(b.id as number)!
    assert.equal(overlay.resync(c), false, 'quiet before')

    m.result.index[b.id].slots = [5, 6, 7]
    assert.equal(overlay.resync(c), true)
    assert.ok(!m.result.index[b.id].children.some(g => g.id === 201), 'and its card is gone')
    assert.equal(overlay.resync(c), false)
})

test('B5: resyncDirty over an untouched clustered bucket claims no change', () => {
    const { m, a, b } = handTree()
    m.clusters.addCustomGroups(b.id, [pile(301, [4, 5])], false)
    assert.equal(m.clusters.resyncDirty(new Set([b.id as number])), false)
    assert.equal(m.clusters.resyncDirty(new Set([a.id as number, b.id as number])), false,
        'a write to an unrelated bucket leaves this one quiet')
})
