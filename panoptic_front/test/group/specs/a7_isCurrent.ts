/**
 * A7 — isCurrent answers false for an iterator that never resolved.
 *
 * isCurrent used to start with the revision fast path, so a handle built from a missing id
 * reported "current" for as long as the tree did not change — and callers then dereferenced a
 * group that was never there.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { handTree } from '../harness/world'

const MISSING = 999999

test('A7: an iterator that never resolved is not current, without any rev change', () => {
    const { m } = handTree()
    const revBefore = m.result.rev
    const bad = m.result.getGroupIterator(MISSING)
    assert.equal(bad.isValid, false)
    assert.equal(bad.isCurrent, false, 'isValid must be tested before the rev fast path')
    assert.equal(m.result.rev, revBefore, 'the rev really did not move')
    assert.equal(bad.isCurrent, false, 'still false on a second read')
})

test('A7: an ImageIterator that never resolved is not current, without any rev change', () => {
    const { m } = handTree()
    const revBefore = m.result.rev
    const bad = m.result.getImageIterator(MISSING, 0)
    assert.equal(bad.isValid, false)
    assert.equal(bad.isCurrent, false)
    assert.equal(m.result.rev, revBefore)
})

test('A7: re-stamping still works for a valid iterator', () => {
    const { m, b } = handTree()
    const it = m.result.getGroupIterator(b.id as number)
    assert.equal(it.isCurrent, true, 'current at the rev it was built on')
    m.result.buildOrdinalRanges()          // rev++, same node
    assert.equal(it.isCurrent, true, 'same node at a new rev is still current')
    assert.equal(it.isCurrent, true, 'and the re-stamp makes the repeat read cheap')
})

test('A7: a valid iterator stops being current when its node is replaced', () => {
    const { m, b } = handTree()
    const it = m.result.getGroupIterator(b.id as number)
    assert.equal(it.isCurrent, true)
    m.result.index[b.id as number] = { ...m.result.index[b.id as number] }
    m.result.buildOrdinalRanges()
    assert.equal(it.isCurrent, false)
})

test('A7: an ImageIterator stops being current when its group loses the image', () => {
    const { m, b } = handTree()
    const it = m.result.getImageIterator(b.id as number, 3)
    assert.equal(it.isCurrent, true)
    m.result.index[b.id as number].slots.length = 1      // same node, fewer images
    m.result.buildOrdinalRanges()
    assert.equal(it.isCurrent, false, 'imageIdx past the end is not a position')
})
