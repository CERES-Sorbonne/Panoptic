/**
 * A8 — computeSha1Piles survives a slot with no sha1.
 *
 * sha1 is written eagerly at instance creation, so a missing one is an invariant breach — but
 * this runs inside synchronous structural edits, so it warns once per call and piles the slot
 * alone rather than throwing and leaving the edit half-applied. `order` must stay a permutation
 * of `slots` whatever happens, or the display order stops matching the group's membership.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { computeSha1Piles, pileCount, pileSlots, pileIndexOfSlot, PileData } from '@/core/sha1Piles'
import { capturedWarnings } from '../harness/console'

/** The shape contract every PileData must satisfy, whatever the input. */
function assertWellFormed(slots: number[], p: PileData, label: string) {
    assert.ok(Array.isArray(p.order) && Array.isArray(p.bounds), `${label}: shape`)
    assert.equal(p.order.length, slots.length, `${label}: order length === slots length`)
    assert.deepEqual([...p.order].sort((a, b) => a - b), [...slots].sort((a, b) => a - b),
        `${label}: order is a permutation of slots`)
    assert.equal(p.bounds[0], 0, `${label}: bounds starts at 0`)
    assert.equal(p.bounds[p.bounds.length - 1], p.order.length, `${label}: bounds ends at order.length`)
    for (let i = 1; i < p.bounds.length; i++) {
        assert.ok(p.bounds[i] >= p.bounds[i - 1], `${label}: bounds non-decreasing at ${i}`)
    }
    assert.equal(p.bounds.length - 1, pileCount(p), `${label}: bounds.length - 1 === pileCount`)
    const seen = new Set<number>()
    for (let k = 0; k < pileCount(p); k++) for (const s of pileSlots(p, k)) {
        assert.ok(!seen.has(s), `${label}: slot ${s} appears in exactly one pile`)
        seen.add(s)
    }
    for (const s of slots) {
        const k = pileIndexOfSlot(p, s)
        assert.ok(k >= 0 && k < pileCount(p), `${label}: pileIndexOfSlot in range for slot ${s}`)
        assert.ok(pileSlots(p, k).includes(s), `${label}: pileIndexOfSlot(${s}) names the pile holding it`)
    }
}

test('A8: a sha1-less slot does not throw, and each one is its own pile', () => {
    // slots 0..6, sha1s: 0=A 1=null 2=B 3=A 4=null 5=B 6=A
    const sha1s = ['A', null, 'B', 'A', null, 'B', 'A']
    const slots = [0, 1, 2, 3, 4, 5, 6]
    const ids = Int32Array.from([100, 101, 102, 103, 104, 105, 106])
    let p: PileData
    assert.doesNotThrow(() => { p = computeSha1Piles(slots, sha1s, ids) })
    assertWellFormed(slots, p!, 'mixed')
    assert.deepEqual(
        Array.from({ length: pileCount(p!) }, (_, k) => pileSlots(p!, k)),
        [[0, 3, 6], [1], [2, 5], [4]],
        'duplicates group in first-seen order; the sha1-less slots are singletons')
    for (const s of [1, 4]) {
        assert.equal(pileSlots(p!, pileIndexOfSlot(p!, s)).length, 1, `slot ${s} is piled alone`)
    }
})

test('A8: a sha1-less slot is reported exactly once per call, naming the count and a sample', () => {
    const sha1s = ['A', null, 'B', 'A', null, 'B', 'A']
    const ids = Int32Array.from([100, 101, 102, 103, 104, 105, 106])
    computeSha1Piles([0, 1, 2, 3, 4, 5, 6], sha1s, ids)
    const warns = capturedWarnings()
    assert.equal(warns.length, 1, `exactly one warn per call, got ${warns.length}`)
    assert.match(warns[0], /2\/7/)
    assert.match(warns[0], /slot 1/)
    assert.match(warns[0], /instance 101/)
})

test('A8: all slots sha1-less — still a permutation, one pile each, one warn', () => {
    const slots = [3, 1, 2]
    let p: PileData
    assert.doesNotThrow(() => { p = computeSha1Piles(slots, [null, null, null, null]) })
    assertWellFormed(slots, p!, 'all-null')
    assert.equal(pileCount(p!), 3)
    assert.deepEqual(p!.order, [3, 1, 2], 'order follows the input, nothing is dropped')
    assert.deepEqual(p!.bounds, [0, 1, 2, 3])
    assert.equal(capturedWarnings().length, 1)
    assert.match(capturedWarnings()[0], /3\/3/)
})

test('A8: an undefined sha1 (slot past the loaded column) does not throw either', () => {
    let p: PileData
    assert.doesNotThrow(() => { p = computeSha1Piles([0, 5], ['A']) })
    assertWellFormed([0, 5], p!, 'undefined-sha1')
    assert.equal(pileCount(p!), 2)
})

test('A8: an empty-string sha1 counts as missing while real duplicates stay one pile', () => {
    const slots = [0, 1, 2, 3]
    const p = computeSha1Piles(slots, ['X', 'X', '', 'X'])
    assertWellFormed(slots, p, 'empty-string')
    assert.deepEqual(pileSlots(p, 0), [0, 1, 3])
    assert.deepEqual(pileSlots(p, 1), [2])
})

test('A8: no duplicates and no nulls gives the singleton layout, with no warn', () => {
    const p = computeSha1Piles([0, 1, 2], ['A', 'B', 'C'])
    assertWellFormed([0, 1, 2], p, 'all-distinct')
    assert.deepEqual(p.order, [0, 1, 2])
    assert.deepEqual(p.bounds, [0, 1, 2, 3])
    assert.equal(capturedWarnings().length, 0)
})

test('A8: an empty leaf yields no layout and no warn', () => {
    assert.equal(computeSha1Piles([], ['A', null]), undefined)
    assert.equal(capturedWarnings().length, 0)
})

test('A8: pileIndexOfSlot returns -1 for a slot outside the layout', () => {
    const p = computeSha1Piles([0, 1], ['A', null])
    assert.equal(pileIndexOfSlot(p, 9), -1)
})
