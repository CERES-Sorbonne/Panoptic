/**
 * Image and pile lines of the tree scroller, as ranges.
 *
 * A line used to carry the ImageIterator of every image it draws, so building the lines walked
 * every image of the tree and allocated an iterator (plus its `slots` array) per image — on every
 * group open/close, resize or result change. A line now only says which positions of which leaf
 * it draws (`groupId`, `start`, `count`: slot indices in a flat leaf, pile indices in a piled
 * one). Iterators are made by the line component for the lines on screen (lineIterators), and
 * the instance ids of a line are read straight off the leaf (lineFirstSlots).
 *
 * Since a line holds no image, a leaf's lines depend only on how many positions the leaf has,
 * whether it is piled, its depth and the sizes (TreeGeometry, per depth). So the tree is handed to
 * the VirtualScroller as a LayoutSource (treeSource) — a group's line count is a division — and a
 * line object is only made for the lines on screen (leafLine).
 *
 * Pure on purpose (no Vue, no stores): the scroller adapts it, and the tests drive it over a
 * real GroupManager.
 */
import type { InjectionKey, Ref } from 'vue'
import type { Group, GroupIndex } from '@/core/group/types'
import type { PileData } from '@/core/sha1Piles'
import type { ImageIterator } from '@/core/group/GroupIterator'
import type { ImageLine } from '../types'
import type { LayoutSource, LineRef, ScrollLayout } from '../virtual/scrollLayout'
import type { CellWalk } from '../cellNavigation'

// What the lines are read against: the GroupResult (the iterator host of every manager).
export interface LineHost {
    readonly index: GroupIndex
    readonly pileIndex: Map<number, PileData>
    readonly rev: number
    getImageIterator(groupId?: number, imageIdx?: number): ImageIterator
}

// Bumped by the scroller every time the tree is read again. The line components read it in the
// computed that makes their iterators: a line object is kept across rebuilds while its range is
// unchanged (see leafLine), but the images at that range may not be — the tree is mutated in
// place — so the iterators are re-checked after each rebuild, not only when `item` changes.
export const treeLinesBuiltKey: InjectionKey<Ref<number>> = Symbol('treeLinesBuilt')

// One indent column as ImageLine/PileLine actually render it: .ps-2 (8) + .image-line's
// border-left (1) + its padding-left (10). Must match that CSS or the lines overflow.
export const MARGIN_STEP = 19
export const GAP = 8 // must match the "me-2" margin applied to Image/PileLine cells
export const BORDER = 2 // Image.vue's .full-container 1px border on each side, added on top of its width style

// Row height of a card line: the image plus one row per property drawn under it (the first one
// taller), plus the line's bottom margin. Depends on the image size actually rendered on that
// line, not on the imageSize prop (see fillWidths).
export function cardLineSize(imgSize: number, propertyCount: number): number {
    let offset = 0
    if (propertyCount > 0) offset += 28
    if (propertyCount > 1) offset += (propertyCount - 1) * 26
    return imgSize + offset + 6
}

// Per-cell widths that exactly fill a line: flooring the cell size leaves up to
// (itemsPerLine - 1) leftover px at the line end, so hand those out 1px at a time to the
// leading columns. The distribution depends only on lineWidth/itemsPerLine (constant across
// a group's lines), so grid columns stay aligned line-to-line and the line comps do no math.
export function fillWidths(lineWidth: number, itemsPerLine: number): { lineImgSize: number, cardWidths: number[] } {
    const cardArea = lineWidth - GAP * (itemsPerLine - 1) // px available for cell OUTER widths
    const baseOuter = Math.floor(cardArea / itemsPerLine)
    const extraCount = cardArea - baseOuter * itemsPerLine
    const lineImgSize = Math.max(1, baseOuter - BORDER)
    const cardWidths: number[] = []
    for (let c = 0; c < itemsPerLine; c++) cardWidths.push(lineImgSize + (c < extraCount ? 1 : 0))
    return { lineImgSize, cardWidths }
}

// Number of image positions a leaf draws: one per pile when piled, one per slot otherwise. The
// same count ImageIterator walks (its positionCount).
export function positionCount(host: LineHost, group: Group): number {
    const pile = host.pileIndex.get(group.id)
    return pile ? pile.bounds.length - 1 : group.slots.length
}

// The geometry shared by every line of the leaves at one depth (and pile state): how many images a
// line holds, their widths, the line's height.
export interface LeafGeometry {
    perLine: number
    lineImgSize: number
    cardWidths: number[]
    size: number
}

export interface TreeLineParams {
    // Content width of the scroller, before any indent.
    contentWidth: number
    imageSize: number
    propertyCount: number
    pilePropertyCount: number
}

const sameParams = (a: TreeLineParams, b: TreeLineParams) => a.contentWidth === b.contentWidth
    && a.imageSize === b.imageSize && a.propertyCount === b.propertyCount && a.pilePropertyCount === b.pilePropertyCount

