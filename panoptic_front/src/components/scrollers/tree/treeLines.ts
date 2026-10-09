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
 * Since a line holds no image, a leaf's block of lines depends only on how many positions the
 * leaf has, whether it is piled, its depth, and the sizes — see LeafKey. TreeLineCache keeps
 * each leaf's block under that key, so a rebuild walks the groups and reuses the blocks of every
 * leaf whose key did not change: O(groups) plus the concatenation, whatever the image count.
 *
 * Pure on purpose (no Vue, no stores): the scroller adapts it, and the tests drive it over a
 * real GroupManager.
 */
import type { InjectionKey, Ref } from 'vue'
import type { Group, GroupIndex } from '@/core/group/types'
import type { PileData } from '@/core/sha1Piles'
import type { ImageIterator } from '@/core/group/GroupIterator'
import type { ImageLine } from '../types'

// What the lines are read against: the GroupResult (the iterator host of every manager).
export interface LineHost {
    readonly index: GroupIndex
    readonly pileIndex: Map<number, PileData>
    readonly rev: number
    getImageIterator(groupId?: number, imageIdx?: number): ImageIterator
}

// Bumped by the scroller every time it hands out a new line list. The line components read it in
// the computed that makes their iterators: a line object is kept across rebuilds while its range
// is unchanged (see TreeLineCache), but the images at that range may not be — the tree is mutated
// in place — so the iterators are re-checked after each rebuild, not only when `item` changes.
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

// Everything a leaf's block of lines is a function of. Nothing about WHICH images the leaf holds:
// the lines only carry ranges, so two leaves with the same key get identical lines.
export interface LeafKey {
    positions: number
    piled: boolean
    depth: number
    // Usable line width once the leaf's indent is taken off.
    width: number
    imageSize: number
    // Properties drawn under each card: all visible ones on image lines, the sha1 ones on piles.
    propertyCount: number
}

export function sameKey(a: LeafKey, b: LeafKey): boolean {
    return a.positions === b.positions && a.piled === b.piled && a.depth === b.depth
        && a.width === b.width && a.imageSize === b.imageSize && a.propertyCount === b.propertyCount
}

// Two lines that draw the same range at the same geometry render the same DOM: the previous
// object is kept so its `:item` stays the same reference and the line is not re-rendered.
function sameRangeLine(a: ImageLine, b: ImageLine): boolean {
    if (!a || a.type !== b.type || a.groupId !== b.groupId || a.start !== b.start || a.count !== b.count) return false
    if (a.size !== b.size || a.depth !== b.depth || a.imageSize !== b.imageSize || a.emptyCount !== b.emptyCount) return false
    const aw = a.cardWidths, bw = b.cardWidths
    if (aw === bw) return true
    if (aw.length !== bw.length) return false
    for (let i = 0; i < aw.length; i++) if (aw[i] !== bw[i]) return false
    return true
}

// The lines of leaf `groupId` under `key`. `previous` is the leaf's last block: lines that come
// out the same are taken from it (by index — a leaf's line k is always its positions
// [k * perLine, ...)), so a leaf that only grew at its end keeps the objects of its first lines.
export function buildLeafLines(groupId: number, key: LeafKey, imageSize: number, previous?: ImageLine[]): ImageLine[] {
    const lines: ImageLine[] = []
    // Empty leaf: no images, so emit no image line (avoids a blank/spinner row).
    if (key.positions <= 0) return lines

    // imageSize only decides how many images fit in a line...
    const itemsPerLine = Math.max(1, Math.floor(key.width / (imageSize + BORDER + GAP)))
    // ...then images are stretched to exactly fill a FULL line. Every line uses these same
    // widths — a trailing/partial line (end of group, small group) keeps them too instead of
    // blowing its images up to fill the leftover space; the empty slots are simulated
    // (reserved, not rendered) so alignment across lines stays consistent.
    const { lineImgSize, cardWidths } = fillWidths(key.width, itemsPerLine)
    const type = key.piled ? 'piles' : 'images'
    const prefix = groupId + (key.piled ? '|pile-' : '|img-')
    const size = cardLineSize(lineImgSize, key.propertyCount)

    for (let k = 0, start = 0; start < key.positions; k++, start += itemsPerLine) {
        const count = Math.min(itemsPerLine, key.positions - start)
        const line: ImageLine = {
            id: prefix + k,
            type,
            groupId,
            start,
            count,
            depth: key.depth + 1,
            imageSize: lineImgSize,
            emptyCount: itemsPerLine - count,
            cardWidths,
            size,
        }
        const old = previous?.[k]
        lines.push(old && sameRangeLine(old, line) ? old : line)
    }
    return lines
}

