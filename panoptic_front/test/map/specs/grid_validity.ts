import { test } from 'node:test'
import assert from 'node:assert/strict'
import { computeGridAssignment } from '@/mixins/mapview/GridLayout'
import { blobCloud, rng, uniformCloud } from '../harness/data'
import { invalidCells } from '../harness/metrics'

test('grid: no points gives an empty grid', () => {
    const a = computeGridAssignment([], [])
    assert.equal(a.cols, 0)
    assert.equal(a.rows, 0)
    assert.equal(a.col.length, 0)
})

test('grid: tiny inputs get one distinct cell each', () => {
    for (let n = 1; n <= 5; n++) {
        const c = uniformCloud(n, n)
        const a = computeGridAssignment(c.xs, c.ys)
        assert.deepEqual(invalidCells(a), [], `n=${n}`)
        assert.ok(a.cols * a.rows >= n)
    }
})

test('grid: identical points still get distinct cells', () => {
    const xs = new Array(50).fill(3), ys = new Array(50).fill(-2)
    assert.deepEqual(invalidCells(computeGridAssignment(xs, ys)), [])
})

test('grid: collinear points (zero-height bbox)', () => {
    const xs = Array.from({ length: 200 }, (_, i) => i)
    const ys = new Array(200).fill(0)
    const a = computeGridAssignment(xs, ys)
    assert.deepEqual(invalidCells(a), [])
    assert.ok(a.cols > a.rows, 'a horizontal line gives a wide grid')
    // The line is several rows thick on the grid, so order only holds beyond one band of columns.
    for (let i = 0; i + 20 < 200; i++) assert.ok(a.col[i + 20] > a.col[i], `and keeps the order along x (${i})`)
})

test('grid: non-finite coordinates are placed, not dropped', () => {
    const xs = [0, 1, NaN, 3, Infinity], ys = [0, 1, 2, NaN, 4]
    assert.deepEqual(invalidCells(computeGridAssignment(xs, ys)), [])
})

test('grid: density 1 fills the grid, short of one row', () => {
    const c = blobCloud(997, 5)
    const a = computeGridAssignment(c.xs, c.ys, 1)
    assert.deepEqual(invalidCells(a), [])
    assert.ok(a.cols * a.rows - 997 < a.cols)
})

test('grid: density sets the share of empty cells', () => {
    const c = blobCloud(3000, 5)
    for (const d of [1.5, 2, 3, 10]) {
        const a = computeGridAssignment(c.xs, c.ys, d)
        assert.deepEqual(invalidCells(a), [], `d=${d}`)
        const ratio = a.cols * a.rows / 3000
        assert.ok(ratio >= d && ratio < d + 0.05, `d=${d}: ${ratio} cells per point`)
    }
})

test('grid: aspect follows the projection, within 1:4', () => {
    const rand = rng(3)
    const wide = computeGridAssignment(Array.from({ length: 1000 }, () => rand() * 300), Array.from({ length: 1000 }, () => rand() * 100))
    assert.ok(Math.abs(wide.cols / wide.rows - 3) < 0.2, `${wide.cols}x${wide.rows}`)
    const thin = computeGridAssignment(Array.from({ length: 1000 }, () => rand()), Array.from({ length: 1000 }, () => rand() * 100))
    assert.ok(Math.abs(thin.rows / thin.cols - 4) < 0.3, `${thin.cols}x${thin.rows}`)
})

test('grid: deterministic, and independent of input order', () => {
    const c = blobCloud(2000, 6, 9)
    const a = computeGridAssignment(c.xs, c.ys)
    const b = computeGridAssignment(c.xs, c.ys)
    assert.deepEqual(a, b)

    const perm = Array.from({ length: 2000 }, (_, i) => 1999 - i)
    const p = computeGridAssignment(perm.map(i => c.xs[i]), perm.map(i => c.ys[i]))
    let same = 0
    perm.forEach((i, k) => { if (p.col[k] === a.col[i] && p.row[k] === a.row[i]) same++ })
    assert.ok(same / 2000 > 0.99, `${same} / 2000 points kept their cell`)
})
