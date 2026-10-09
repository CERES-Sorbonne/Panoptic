/**
 * H2 — scroller lines are built in proportion to the change.
 *
 * Tree: an image/pile line is a range of its leaf (`groupId`, `start`, `count`), not an array of
 * ImageIterators, and each leaf's block of lines is cached under what it is a function of
 * (positions, piled, depth, width, imageSize, property count). The iterators the line components
 * make for a range must be exactly the ones the old per-image walk produced.
 *
 * Grid: one row per image, so a block is a function of the leaf's content; it is reused while the
 * tree did not change (open/close), and after a change while its rows still match the leaf.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { GroupManager } from '@/core/GroupManager'
import { Group } from '@/core/group/types'
import { GroupIterator, ImageIterator } from '@/core/group/GroupIterator'
import {
    BORDER, GAP, MARGIN_STEP, TreeLineCache, TreeLineParams, buildLeafLines, cardLineSize,
    lineFirstSlots, lineIterators, lineSlot,
} from '@/components/scrollers/tree/treeLines'
import { GridLineCache, MeasuredHeight, rowInstanceId } from '@/components/scrollers/grid/gridLines'
import { ImageLine, PileRowLine, RowLine, ScrollerLine } from '@/components/scrollers/types'
import { adjacentCell, CellLines } from '@/components/scrollers/cellNavigation'
import { columnStub } from '../harness/stubs/columnStore'
import { groupedBy, handTree, leafFor } from '../harness/world'

const params = (over: Partial<TreeLineParams> = {}): TreeLineParams =>
    ({ contentWidth: 400, imageSize: 100, propertyCount: 2, pilePropertyCount: 1, ...over })

/** TreeScroller.computeLines, minus Vue: the groups in display order, each open leaf's block. */
function treeLines(m: GroupManager, cache: TreeLineCache, p = params()): ScrollerLine[] {
    const lines: ScrollerLine[] = []
    let it: GroupIterator | undefined = m.getGroupIterator()
    while (it) {
        const group = it.group
        lines.push({ id: group.id, type: 'group', data: group, size: 30 })
        if (group.children.length === 0 && !group.view.closed) lines.push(...cache.leafLines(m.result, group, p))
        it = it.nextGroup()
    }
    cache.prune(m.result)
    return lines
}

const imageLinesOf = (lines: ScrollerLine[]) =>
    lines.filter(l => l.type === 'images' || l.type === 'piles') as ImageLine[]

/** The old computeImageLines walk over one leaf: every image's iterator, in line-sized chunks. */
function legacyWalk(m: GroupManager, group: Group, perLine: number): ImageIterator[][] {
    const out: ImageIterator[][] = []
    let line: ImageIterator[] = []
    let imgIt = ImageIterator.fromGroupIterator(m.getGroupIterator(group.id))
    while (imgIt && imgIt.isValid && imgIt.groupId == group.id) {
        line.push(imgIt)
        imgIt = imgIt.nextImages()
        if (line.length >= perLine) { out.push(line); line = [] }
    }
    if (line.length) out.push(line)
    return out
}

const sameIterator = (a: ImageIterator, b: ImageIterator) =>
    a.isValid === b.isValid && a.groupId === b.groupId && a.imageIdx === b.imageIdx && a.group === b.group
    && a.slot === b.slot && a.slots.join() === b.slots.join() && a.getImageOrder() === b.getImageOrder()