/**
 * Line geometry per depth: a leaf's lines depend only on its indent (depth), whether it is piled,
 * and the params — so it is computed once per (depth, piled), not per leaf or line.
 */
export class TreeGeometry {
    private cache = new Map<number, LeafGeometry>()

    constructor(private params: TreeLineParams) { }

    // Whether anything changed.
    setParams(params: TreeLineParams): boolean {
        if (sameParams(params, this.params)) return false
        this.params = { ...params }
        this.cache.clear()
        return true
    }

    get(depth: number, piled: boolean): LeafGeometry {
        const k = depth * 2 + (piled ? 1 : 0)
        let g = this.cache.get(k)
        if (g) return g
        const p = this.params
        // An image line draws depth + 1 indent columns (the ancestors and the group itself, see
        // TreeScroller's imageLineParents), so that many are reserved, not `depth`.
        const width = p.contentWidth - (depth + 1) * MARGIN_STEP
        // imageSize only decides how many images fit in a line...
        const perLine = Math.max(1, Math.floor(width / (p.imageSize + BORDER + GAP)))
        // ...then images are stretched to exactly fill a FULL line. Every line uses these same
        // widths — a trailing/partial line (end of group, small group) keeps them too instead of
        // blowing its images up to fill the leftover space; the empty slots are simulated
        // (reserved, not rendered) so alignment across lines stays consistent.
        const { lineImgSize, cardWidths } = fillWidths(width, perLine)
        const size = cardLineSize(lineImgSize, piled ? p.pilePropertyCount : p.propertyCount)
        this.cache.set(k, g = { perLine, lineImgSize, cardWidths, size })
        return g
    }
}

// Two lines that draw the same range at the same geometry render the same DOM: the previous
// object is kept so its `:item` stays the same reference and the line is not re-rendered.
export function sameRangeLine(a: ImageLine | undefined, b: ImageLine): boolean {
    if (!a || a.type !== b.type || a.groupId !== b.groupId || a.start !== b.start || a.count !== b.count) return false
    if (a.size !== b.size || a.depth !== b.depth || a.imageSize !== b.imageSize || a.emptyCount !== b.emptyCount) return false
    const aw = a.cardWidths, bw = b.cardWidths
    if (aw === bw) return true
    if (aw.length !== bw.length) return false
    for (let i = 0; i < aw.length; i++) if (aw[i] !== bw[i]) return false
    return true
}

// Lines of a leaf's body: none for a leaf without images.
export function leafLineCount(host: LineHost, group: Group, geometry: TreeGeometry): number {
    if (!group.slots?.length) return 0
    const geo = geometry.get(group.depth, host.pileIndex.has(group.id))
    return Math.ceil(positionCount(host, group) / geo.perLine)
}

/**
 * Line `index` of leaf `groupId`: positions [index * perLine, ...) — slot indices in a flat leaf,
 * pile indices in a piled one. `previous` is handed back when the line comes out the same.
 * Undefined when the group is no longer a leaf of the tree.
 */
export function leafLine(host: LineHost, groupId: number, index: number, geometry: TreeGeometry, previous?: ImageLine): ImageLine | undefined {
    const group = host.index[groupId]
    if (!group || group.children.length) return undefined
    const piled = host.pileIndex.has(groupId)
    const geo = geometry.get(group.depth, piled)
    const start = index * geo.perLine
    const count = Math.max(0, Math.min(geo.perLine, positionCount(host, group) - start))
    const line: ImageLine = {
        id: groupId + (piled ? '|pile-' : '|img-') + index,
        type: piled ? 'piles' : 'images',
        groupId,
        start,
        count,
        depth: group.depth + 1,
        imageSize: geo.lineImgSize,
        emptyCount: geo.perLine - count,
        cardWidths: geo.cardWidths,
        size: geo.size,
    }
    return sameRangeLine(previous, line) ? previous! : line
}

// Height of a group line.
export const GROUP_LINE_SIZE = 30

// What the tree scroller's layout reads: the manager's GroupResult.
export interface TreeHost extends LineHost {
    readonly root?: Group
}

/**
 * The tree as a LayoutSource: every group has a header line (none with `hideGroup`), an open leaf
 * has its image (or pile) lines. Each answer is O(1); nothing is built per line.
 */
export function treeSource(host: () => TreeHost, geometry: TreeGeometry, hideGroup: () => boolean): LayoutSource {
    const group = (id: number) => host().index[id]
    return {
        root: () => host().root?.id,
        childCount: id => group(id)?.children.length ?? 0,
        child: (id, i) => group(id).children[i].id,
        isOpen: id => !group(id)?.view.closed,
        headerSize: () => hideGroup() ? 0 : GROUP_LINE_SIZE,
        bodyLines: id => {
            const g = group(id)
            return !g || g.children.length ? 0 : leafLineCount(host(), g, geometry)
        },
        lineEstimate: id => {
            const g = group(id)
            return g ? geometry.get(g.depth, host().pileIndex.has(id)).size : 1
        },
        lineType: (id, index) => index < 0 ? 'group' : host().pileIndex.has(id) ? 'piles' : 'images',
    }
}