interface LeafBlock {
    key: LeafKey
    lines: ImageLine[]
}

export interface TreeLineParams {
    // Content width of the scroller, before any indent.
    contentWidth: number
    imageSize: number
    propertyCount: number
    pilePropertyCount: number
}

const NO_LINES: ImageLine[] = []

/**
 * The image/pile lines of every leaf, kept between rebuilds.
 *
 * Invariant: a cached block is returned only when the leaf's current LeafKey equals the one it was
 * built under, and a block is a pure function of (group id, LeafKey). Every input is read off the
 * leaf at each call, in O(1), so no change signal from the tree is needed — and none would be
 * reliable: groups are mutated in place (ClusterManager.drain filters `slots`, the overlay
 * refills a pile's `slots` array without replacing it), and open/close bumps `version` without
 * touching any group's content. What the lines do NOT capture — which images sit at each
 * position — is read live by the line components (lineIterators) and the scroller (lineFirstSlots).
 *
 * Line sizes are part of the key (propertyCount) but are also changed in place by `resize`, which
 * the scroller calls instead of rebuilding when the visible properties change: all cached blocks
 * are resized, not only the drawn ones, so the block of a closed group is right when it reopens.
 */
export class TreeLineCache {
    private blocks = new Map<number, LeafBlock>()
    private host: LineHost | undefined

    // The lines leaf `group` draws (an empty list when it draws none). `group` must be an open
    // leaf; the caller decides that, since closing does not change the block itself.
    leafLines(host: LineHost, group: Group, params: TreeLineParams): ImageLine[] {
        if (host !== this.host) {
            this.blocks.clear()
            this.host = host
        }
        if (!group.slots || group.slots.length === 0) return NO_LINES
        const piled = host.pileIndex.has(group.id)
        const key: LeafKey = {
            positions: positionCount(host, group),
            piled,
            depth: group.depth,
            // An image line draws depth + 1 indent columns (the ancestors and the group itself,
            // see getImageLineParents), so that many are reserved, not `depth`.
            width: params.contentWidth - (group.depth + 1) * MARGIN_STEP,
            imageSize: params.imageSize,
            propertyCount: piled ? params.pilePropertyCount : params.propertyCount,
        }
        const block = this.blocks.get(group.id)
        if (block && sameKey(block.key, key)) return block.lines
        const lines = buildLeafLines(group.id, key, params.imageSize, block?.lines)
        this.blocks.set(group.id, { key, lines })
        return lines
    }

    // The visible properties changed: resize every cached line in place (line objects kept, so
    // nothing is re-created) and restamp the blocks with the new counts.
    resize(propertyCount: number, pilePropertyCount: number) {
        for (const block of this.blocks.values()) {
            const n = block.key.piled ? pilePropertyCount : propertyCount
            if (block.key.propertyCount === n) continue
            block.key = { ...block.key, propertyCount: n }
            for (const line of block.lines) line.size = cardLineSize(line.imageSize, n)
        }
    }

    // Drop the blocks of groups the tree no longer holds. O(cached leaves).
    prune(host: LineHost) {
        if (host !== this.host) return
        for (const id of this.blocks.keys()) {
            if (!host.index[id]) this.blocks.delete(id)
        }
    }

    clear() {
        this.blocks.clear()
        this.host = undefined
    }

    get size() {
        return this.blocks.size
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