function assertMatchesLegacy(m: GroupManager, lines: ScrollerLine[], label: string) {
    const byGroup = new Map<number, ImageLine[]>()
    for (const l of imageLinesOf(lines)) {
        if (!byGroup.has(l.groupId)) byGroup.set(l.groupId, [])
        byGroup.get(l.groupId)!.push(l)
    }
    let checked = 0
    for (const [groupId, ls] of byGroup) {
        const group = m.result.index[groupId]
        const perLine = ls[0].count + ls[0].emptyCount
        const legacy = legacyWalk(m, group, perLine)
        assert.equal(ls.length, legacy.length, `${label}: leaf ${groupId} line count`)
        ls.forEach((line, k) => {
            assert.equal(line.type, m.result.pileIndex.has(groupId) ? 'piles' : 'images', `${label}: line type`)
            assert.equal(line.id, groupId + (line.type === 'piles' ? '|pile-' : '|img-') + k, `${label}: line id`)
            assert.equal(line.depth, group.depth + 1)
            const its = lineIterators(m.result, line)
            assert.equal(its.length, legacy[k].length, `${label}: leaf ${groupId} line ${k} size`)
            its.forEach((it, i) => assert.ok(sameIterator(it, legacy[k][i]), `${label}: leaf ${groupId} line ${k} image ${i}`))
            assert.deepEqual(lineFirstSlots(m.result, line), legacy[k].map(it => it.slot))
            legacy[k].forEach((it, i) => assert.equal(lineSlot(m.result, line, i), it.slot))
            checked += its.length
        })
    }
    return checked
}

async function flatTree() {
    // value 1: 10 images, value 2: 7, value 3: 1
    const values = [...Array(10).fill(1), ...Array(7).fill(2), 3]
    return groupedBy(values)
}

function pileTree() {
    const t = handTree()
    t.m.state.sha1Mode = true
    t.m.applySha1Piles()
    t.m.buildOrdinalRanges()
    return t
}

test('H2: flat range lines give the very iterators the per-image walk gave', async () => {
    const m = await flatTree()
    const lines = treeLines(m, new TreeLineCache())
    assert.equal(assertMatchesLegacy(m, lines, 'flat'), 18, 'every image is on a line')
})

test('H2: piled range lines give the per-pile iterators (slots = the whole pile)', () => {
    const { m, a, b } = pileTree()
    assert.ok(m.result.pileIndex.has(a.id as number) && m.result.pileIndex.has(b.id as number), 'the fixture piles')
    const lines = treeLines(m, new TreeLineCache())
    const piles = imageLinesOf(lines)
    assert.ok(piles.every(l => l.type === 'piles'))
    assert.equal(assertMatchesLegacy(m, lines, 'piled'), 9, 'one position per pile (3 per bucket)')
    const first = lineIterators(m.result, piles[0])
    assert.deepEqual(first[0].slots, [0, 1], 'a pile iterator holds every slot of its pile')
})

test('H2: line geometry is the old computeImageLines geometry', async () => {
    const m = await flatTree()
    const leaf = leafFor(m, 1)!
    const p = params()
    const lines = new TreeLineCache().leafLines(m.result, leaf, p)
    const width = p.contentWidth - (leaf.depth + 1) * MARGIN_STEP
    const perLine = Math.max(1, Math.floor(width / (p.imageSize + BORDER + GAP)))
    const want: number[][] = []
    for (let start = 0; start < 10; start += perLine) {
        const count = Math.min(perLine, 10 - start)
        want.push([start, count, perLine - count])
    }
    assert.ok(want.length > 1 && want[want.length - 1][2] > 0, 'the fixture has a partial last line')
    assert.deepEqual(lines.map(l => [l.start, l.count, l.emptyCount]), want)
    const widths = lines[0].cardWidths
    assert.equal(widths.length, perLine)
    assert.equal(widths.reduce((a, b) => a + b + BORDER, 0) + GAP * (perLine - 1), width, 'cells fill the line exactly')
    assert.ok(lines.every(l => l.cardWidths === widths && l.size === cardLineSize(l.imageSize, p.propertyCount)))
})