// The leaf a line draws, while it still is one: a line can outlive its group for the 50ms
// between a result change and the rebuild it triggers.
function lineLeaf(host: LineHost, line: ImageLine): Group | undefined {
    const group = host.index[line.groupId]
    if (!group || group.children.length) return undefined
    return group
}

// How many of the line's positions the leaf still has (all of them, once lines are rebuilt).
function liveCount(host: LineHost, line: ImageLine, group: Group | undefined): number {
    if (!group) return 0
    return Math.max(0, Math.min(line.count, positionCount(host, group) - line.start))
}

// The first slot of each position of the line (the slot itself in a flat leaf, the pile's first
// slot in a piled one) — what an ImageIterator's `slot` would be, without making one.
export function lineFirstSlots(host: LineHost, line: ImageLine, out: number[] = []): number[] {
    const group = lineLeaf(host, line)
    const n = liveCount(host, line, group)
    if (!n) return out
    const pile = host.pileIndex.get(line.groupId)
    if (pile) {
        for (let i = 0; i < n; i++) out.push(pile.order[pile.bounds[line.start + i]])
    } else {
        const slots = group!.slots
        for (let i = 0; i < n; i++) out.push(slots[line.start + i])
    }
    return out
}

// Slot of the line's `i`-th position, as lineFirstSlots gives it; undefined past the leaf's end.
export function lineSlot(host: LineHost, line: ImageLine, i: number): number | undefined {
    const group = lineLeaf(host, line)
    if (i < 0 || i >= liveCount(host, line, group)) return undefined
    const pile = host.pileIndex.get(line.groupId)
    return pile ? pile.order[pile.bounds[line.start + i]] : group!.slots[line.start + i]
}

// The iterators of the images the line draws: the same ones the old per-image walk made
// (`new ImageIterator(host, groupId, position)`, default options). Hands back `previous` when it
// still describes exactly these positions of the current tree (`isCurrent` checks the group node
// and the slots at each position), so a line whose images did not change keeps the same array —
// and its cards the same `image` prop — across rebuilds.
export function lineIterators(host: LineHost, line: ImageLine, previous?: ImageIterator[]): ImageIterator[] {
    const n = liveCount(host, line, lineLeaf(host, line))
    if (previous && previous.length === n) {
        let same = true
        for (let i = 0; i < n && same; i++) {
            const it = previous[i]
            // The host too: after a manager swap the old tree's iterators are still "current"
            // against their own (unchanged) host.
            same = (it['manager'] as unknown) === host && it.groupId === line.groupId && it.imageIdx === line.start + i && it.isCurrent
        }
        if (same) return previous
    }
    const out: ImageIterator[] = new Array(n)
    for (let i = 0; i < n; i++) out[i] = host.getImageIterator(line.groupId, line.start + i)
    return out
}

/**
 * The cells of one property in display order, for Tab: every image of an image line, and every pile
 * of a pile line when the property is one the piles show (`onPiles`). A cell is found in its own
 * leaf (a pile by its first image, the one its card edits), never by scanning the whole tree.
 */
export function treeCellWalk(host: LineHost, layout: ScrollLayout, geometry: TreeGeometry, ids: ArrayLike<number>, onPiles: boolean): CellWalk<LineRef> {
    const lineOf = (line: LineRef) => line.index >= 0 ? leafLine(host, line.node, line.index, geometry) : undefined
    return {
        find: from => {
            const group = host.index[from.groupId]
            if (!group || group.children.length) return undefined
            const pile = host.pileIndex.get(group.id)
            if (pile && !onPiles) return undefined
            const n = positionCount(host, group)
            for (let pos = 0; pos < n; pos++) {
                const slot = pile ? pile.order[pile.bounds[pos]] : group.slots[pos]
                if (ids[slot] !== from.instanceId) continue
                const perLine = geometry.get(group.depth, !!pile).perLine
                const line = { node: group.id, index: Math.floor(pos / perLine) }
                return layout.isShown(line) ? { line, index: pos % perLine } : undefined
            }
            return undefined
        },
        cells: line => {
            const item = lineOf(line)
            if (!item || (item.type === 'piles' && !onPiles)) return 0
            return item.count
        },
        at: (line, i) => ({ instanceId: ids[lineSlot(host, lineOf(line)!, i)!], groupId: line.node }),
        next: line => layout.next(line),
        prev: line => layout.prev(line),
    }
}
