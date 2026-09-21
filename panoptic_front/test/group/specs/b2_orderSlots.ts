/**
 * B2 — orderSlots produces exactly what the full comparison sort produced.
 *
 * An incremental update leaves a group's slots as an ordered prefix plus a short appended tail,
 * so the array is merged rather than re-sorted. The result has to be element-for-element the
 * old `slots.sort(byPosition)`, ties included, or the display order silently drifts.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { orderSlots, slotPosition, SlotPositions } from '@/core/group/slotOrder'

/** Fixed-seed PRNG so a failure is reproducible; the seed is printed with the trial count. */
const SEED = 0x5eed1234
function mulberry32(a: number) {
    return function () {
        a |= 0; a = (a + 0x6D2B79F5) | 0
        let t = Math.imul(a ^ (a >>> 15), 1 | a)
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296
    }
}

function makePositions(n: number, rnd: () => number): SlotPositions {
    const perm = Array.from({ length: n }, (_, i) => i)
    for (let i = perm.length - 1; i > 0; i--) {
        const j = (rnd() * (i + 1)) | 0
        const tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp
    }
    const posArr = new Int32Array(n).fill(-1)
    for (let s = 0; s < n; s++) posArr[s] = perm[s]
    return { posArr, maxSlot: n - 1, count: n }
}

/** The sort orderSlots replaces. */
const reference = (slots: number[], p: SlotPositions) =>
    [...slots].sort((a, b) => slotPosition(a, p) - slotPosition(b, p))

function assertSameAsSort(label: string, slots: number[], cut: number, p: SlotPositions) {
    const want = reference(slots, p)
    const got = [...slots]
    orderSlots(got, cut, p)
    assert.deepEqual(got, want, `${label} (n=${slots.length}, cut=${cut}, seed=0x${SEED.toString(16)})`)
}

test(`B2: orderSlots matches the reference sort over 300 randomised trials (seed 0x${SEED.toString(16)})`, () => {
    const rnd = mulberry32(SEED)
    for (let trial = 0; trial < 300; trial++) {
        const n = 1 + ((rnd() * 4000) | 0)
        const extra = (rnd() * 20) | 0
        const p = makePositions(n, rnd)
        const nSlots = n + extra

        // the group before the edit: a subset of the collection, in display order
        let group: number[] = []
        for (let s = 0; s < n; s++) if (rnd() < 0.7) group.push(s)
        group = reference(group, p)

        // the edit: order-preserving removal, then an appended tail in arbitrary order
        const dropped = new Set(group.filter(() => rnd() < 0.15))
        const prefix = group.filter(s => !dropped.has(s))
        const tail: number[] = []
        for (const s of dropped) if (rnd() < 0.8) tail.push(s)
        const addCount = (rnd() * 30) | 0
        for (let i = 0; i < addCount; i++) tail.push((rnd() * nSlots) | 0)

        assertSameAsSort(`trial ${trial}`, [...prefix, ...tail], prefix.length, p)
    }
})

test('B2: orderSlots matches the reference sort on every edge case', () => {
    const p = makePositions(500, mulberry32(SEED ^ 0x1))
    const sorted = reference(Array.from({ length: 500 }, (_, i) => i), p)
    const cases: [string, number[], number][] = [
        ['empty group', [], 0],
        ['single slot, no append', [7], 1],
        ['single slot, appended', [7], 0],
        ['all removed, all appended', sorted.slice(0, 50), 0],
        ['nothing appended (grouped root)', sorted, sorted.length],
        ['nothing appended, one slot gone', sorted.filter((_, i) => i !== 123), sorted.length - 1],
        ['every slot appended, none kept', [...sorted].reverse(), 0],
        ['one appended to a long prefix', [...sorted.slice(0, 499), sorted[499]], 499],
        ['appended tail longer than prefix', [...sorted.slice(0, 10), ...[...sorted].reverse()], 10],
        ['duplicate positions (same slot twice)', [...sorted.slice(0, 20), sorted[3], sorted[3], sorted[19]], 20],
        ['duplicates inside the prefix too', [sorted[1], sorted[1], sorted[2], sorted[9], sorted[2]], 4],
        ['UNSORTED prefix -> full-sort fallback', [...sorted].reverse(), 500],
        ['unsorted prefix + tail', [...[...sorted.slice(0, 100)].reverse(), ...sorted.slice(200, 210)], 100],
        ['unknown slots (no recorded position)', [...sorted.slice(0, 30), 900, 700, 512], 30],
        ['cut past the end', sorted.slice(0, 40), 9999],
        ['negative cut', [...sorted.slice(0, 40)].reverse(), -5],
        ['stability with equal positions', [sorted[0], sorted[5], sorted[5], sorted[2], sorted[5]], 3],
    ]
    for (const [name, slots, cut] of cases) assertSameAsSort(name, slots, cut, p)
})

test('B2: a slot with no recorded position sorts after everything the last run ordered', () => {
    const p: SlotPositions = { posArr: Int32Array.from([2, 0, 1]), maxSlot: 2, count: 3 }
    const slots = [7, 0, 1, 2]
    orderSlots(slots, 0, p)
    assert.deepEqual(slots, [1, 2, 0, 7], 'the unknown slot lands last, not at position 0')
})