test('H2: an unchanged leaf hands back the same block — open/close re-lines nothing', async () => {
    const m = await flatTree()
    const cache = new TreeLineCache()
    const before = imageLinesOf(treeLines(m, cache))
    const two = leafFor(m, 2)!
    m.closeGroup(two.id, true)
    const closed = imageLinesOf(treeLines(m, cache))
    assert.ok(closed.every(l => l.groupId !== two.id), 'a closed leaf draws no line')
    assert.ok(closed.every(l => before.includes(l)), 'the other leaves keep their line objects')
    m.openGroup(two.id, true)
    const reopened = imageLinesOf(treeLines(m, cache))
    assert.equal(reopened.length, before.length)
    reopened.forEach((l, i) => assert.equal(l, before[i], `line ${i} is the same object after reopening`))
})

test('H2: a changed key rebuilds the block, keeping the lines that come out the same', async () => {
    const m = await flatTree()
    const cache = new TreeLineCache()
    const leaf = leafFor(m, 1)!
    const p = params()
    const before = cache.leafLines(m.result, leaf, p)
    // The leaf grows at its end: its first full lines are unchanged.
    leaf.slots.push(leaf.slots[0])
    const grown = cache.leafLines(m.result, leaf, p)
    assert.notEqual(grown, before)
    assert.equal(grown[0], before[0], 'a full line before the change is kept')
    assert.notEqual(grown[grown.length - 1], before[before.length - 1], 'the partial line is redone')
    leaf.slots.pop()
    // Wider: every line changes.
    const wide = cache.leafLines(m.result, leaf, params({ contentWidth: 900 }))
    assert.ok(wide.every(l => !before.includes(l)))
    // Same key again: the very same block.
    assert.equal(cache.leafLines(m.result, leaf, params({ contentWidth: 900 })), wide)
})

test('H2: resize changes every cached block in place, closed leaves included', async () => {
    const m = await flatTree()
    const cache = new TreeLineCache()
    const p = params()
    const two = leafFor(m, 2)!
    const twoLines = cache.leafLines(m.result, two, p)
    m.closeGroup(two.id)
    const drawn = imageLinesOf(treeLines(m, cache, p))
    cache.resize(5, 1)
    for (const l of [...drawn, ...twoLines]) assert.equal(l.size, cardLineSize(l.imageSize, 5))
    m.openGroup(two.id)
    const after = imageLinesOf(treeLines(m, cache, params({ propertyCount: 5 })))
    assert.ok(twoLines.every(l => after.includes(l)), 'the resized block is reused, not rebuilt')
})

test('H2: prune drops the blocks of groups the tree lost; a new host starts empty', async () => {
    const m = await flatTree()
    const cache = new TreeLineCache()
    treeLines(m, cache)
    assert.equal(cache.size, 3)
    const three = leafFor(m, 3)!
    delete m.result.index[three.id]
    cache.prune(m.result)
    assert.equal(cache.size, 2)
    const other = await flatTree()
    const leaf = leafFor(other, 1)!
    cache.leafLines(other.result, leaf, params())
    assert.equal(cache.size, 1, 'blocks of the previous tree are gone')
})

test('H2: lineIterators keeps the previous array only while it still describes the tree', async () => {
    const m = await flatTree()
    const leaf = leafFor(m, 1)!
    const [line] = new TreeLineCache().leafLines(m.result, leaf, params())
    const first = lineIterators(m.result, line)
    assert.equal(lineIterators(m.result, line, first), first, 'nothing changed')
    m.buildOrdinalRanges()
    assert.equal(lineIterators(m.result, line, first), first, 'a rebuild that left these images alone')
    // In place, same length: the line object (a range) is unchanged, its images are not.
    leaf.slots.reverse()
    m.buildOrdinalRanges()
    const now = lineIterators(m.result, line, first)
    assert.notEqual(now, first)
    assert.deepEqual(now.map(it => it.slot), leaf.slots.slice(0, line.count))
    // The same range of another tree is not this one.
    const other = await flatTree()
    assert.notEqual(lineIterators(other.result, line, now), now)
})

