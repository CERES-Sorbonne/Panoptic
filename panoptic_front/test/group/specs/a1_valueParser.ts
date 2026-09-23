/**
 * A1 — one "no value" key per property type.
 *
 * A numeric column stores "unset" as NaN in the raw buffer the full rebuild reads, and readSlot
 * hands out null for that same slot to the incremental path. The old parsers collapsed only one
 * of the two, so the two paths minted two different empty buckets for the same property.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { PropertyType } from '@/data/models'
import { valueParser, isNoValue } from '@/core/group/valueParser'
import { GroupType, Group } from '@/core/group/types'
import { groupedBy, PROP, emptyLeaf, i2gProblems, coverageProblems } from '../harness/world'
import { setValue } from '../harness/stubs/columnStore'

const NUMERIC: [string, PropertyType][] = [
    ['number', PropertyType.number],
    ['color', PropertyType.color],
    ['_id', PropertyType._id],
    ['_height', PropertyType._height],
    ['_width', PropertyType._width],
]

for (const [name, type] of NUMERIC) {
    test(`A1 valueParser[${name}]: NaN, null and undefined all key to the same "no value"`, () => {
        const p = valueParser[type] as (x: any) => any
        assert.equal(p(NaN), undefined, 'NaN (raw buffer spelling)')
        assert.equal(p(null), undefined, 'null (readSlot spelling)')
        assert.equal(p(undefined), undefined, 'undefined (absent column)')
    })

    test(`A1 valueParser[${name}]: 0 is a value, not "no value"`, () => {
        const p = valueParser[type] as (x: any) => any
        assert.equal(p(0), 0)
        assert.equal(p(42), 42)
    })
}

test('A1 valueParser[checkbox]: false is a value, and null/undefined read as false', () => {
    const cb = valueParser[PropertyType.checkbox] as (x: any) => any
    assert.equal(cb(false), false)
    assert.equal(cb(null), false)
    assert.equal(cb(undefined), false)
    assert.equal(cb(true), true)
})

test('A1 valueParser[date]: NaN/null/undefined key alike, a real date round-trips', () => {
    const dt = valueParser[PropertyType.date] as (x: any) => any
    const d = new Date(0)
    assert.equal(dt(NaN), undefined)
    assert.equal(dt(null), undefined)
    assert.equal(dt(undefined), undefined)
    assert.equal(dt(d), d)
})

test('A1 isNoValue: NaN/null/undefined/"" are no value; 0, false, "a" and [] are values', () => {
    assert.ok(isNoValue(NaN) && isNoValue(null) && isNoValue(undefined) && isNoValue(''))
    assert.ok(!isNoValue(0) && !isNoValue(false) && !isNoValue('a') && !isNoValue([]))
})

// ── the integration form: the divergence that created two empty buckets ──────

const emptyBuckets = (m: any): Group[] =>
    (Object.values(m.result.index) as Group[]).filter(g =>
        g.type === GroupType.Property && g.meta?.propertyValues?.[0]?.value === undefined)

test('A1 integration: an unset slot added by updateSelection joins the SAME empty bucket the full build made', async () => {
    // slot 2 is unset from the start, so group() mints the empty bucket through the raw buffer.
    const m = await groupedBy([10, 10, NaN, 20])
    const built = emptyLeaf(m)
    assert.ok(built, 'group() made an empty bucket for the NaN slot')
    assert.deepEqual(built!.slots, [2], 'and it holds the unset slot')
    const builtId = built!.id

    // Clearing slot 3 now goes through readSlot, which spells the same "unset" as null.
    setValue(PROP, 3, NaN)
    m.updateSelection(new Set([1003]), new Set())

    const buckets = emptyBuckets(m)
    assert.equal(buckets.length, 1,
        `exactly one empty bucket, got ${buckets.length}: ${JSON.stringify(buckets.map(g => [g.id, g.slots]))}`)
    assert.equal(buckets[0].id, builtId, 'the incremental path reused the bucket group() minted')
    assert.deepEqual(buckets[0].slots.slice().sort((a, b) => a - b), [2, 3])
    assert.deepEqual(i2gProblems(m), [])
    assert.deepEqual(coverageProblems(m), [])
})

test('A1 integration: a full re-group keeps the bucket the incremental path used', async () => {
    const m = await groupedBy([10, 10, NaN, 20])
    setValue(PROP, 3, NaN)
    m.updateSelection(new Set([1003]), new Set())
    const idAfterUpdate = emptyLeaf(m)!.id

    await m.update()
    const buckets = emptyBuckets(m)
    assert.equal(buckets.length, 1, 'a rebuild does not add a second empty bucket')
    assert.equal(buckets[0].id, idAfterUpdate, 'and keeps the same stable id')
    assert.deepEqual(buckets[0].slots.slice().sort((a, b) => a - b), [2, 3])
})

test('A1 integration: 0 keeps its own bucket, separate from "no value"', async () => {
    const m = await groupedBy([0, NaN, 0, 10])
    const zero = (Object.values(m.result.index) as Group[])
        .find(g => g.meta?.propertyValues?.[0]?.value === 0)
    assert.ok(zero, '0 has a bucket of its own')
    assert.deepEqual(zero!.slots, [0, 2])
    assert.notEqual(zero!.id, emptyLeaf(m)!.id)
})
