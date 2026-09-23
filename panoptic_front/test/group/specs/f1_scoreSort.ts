/**
 * F1 — a similarity search's scores sort before every property, then sortBy, then slot.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { SortManager, SortDirection } from '@/core/SortManager'
import { GroupManager } from '@/core/GroupManager'
import { PropertyType, GroupScoreList } from '@/data/models'
import { reset, PROP } from '../harness/world'
import { setSlots, setColumn, instanceIdOf } from '../harness/stubs/columnStore'
import { setProperty } from '../harness/stubs/dataStore'

// slots 0..5; slot 5 has no score (goes last)
const VALUES = [3, 1, 2, 1, 2, 9]
const SCORES = [0.5, 0.9, 0.5, 0.5, 0.9]

function scoresFor(maxIsBest: boolean): GroupScoreList {
    const valueIndex: { [id: number]: number } = {}
    SCORES.forEach((v, s) => { valueIndex[instanceIdOf(s)] = v })
    return { valueIndex, min: 0, max: 1, maxIsBest, description: '' }
}

function setup() {
    reset()
    setSlots(VALUES.length)
    setProperty(PROP, PropertyType.number)
    setColumn(PROP, VALUES)
}

const ALL = () => new Int32Array([0, 1, 2, 3, 4, 5])

test('F1 no sortBy: score first (best first), ties and missing by slot', async () => {
    setup()
    const sm = new SortManager()
    const scores = scoresFor(true)
    sm.scoreSource = () => scores
    const res = await sm.sort(ALL())
    assert.deepEqual(Array.from(res.slots), [1, 4, 0, 2, 3, 5])
})

test('F1 score -> sortBy -> slot', async () => {
    setup()
    const sm = new SortManager()
    sm.setSort(PROP, { direction: SortDirection.Ascending })
    const scores = scoresFor(true)
    sm.scoreSource = () => scores
    const res = await sm.sort(ALL())
    // 0.9: slot1(v1), slot4(v2); 0.5: slot3(v1), slot2(v2), slot0(v3); missing: slot5
    assert.deepEqual(Array.from(res.slots), [1, 4, 3, 2, 0, 5])
})

test('F1 maxIsBest=false sorts ascending, missing still last', async () => {
    setup()
    const sm = new SortManager()
    const scores = scoresFor(false)
    sm.scoreSource = () => scores
    const res = await sm.sort(ALL())
    assert.deepEqual(Array.from(res.slots), [0, 2, 3, 1, 4, 5])
})

test('F1 updateSelection re-inserts an updated image by its score', async () => {
    setup()
    const sm = new SortManager()
    sm.setSort(PROP, { direction: SortDirection.Ascending })
    const scores = scoresFor(true)
    sm.scoreSource = () => scores
    await sm.sort(ALL())
    scores.valueIndex[instanceIdOf(0)] = 1.0 // slot 0 becomes the best match
    sm.updateSelection(new Set([instanceIdOf(0)]), new Set())
    assert.deepEqual(Array.from(sm.result.slots), [0, 1, 4, 3, 2, 5])
})

test('F1 without scores the order is unchanged (slot order)', async () => {
    setup()
    const sm = new SortManager()
    const res = await sm.sort(ALL())
    assert.deepEqual(Array.from(res.slots), [0, 1, 2, 3, 4, 5])
})

test('F1 groups carry the scores for display', async () => {
    setup()
    const gm = new GroupManager()
    const scores = scoresFor(true)
    gm.scoreSource = () => scores
    gm.setGroupOption(PROP)
    await gm.group(ALL())
    for (const g of Object.values(gm.result.index)) assert.equal((g as any).scores, scores)
})
