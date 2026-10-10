import { test } from 'node:test'
import assert from 'node:assert/strict'
import { brushRectAt, cellAt, CellStroke, clipRect, lineCells, MAX_BRUSH_SIZE, nextBrushSize, rectBetween, worldToGrid } from '@/mixins/mapview/GridBrush'
import { cellCenter } from '@/mixins/mapview/GridLayout'

test('brush: a cell centre maps back to its cell', () => {
    const grid = { cols: 7, rows: 4, cells: new Map() }
    const size = 0.3
    for (let r = 0; r < grid.rows; r++) for (let c = 0; c < grid.cols; c++) {
        const [x, y] = cellCenter(grid, r * grid.cols + c, size)
        const { u, v } = worldToGrid(x, y, grid.cols, grid.rows, size)
        assert.deepEqual(cellAt(u, v), { c, r })
    }
})

test('brush: odd sizes centre on the cell under the cursor, even ones on the nearest corner', () => {
    assert.deepEqual(brushRectAt(5.3, 2.9, 1), { c0: 5, r0: 2, c1: 5, r1: 2 })
    assert.deepEqual(brushRectAt(5.3, 2.9, 3), { c0: 4, r0: 1, c1: 6, r1: 3 })
    assert.deepEqual(brushRectAt(5.3, 2.9, 2), { c0: 4, r0: 2, c1: 5, r1: 3 })
    assert.deepEqual(brushRectAt(5.7, 2.2, 2), { c0: 5, r0: 1, c1: 6, r1: 2 })
})

test('brush: rectangle between two cells, in any drag direction', () => {
    assert.deepEqual(rectBetween({ c: 6, r: 1 }, { c: 2, r: 4 }), { c0: 2, r0: 1, c1: 6, r1: 4 })
    assert.deepEqual(clipRect({ c0: -3, r0: 2, c1: 4, r1: 20 }, 10, 8), { c0: 0, r0: 2, c1: 4, r1: 7 })
    assert.equal(clipRect({ c0: 12, r0: 0, c1: 14, r1: 3 }, 10, 8), null)
})

test('brush: lines are 8-connected and include both ends', () => {
    for (const [a, b] of [[{ c: 0, r: 0 }, { c: 7, r: 3 }], [{ c: 4, r: 9 }, { c: -2, r: 0 }], [{ c: 3, r: 3 }, { c: 3, r: 3 }]]) {
        const line = lineCells(a, b)
        assert.deepEqual(line[0], a)
        assert.deepEqual(line[line.length - 1], b)
        assert.equal(line.length, Math.max(Math.abs(b.c - a.c), Math.abs(b.r - a.r)) + 1)
        for (let i = 1; i < line.length; i++) {
            assert.ok(Math.abs(line[i].c - line[i - 1].c) <= 1 && Math.abs(line[i].r - line[i - 1].r) <= 1)
        }
    }
})

test('brush: a fast drag leaves no gap between two stamps', () => {
    const s = new CellStroke(20, 10)
    s.stamp(1.5, 5.5, 1)
    s.stamp(15.5, 5.5, 1)
    for (let c = 1; c <= 15; c++) assert.equal(s.marks[5 * 20 + c], 1, `cell ${c}`)
    assert.equal(s.cells().length, 15)
})

test('brush: stamps are clipped to the grid', () => {
    const s = new CellStroke(5, 5)
    s.stamp(0.5, 0.5, 3)
    assert.deepEqual(s.cells(), [0, 1, 5, 6])
    const out = new CellStroke(5, 5)
    out.stamp(-10, -10, 3)
    assert.deepEqual(out.cells(), [])
})

test('brush: a rectangle replaces what it covered before', () => {
    const s = new CellStroke(6, 6)
    s.setRect({ c: 0, r: 0 }, { c: 4, r: 4 })
    s.setRect({ c: 1, r: 1 }, { c: 0, r: 2 })
    assert.deepEqual(s.cells(), [6, 7, 12, 13])
})

test('brush: size steps stay in bounds and come back the way they went', () => {
    assert.equal(nextBrushSize(1, -1), 1)
    assert.equal(nextBrushSize(MAX_BRUSH_SIZE, 1), MAX_BRUSH_SIZE)
    let size = 1
    const up = [size]
    while (size < MAX_BRUSH_SIZE) {
        const next = nextBrushSize(size, 1)
        assert.ok(next > size)
        up.push(size = next)
    }
    for (let i = up.length - 1; i > 0; i--) assert.ok(nextBrushSize(up[i], -1) < up[i])
    assert.deepEqual(up.slice(0, 8), [1, 2, 3, 4, 5, 6, 7, 8])
})
