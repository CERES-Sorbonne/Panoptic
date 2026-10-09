import { test } from 'node:test'
import assert from 'node:assert/strict'
import { groupIslands, groupStrokes, STROKE_STRIDE } from '@/mixins/mapview/GridRegions'

// Rows from the top of the picture down; row 0 of the grid is the last string.
function grid(...lines: string[]) {
    const rows = lines.length, cols = lines[0].length
    const cellGroup = new Int32Array(cols * rows)
    lines.forEach((line, i) => {
        const r = rows - 1 - i
        for (let c = 0; c < cols; c++) cellGroup[r * cols + c] = line[c] === '.' ? -1 : Number(line[c])
    })
    return { cellGroup, cols, rows }
}

// "x0,y0,x1,y1 nx,ny g", sorted.
function strokes(flat: number[]) {
    const res: string[] = []
    for (let i = 0; i < flat.length; i += STROKE_STRIDE) {
        const [x0, y0, x1, y1, nx, ny, g] = flat.slice(i, i + STROKE_STRIDE)
        res.push(`${x0},${y0},${x1},${y1} ${nx},${ny} ${g}`)
    }
    return res.sort()
}

test('regions: a lone island is outlined by four merged strokes facing inwards', () => {
    const { cellGroup, cols, rows } = grid(
        '....',
        '.00.',
        '.00.',
        '....',
    )
    assert.deepEqual(strokes(groupStrokes(cellGroup, cols, rows)), [
        '1,1,1,3 1,0 0',
        '1,1,3,1 0,1 0',
        '1,3,3,3 0,-1 0',
        '3,1,3,3 -1,0 0',
    ])
})

test('regions: where two groups touch, each gets its own stroke on its side', () => {
    const { cellGroup, cols, rows } = grid(
        '0011',
        '0011',
    )
    const res = strokes(groupStrokes(cellGroup, cols, rows))
    assert.ok(res.includes('2,0,2,2 -1,0 0'))
    assert.ok(res.includes('2,0,2,2 1,0 1'))
    assert.ok(res.includes('0,0,2,0 0,1 0'), 'a run stops where the group changes')
    assert.ok(res.includes('2,0,4,0 0,1 1'))
    assert.equal(res.length, 8)
})

test('regions: no stroke inside a group nor around empty cells', () => {
    const empty = grid('...', '...')
    assert.deepEqual(groupStrokes(empty.cellGroup, empty.cols, empty.rows), [])
    const full = grid('00', '00')
    assert.equal(strokes(groupStrokes(full.cellGroup, full.cols, full.rows)).length, 4)
})

test('regions: islands are 4-connected, largest first', () => {
    const { cellGroup, cols, rows } = grid(
        '00.1',
        '0..1',
        '.0.1',
        '..11',
    )
    const islands = groupIslands(cellGroup, cols, rows)
    assert.deepEqual(islands.map(i => [i.group, i.size]), [[1, 5], [0, 3], [0, 1]])
})

test('regions: the label cell stays inside an island bent around its centroid', () => {
    const { cellGroup, cols, rows } = grid(
        '00000',
        '0....',
        '0....',
        '0....',
        '00000',
    )
    const [island] = groupIslands(cellGroup, cols, rows)
    assert.equal(island.size, 13)
    assert.equal(cellGroup[island.r * cols + island.c], 0)
})
