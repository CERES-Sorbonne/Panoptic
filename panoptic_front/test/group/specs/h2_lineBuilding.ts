/**
 * H2 — scroller lines are made for the lines on screen only, from the tree itself.
 *
 * Tree: the tree is the layout (treeSource: a leaf's line count is a division), and an image/pile
 * line is a range of its leaf (`groupId`, `start`, `count`), made on demand (leafLine). The
 * iterators the line components make for a range must be exactly the ones the old per-image walk
 * produced, and the lines must come in the order the old group walk gave.
 *
 * Grid: one row per image (or pile) of every open leaf (gridSource), made on demand (gridRow) and
 * handed back while it still shows the same image.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { GroupManager } from '@/core/GroupManager'
import { Group } from '@/core/group/types'
import { GroupIterator, ImageIterator } from '@/core/group/GroupIterator'
import {
    BORDER, GAP, MARGIN_STEP, TreeGeometry, TreeLineParams, cardLineSize, leafLine, leafLineCount,
    lineFirstSlots, lineIterators, lineSlot, treeCellWalk, treeSource,
} from '@/components/scrollers/tree/treeLines'
import { gridCellWalk, gridRow, gridSource, rowInstanceId } from '@/components/scrollers/grid/gridLines'
import { ImageLine, PileRowLine, RowLine, ScrollerLine } from '@/components/scrollers/types'
import { adjacentCellIn } from '@/components/scrollers/cellNavigation'
import { HEADER, LineRef, ScrollLayout } from '@/components/scrollers/virtual/scrollLayout'
import { columnStub } from '../harness/stubs/columnStore'
import { groupedBy, handTree, leafFor } from '../harness/world'

const params = (over: Partial<TreeLineParams> = {}): TreeLineParams =>
    ({ contentWidth: 400, imageSize: 100, propertyCount: 2, pilePropertyCount: 1, ...over })

function treeLayout(m: GroupManager, p = params()) {
    const geometry = new TreeGeometry(p)
    const layout = new ScrollLayout(treeSource(() => m.result, geometry, () => false))
    layout.rebuild()
    return { geometry, layout }
}

/** Every line of the layout in display order. */
function allRefs(layout: ScrollLayout): LineRef[] {
    const out: LineRef[] = []
    for (let l = layout.locate(0); l; l = layout.next(l)) out.push({ node: l.node, index: l.index })
    return out
}

