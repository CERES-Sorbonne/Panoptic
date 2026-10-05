import { test } from 'node:test'
import assert from 'node:assert/strict'
import { cellCenter, computeGridAssignment, mapGrid } from '@/mixins/mapview/GridLayout'
import { blobCloud } from '../harness/data'

function mapData(n: number, seed = 1): any[] {
    const c = blobCloud(n, 4, seed)
    const data: any[] = []
    for (let i = 0; i < n; i++) data.push(`sha${i}`, c.xs[i], c.ys[i])
    return data
}

test('mapGrid: one cell per sha1, matching computeGridAssignment', () => {
    const data = mapData(500)
    const grid = mapGrid(data, 1.5)
    const xs = [], ys = []
    for (let i = 0; i < data.length; i += 3) { xs.push(data[i + 1]); ys.push(data[i + 2]) }
    const a = computeGridAssignment(xs, ys, 1.5)
    assert.equal(grid.cols, a.cols)
    assert.equal(grid.cells.size, 500)
    for (let i = 0; i < 500; i++) assert.equal(grid.cells.get(`sha${i}`), a.row[i] * a.cols + a.col[i])
})

test('mapGrid: cached per map and density, last three densities kept', () => {
    const data = mapData(300)
    const g15 = mapGrid(data, 1.5)
    assert.equal(mapGrid(data, 1.5), g15, 'same map and density: cached')
    assert.notEqual(mapGrid(mapData(300), 1.5), g15, 'another data array: its own grid')

    const g2 = mapGrid(data, 2)
    mapGrid(data, 1.5)
    mapGrid(data, 3)
    mapGrid(data, 1)
    assert.equal(mapGrid(data, 1.5), g15, 'recently used density survives')
    assert.notEqual(mapGrid(data, 2), g2, 'least recently used density was evicted')
})

test('cellCenter: grid centred on the origin, one cell size apart', () => {
    const grid = { cols: 4, rows: 2, cells: new Map() }
    assert.deepEqual(cellCenter(grid, 0, 2), [-3, -1])
    assert.deepEqual(cellCenter(grid, 7, 2), [3, 1])
    assert.deepEqual(cellCenter(grid, 5, 2), [-1, 1])
})