test('H2: a line outliving its leaf draws what is left of it, not a throw', async () => {
    const m = await flatTree()
    const leaf = leafFor(m, 1)!
    const lines = new TreeLineCache().leafLines(m.result, leaf, params())
    const last = lines[lines.length - 1]
    leaf.slots.length = last.start + 1
    m.buildOrdinalRanges()
    assert.equal(lineIterators(m.result, last).length, 1)
    assert.equal(lineFirstSlots(m.result, last).length, 1)
    assert.equal(lineSlot(m.result, last, 1), undefined)
    delete m.result.index[leaf.id]
    assert.equal(lineIterators(m.result, last).length, 0)
    assert.deepEqual(lineFirstSlots(m.result, last), [])
})

test('H2: an empty leaf draws no line', () => {
    assert.deepEqual(buildLeafLines(1, { positions: 0, piled: false, depth: 0, width: 400, imageSize: 100, propertyCount: 0 }, 100), [])
})

test('H2: Tab walks the range lines like it walked the iterator lines', async () => {
    const m = await flatTree()
    const lines = treeLines(m, new TreeLineCache())
    const ids = columnStub.instanceIds()
    // TreeScroller.cellLines
    const cells: CellLines = {
        count: lines.length,
        cells: l => lines[l].type === 'images' ? (lines[l] as ImageLine).count : 0,
        at: (l, i) => ({ instanceId: ids[lineSlot(m.result, lines[l] as ImageLine, i)!], groupId: lines[l].groupId! }),
    }
    const one = leafFor(m, 1)!, two = leafFor(m, 2)!
    const last = { instanceId: ids[one.slots[one.slots.length - 1]], groupId: one.id }
    assert.deepEqual(adjacentCell(cells, last, false)?.cell, { instanceId: ids[two.slots[0]], groupId: two.id })
    assert.deepEqual(adjacentCell(cells, { instanceId: ids[two.slots[0]], groupId: two.id }, true)?.cell, last)
})

// ── grid ─────────────────────────────────────────────────────────────────────

function gridRows(m: GroupManager, cache: GridLineCache, size = 28, measured?: MeasuredHeight): ScrollerLine[] {
    const out: ScrollerLine[] = []
    const ids = columnStub.instanceIds()
    const visit = (g: Group) => {
        if (g.children.length) { if (!g.view.closed) g.children.forEach(visit); return }
        if (!g.view.closed) out.push(...cache.leafLines(m.result, g, ids, size, measured))
    }
    visit(m.result.root)
    cache.prune(m.result)
    return out
}

test('H2 grid: rows are one per image, as before, and unchanged leaves keep them over open/close', async () => {
    const m = await flatTree()
    const cache = new GridLineCache()
    const ids = columnStub.instanceIds()
    const rows = gridRows(m, cache)
    assert.equal(rows.length, 18)
    const one = leafFor(m, 1)!
    const r0 = rows[0] as RowLine
    assert.equal(r0.id, one.id + '-img:' + ids[one.slots[0]])
    assert.deepEqual([r0.type, r0.groupId, r0.index, r0.data.id], ['image', one.id, 0, ids[one.slots[0]]])
    m.closeGroup(one.id, true)
    const closed = gridRows(m, cache)
    assert.equal(closed.length, 8)
    assert.ok(closed.every(r => rows.includes(r)))
    m.openGroup(one.id, true)
    gridRows(m, cache).forEach((r, i) => assert.equal(r, rows[i], `row ${i} kept`))
})

test('H2 grid: after a tree change, only the leaves whose rows changed are re-rowed', async () => {
    const m = await flatTree()
    const cache = new GridLineCache()
    const ids = columnStub.instanceIds()
    const rows = gridRows(m, cache)
    const one = leafFor(m, 1)!, two = leafFor(m, 2)!
    // In place, same array and length — only the rev says something happened.
    two.slots.reverse()
    m.buildOrdinalRanges()
    const after = gridRows(m, cache)
    const oneRows = (rs: ScrollerLine[]) => rs.filter(r => r.groupId === one.id)
    const twoRows = (rs: ScrollerLine[]) => rs.filter(r => r.groupId === two.id)
    oneRows(after).forEach((r, i) => assert.equal(r, oneRows(rows)[i], 'leaf 1 untouched: same rows'))
    assert.ok(twoRows(after).every(r => !rows.includes(r)), 'leaf 2 re-rowed')
    assert.deepEqual(twoRows(after).map(r => (r as RowLine).data.id), two.slots.map(s => ids[s]))
})