/** TreeScroller's lines, minus Vue: the layout walked top to bottom, each line made on demand. */
function treeLines(m: GroupManager, p = params()): ScrollerLine[] {
    const { geometry, layout } = treeLayout(m, p)
    return allRefs(layout).map(ref => ref.index < 0
        ? { id: ref.node, type: 'group', data: m.result.index[ref.node], size: 30 }
        : leafLine(m.result, ref.node, ref.index, geometry)!)
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

test('H2: the layout walks the groups in the order the group iterator did', async () => {
    const m = await flatTree()
    const two = leafFor(m, 2)!
    m.closeGroup(two.id, true)
    // The old computeLines: every group the iterator visits, then an open leaf's lines.
    const legacy: string[] = []
    let it: GroupIterator | undefined = m.getGroupIterator()
    while (it) {
        legacy.push('g' + it.group.id)
        if (!it.group.children.length && !it.group.view.closed) legacy.push('l' + it.group.id)
        it = it.nextGroup()
    }
    const lines = treeLines(m)
    const got: string[] = []
    for (const l of lines) {
        const tag = (l.type === 'group' ? 'g' : 'l') + (l.type === 'group' ? l.id : l.groupId)
        if (got[got.length - 1] !== tag) got.push(tag)
    }
    assert.deepEqual(got, legacy)
    assert.ok(lines.every(l => l.type === 'group' || l.groupId !== two.id), 'a closed leaf draws no line')
})

test('H2: flat range lines give the very iterators the per-image walk gave', async () => {
    const m = await flatTree()
    const lines = treeLines(m)
    assert.equal(assertMatchesLegacy(m, lines, 'flat'), 18, 'every image is on a line')
})

test('H2: piled range lines give the per-pile iterators (slots = the whole pile)', () => {
    const { m, a, b } = pileTree()
    assert.ok(m.result.pileIndex.has(a.id as number) && m.result.pileIndex.has(b.id as number), 'the fixture piles')
    const lines = treeLines(m)
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
    const geometry = new TreeGeometry(p)
    const n = leafLineCount(m.result, leaf, geometry)
    const lines = Array.from({ length: n }, (_, k) => leafLine(m.result, leaf.id, k, geometry)!)
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
    // The layout sizes the lines as they are drawn.
    const { layout } = treeLayout(m, p)
    assert.equal(layout.bodyLines(leaf.id), n)
    assert.equal(layout.sizeOf({ node: leaf.id, index: 0 }), lines[0].size)
    assert.equal(layout.sizeOf({ node: leaf.id, index: HEADER }), 30)
})

test('H2: a line that comes out the same is the same object; another geometry is not', async () => {
    const m = await flatTree()
    const leaf = leafFor(m, 1)!
    const geometry = new TreeGeometry(params())
    const first = leafLine(m.result, leaf.id, 0, geometry)!
    assert.equal(leafLine(m.result, leaf.id, 0, geometry, first), first)
    // The leaf grows at its end: its first full line is unchanged, its last partial one is not.
    const n = leafLineCount(m.result, leaf, geometry)
    const last = leafLine(m.result, leaf.id, n - 1, geometry)!
    leaf.slots.push(leaf.slots[0])
    assert.equal(leafLine(m.result, leaf.id, 0, geometry, first), first)
    assert.notEqual(leafLine(m.result, leaf.id, n - 1, geometry, last), last)
    leaf.slots.pop()
    // Wider: every line changes.
    assert.equal(geometry.setParams(params({ contentWidth: 900 })), true)
    assert.notEqual(leafLine(m.result, leaf.id, 0, geometry, first), first)
    assert.equal(geometry.setParams(params({ contentWidth: 900 })), false, 'same params, nothing to redo')
})

test('H2: more properties only make the lines taller; the layout follows on refresh', async () => {
    const m = await flatTree()
    const { geometry, layout } = treeLayout(m)
    const leaf = leafFor(m, 1)!
    const lines = layout.bodyLines(leaf.id)
    const height = layout.height
    geometry.setParams(params({ propertyCount: 5 }))
    layout.refresh()
    assert.equal(layout.bodyLines(leaf.id), lines, 'as many lines: no line is given another range')
    const line = leafLine(m.result, leaf.id, 0, geometry)!
    assert.equal(line.size, cardLineSize(line.imageSize, 5))
    assert.equal(layout.sizeOf({ node: leaf.id, index: 0 }), line.size)
    assert.ok(layout.height > height)
})

test('H2: opening and closing a group updates the layout without a rebuild', async () => {
    const m = await flatTree()
    const { layout } = treeLayout(m)
    const before = allRefs(layout)
    const two = leafFor(m, 2)!
    m.closeGroup(two.id, true)
    layout.refreshNode(two.id)
    assert.deepEqual(allRefs(layout), before.filter(r => r.node !== two.id || r.index < 0))
    m.openGroup(two.id, true)
    layout.refreshNode(two.id)
    assert.deepEqual(allRefs(layout), before)
})

test('H2: lineIterators keeps the previous array only while it still describes the tree', async () => {
    const m = await flatTree()
    const leaf = leafFor(m, 1)!
    const line = leafLine(m.result, leaf.id, 0, new TreeGeometry(params()))!
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
    const geometry = new TreeGeometry(params())
    const last = leafLine(m.result, leaf.id, leafLineCount(m.result, leaf, geometry) - 1, geometry)!
    leaf.slots.length = last.start + 1
    m.buildOrdinalRanges()
    assert.equal(lineIterators(m.result, last).length, 1)
    assert.equal(lineFirstSlots(m.result, last).length, 1)
    assert.equal(lineSlot(m.result, last, 1), undefined)
    delete m.result.index[leaf.id]
    assert.equal(lineIterators(m.result, last).length, 0)
    assert.deepEqual(lineFirstSlots(m.result, last), [])
    assert.equal(leafLine(m.result, leaf.id, 0, geometry), undefined, 'no line for a group that is gone')
})

test('H2: an empty leaf draws no line', async () => {
    const m = await flatTree()
    const leaf = leafFor(m, 3)!
    leaf.slots.length = 0
    const { layout } = treeLayout(m)
    assert.equal(layout.bodyLines(leaf.id), 0)
})

test('H2: Tab walks the range lines like it walked the iterator lines', async () => {
    const m = await flatTree()
    const { geometry, layout } = treeLayout(m)
    const ids = columnStub.instanceIds()
    const walk = treeCellWalk(m.result, layout, geometry, ids, false)
    const one = leafFor(m, 1)!, two = leafFor(m, 2)!
    const last = { instanceId: ids[one.slots[one.slots.length - 1]], groupId: one.id }
    assert.deepEqual(adjacentCellIn(walk, last, false)?.cell, { instanceId: ids[two.slots[0]], groupId: two.id })
    assert.deepEqual(adjacentCellIn(walk, { instanceId: ids[two.slots[0]], groupId: two.id }, true)?.cell, last)
    // Within a line.
    const second = adjacentCellIn(walk, { instanceId: ids[one.slots[0]], groupId: one.id }, false)!
    assert.deepEqual(second.cell, { instanceId: ids[one.slots[1]], groupId: one.id })
    // A closed group's cells are not drawn: not found.
    m.closeGroup(one.id, true)
    layout.refreshNode(one.id)
    assert.equal(adjacentCellIn(walk, last, false), undefined)
})

// ── grid ─────────────────────────────────────────────────────────────────────

function gridLayout(m: GroupManager, size = 28) {
    const layout = new ScrollLayout(gridSource(() => m.result, () => size))
    layout.rebuild()
    return layout
}

/** GridScroller's lines, minus Vue. */
function gridLines(m: GroupManager, layout = gridLayout(m)) {
    const ids = columnStub.instanceIds()
    return allRefs(layout).map(ref => ref.index < 0 ? { header: ref.node } : gridRow(m.result, ids, ref)!)
}

test('H2 grid: one header per leaf (not the root) and one row per image, inner groups draw nothing', async () => {
    const m = await flatTree()
    const ids = columnStub.instanceIds()
    const lines = gridLines(m)
    const rows = lines.filter(l => !('header' in l)) as RowLine[]
    assert.equal(rows.length, 18)
    const one = leafFor(m, 1)!
    assert.deepEqual(lines[0], { header: one.id })
    const r0 = rows[0]
    assert.equal(r0.id, one.id + '-img:' + ids[one.slots[0]])
    assert.deepEqual([r0.type, r0.groupId, r0.index, r0.data.id], ['image', one.id, 0, ids[one.slots[0]]])
    assert.equal(lines.filter(l => 'header' in l).length, 3)
    m.closeGroup(one.id, true)
    const layout = gridLayout(m)
    assert.equal(gridLines(m, layout).filter(l => !('header' in l)).length, 8, 'a closed leaf keeps its header only')
    // Closing the root (an inner group) hides everything.
    m.closeGroup(m.result.root.id, true)
    layout.refreshNode(m.result.root.id)
    assert.equal(layout.height, 0)
})

test('H2 grid: a row is handed back while it shows the same image', async () => {
    const m = await flatTree()
    const ids = columnStub.instanceIds()
    const two = leafFor(m, 2)!
    const ref = { node: two.id, index: 0 }
    const row = gridRow(m.result, ids, ref)!
    assert.equal(gridRow(m.result, ids, ref, row), row)
    two.slots.reverse()
    m.buildOrdinalRanges()
    const after = gridRow(m.result, ids, ref, row) as RowLine
    assert.notEqual(after, row)
    assert.equal(after.data.id, ids[two.slots[0]])
    assert.equal(gridRow(m.result, ids, { node: two.id, index: two.slots.length }), undefined)
})

test('H2 grid: pile rows, and a pile row is edited as its first image', () => {
    const { m, a } = pileTree()
    const ids = columnStub.instanceIds()
    const rows = gridLines(m).filter(l => !('header' in l)) as (RowLine | PileRowLine)[]
    const pileRows = rows.filter(r => r.type === 'pile') as PileRowLine[]
    assert.equal(pileRows.length, 9)
    assert.deepEqual(pileRows[0].data, { groupId: a.id, pileIndex: 0, slots: [0, 1] })
    assert.equal(rowInstanceId(pileRows[0], ids), ids[0])
    // The overlay recomputed to an equal pile (new object): the row still matches, so it is kept.
    m.applySha1Piles()
    m.buildOrdinalRanges()
    assert.equal(gridRow(m.result, ids, { node: a.id as number, index: 0 }, pileRows[0]), pileRows[0])
})

test('H2 grid: Tab goes row to row, across leaves', async () => {
    const m = await flatTree()
    const ids = columnStub.instanceIds()
    const layout = gridLayout(m)
    const walk = gridCellWalk(m.result, layout, ids)
    const one = leafFor(m, 1)!, two = leafFor(m, 2)!
    const last = { instanceId: ids[one.slots[one.slots.length - 1]], groupId: one.id }
    assert.deepEqual(adjacentCellIn(walk, last, false)?.cell, { instanceId: ids[two.slots[0]], groupId: two.id })
    assert.deepEqual(adjacentCellIn(walk, { instanceId: ids[one.slots[0]], groupId: one.id }, false)?.cell,
        { instanceId: ids[one.slots[1]], groupId: one.id })
})
