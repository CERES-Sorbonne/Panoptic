/**
 * H1 — Tab between property cells is read off the scroller's own lines.
 *
 * The scrollers now mount an editor only for the edited cell, so Tab can no longer walk the
 * editors inputStore had registered (only the mounted ones, in image order). It walks the
 * scroller's full line list instead: the same property on the next / previous image in display
 * order, across lines and groups, skipping lines that draw no such cell, no wrap-around. The same
 * image drawn in two groups is two cells.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { adjacentCell, CellLines, CellTarget, findCell, revealOffset } from '@/components/scrollers/cellNavigation'
import { openPropertiesOf, sameCell } from '@/components/scrollers/cellEditing'

// lines as [groupId, instanceIds] — an empty list is a line with no cell (a group header)
function linesOf(spec: [number, number[]][]): CellLines {
    return {
        count: spec.length,
        cells: l => spec[l][1].length,
        at: (l, i) => ({ instanceId: spec[l][1][i], groupId: spec[l][0] }),
    }
}

const c = (instanceId: number, groupId: number): CellTarget => ({ instanceId, groupId })

// group 1: header, [10 11 12], [13]; group 2: header, [11 20]
const tree = linesOf([[1, []], [1, [10, 11, 12]], [1, [13]], [2, []], [2, [11, 20]]])

test('H1: Tab moves within a line, then to the next line, over group headers', () => {
    assert.deepEqual(adjacentCell(tree, c(10, 1), false)?.cell, c(11, 1))
    assert.deepEqual(adjacentCell(tree, c(12, 1), false)?.cell, c(13, 1))
    const next = adjacentCell(tree, c(13, 1), false)
    assert.deepEqual(next?.cell, c(11, 2))
    assert.equal(next?.line, 4)
    assert.equal(next?.index, 0)
})

test('H1: Shift-Tab walks back the same way', () => {
    assert.deepEqual(adjacentCell(tree, c(11, 2), true)?.cell, c(13, 1))
    assert.deepEqual(adjacentCell(tree, c(13, 1), true)?.cell, c(12, 1))
    assert.deepEqual(adjacentCell(tree, c(11, 1), true)?.cell, c(10, 1))
})

test('H1: no wrap-around at either end', () => {
    assert.equal(adjacentCell(tree, c(10, 1), true), undefined)
    assert.equal(adjacentCell(tree, c(20, 2), false), undefined)
})

test('H1: the same image in two groups is two cells', () => {
    assert.deepEqual(adjacentCell(tree, c(11, 1), false)?.cell, c(12, 1))
    assert.deepEqual(adjacentCell(tree, c(11, 2), false)?.cell, c(20, 2))
    assert.equal(findCell(tree, c(11, 2))?.line, 4)
})

test('H1: a cell that is not drawn goes nowhere', () => {
    assert.equal(adjacentCell(tree, c(99, 1), false), undefined)
    assert.equal(adjacentCell(tree, c(10, 2), false), undefined)
    assert.equal(adjacentCell(linesOf([]), c(10, 1), false), undefined)
})

test('H1: the start hint only speeds the search up', () => {
    // right hint, wrong hint (past the cell), out-of-range hint: same answer
    for (const hint of [3, 4, 0, 100, -5]) {
        assert.deepEqual(adjacentCell(tree, c(11, 2), true, hint)?.cell, c(13, 1), `hint ${hint}`)
        assert.deepEqual(adjacentCell(tree, c(10, 1), false, hint)?.cell, c(11, 1), `hint ${hint}`)
    }
})

test('H1: one cell per row (the grid)', () => {
    const grid = linesOf([[1, []], [1, [5]], [1, [6]], [2, []], [2, [7]]])
    assert.deepEqual(adjacentCell(grid, c(6, 1), false)?.cell, c(7, 2))
    assert.deepEqual(adjacentCell(grid, c(7, 2), true)?.cell, c(6, 1))
})

test('H1: revealOffset scrolls as little as possible', () => {
    // viewport [100, 400)
    assert.equal(revealOffset(150, 100, 100, 300), undefined, 'already in view')
    assert.equal(revealOffset(50, 100, 100, 300), 50, 'above: align its top')
    assert.equal(revealOffset(350, 100, 100, 300), 150, 'below: align its bottom')
    assert.equal(revealOffset(500, 400, 100, 300), 500, 'taller than the viewport: align its top')
    assert.equal(revealOffset(100, 300, 100, 300), undefined, 'exactly fills it')
})

test('H1: openPropertiesOf keeps the previous array while a card is unchanged', () => {
    const open = [{ instanceId: 1, groupId: 1, propertyId: 3 }, { instanceId: 2, groupId: 1, propertyId: 4 }]
    const prev = openPropertiesOf(open, 1, 1)
    assert.deepEqual(prev, [3])
    assert.equal(openPropertiesOf(open, 1, 1, prev), prev, 'same content: same array')
    assert.deepEqual(openPropertiesOf(open, 1, 2, prev), [], 'other group: nothing open')
    const none = openPropertiesOf([], 5, 5)
    assert.equal(openPropertiesOf(open, 5, 5, none), none)
    assert.ok(sameCell(open[0], { instanceId: 1, groupId: 1, propertyId: 3 }))
    assert.ok(!sameCell(open[0], { instanceId: 1, groupId: 2, propertyId: 3 }))
})