test('H2 grid: pile rows and resize', () => {
    const { m, a } = pileTree()
    const cache = new GridLineCache()
    const rows = gridRows(m, cache)
    const pileRows = rows.filter(r => r.type === 'pile') as PileRowLine[]
    assert.equal(pileRows.length, 9)
    assert.deepEqual(pileRows[0].data, { groupId: a.id, pileIndex: 0, slots: [0, 1] })
    m.closeGroup(a.id)
    gridRows(m, cache)
    cache.resize(104)
    m.openGroup(a.id)
    const resized = gridRows(m, cache, 104)
    assert.ok(resized.every(r => r.size === 104))
    resized.forEach((r, i) => assert.equal(r, rows[i], 'resized in place, not rebuilt'))
    // The overlay recomputed to an equal pile (new object): rows still match, so they are kept.
    m.applySha1Piles()
    m.buildOrdinalRanges()
    gridRows(m, cache, 104).forEach((r, i) => assert.equal(r, rows[i]))
})

test('H2 grid: re-rowed leaves start at their measured heights; resize spares the rows on screen', async () => {
    const m = await flatTree()
    const cache = new GridLineCache()
    const ids = columnStub.instanceIds()
    // Heights measured per image (GridScroller's map): rows are re-made after a sort, and keep them.
    const heights = new Map<number, number>()
    const measured: MeasuredHeight = id => heights.get(id)
    const rows = gridRows(m, cache, 28, measured)
    assert.ok(rows.every(r => r.size === 28), 'nothing measured yet: the estimate')
    rows[0].size = 90
    heights.set(rowInstanceId(rows[0], ids)!, 90)
    const two = leafFor(m, 2)!
    const twoFirst = rows.find(r => r.groupId === two.id)!
    twoFirst.size = 50
    heights.set(rowInstanceId(twoFirst, ids)!, 50)

    // Leaf 2 re-rowed (new row objects): its measured row keeps its height through the map.
    two.slots.reverse()
    m.buildOrdinalRanges()
    const after = gridRows(m, cache, 28, measured)
    const remade = after.find(r => r.groupId === two.id && rowInstanceId(r, ids) === rowInstanceId(twoFirst, ids))!
    assert.notEqual(remade, twoFirst)
    assert.equal(remade.size, 50)
    assert.ok(after.filter(r => r.groupId === two.id && r !== remade).every(r => r.size === 28))

    // Columns changed: back to the estimate, except the rows on screen (they measure themselves).
    const onScreen = new Set([after[0]])
    assert.equal(cache.resize(28, onScreen), true)
    assert.equal(after[0].size, 90, 'kept')
    assert.equal(remade.size, 28, 'reset')
    assert.equal(cache.resize(28, onScreen), false, 'nothing left to reset')
})

test('H2 grid: a pile row is measured as its first image', () => {
    const { m } = pileTree()
    const ids = columnStub.instanceIds()
    const pile = gridRows(m, new GridLineCache()).find(r => r.type === 'pile') as PileRowLine
    assert.equal(rowInstanceId(pile, ids), ids[pile.data.slots[0]])
    const heights = new Map([[ids[pile.data.slots[0]], 77]])
    const again = gridRows(m, new GridLineCache(), 28, id => heights.get(id)).find(r => r.id === pile.id)!
    assert.equal(again.size, 77)
    assert.equal(rowInstanceId({ id: 'g', type: 'group', size: 35 }, ids), undefined)
})
