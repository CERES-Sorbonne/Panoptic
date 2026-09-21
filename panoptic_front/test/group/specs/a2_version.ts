/**
 * A2 — a removal that really drops something bumps the result version.
 *
 * FilterManager rejects every dirty instance that fails the filter, including ones that were
 * already filtered out. The old test was `removed.size > 1`, so a single removed instance left
 * the version untouched and the scrollers kept drawing it.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { groupedBy, ungrouped, i2gProblems, coverageProblems } from '../harness/world'

test('A2: one removed instance bumps the version (ungrouped)', async () => {
    const m = await ungrouped(4)
    const before = m.version.value
    m.updateSelection(new Set(), new Set([1002]))
    assert.equal(m.version.value, before + 1, 'a single removal must emit')
    assert.ok(!m.result.root.slots.includes(2), 'and the slot is really gone')
    assert.deepEqual(i2gProblems(m), [])
})

test('A2: one removed instance bumps the version (grouped)', async () => {
    const m = await groupedBy([10, 10, 20, 20])
    const before = m.version.value
    m.updateSelection(new Set(), new Set([1002]))
    assert.equal(m.version.value, before + 1)
    assert.ok(!m.result.root.slots.includes(2))
    assert.deepEqual(coverageProblems(m), [])
})

test('A2: an instance that was never in the tree does NOT bump the version', async () => {
    // slot 3 is filtered out from the start, so rejecting it again changes nothing on screen.
    const m = await ungrouped(4, [0, 1, 2])
    assert.ok(!m.result.imageToGroups.has(1003), 'precondition: 1003 is not in the tree')
    const before = m.version.value
    m.updateSelection(new Set(), new Set([1003]))
    assert.equal(m.version.value, before, 'a no-op rejection must stay quiet')
})

test('A2: a rejection of an absent instance stays quiet while a real one still emits', async () => {
    const m = await groupedBy([10, 10, 20, 20], [0, 1, 2])
    const before = m.version.value
    m.updateSelection(new Set(), new Set([1003]))
    assert.equal(m.version.value, before, 'the absent instance alone is quiet')
    m.updateSelection(new Set(), new Set([1003, 1000]))
    assert.equal(m.version.value, before + 1, 'a real removal in the same call still emits')
})
