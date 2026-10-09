/**
 * Row lines of the grid scroller, kept per leaf between rebuilds.
 *
 * The grid draws one row per image (or per sha1 pile), and each row names its image: unlike the
 * tree's range lines, a block of rows is a function of the leaf's CONTENT. Every version bump
 * used to rebuild one row object (and one id string) per image of the whole tree — a group
 * open/close included, which changes no content at all.
 *
 * Invariant: a leaf's cached block is handed back only when it still matches the leaf —
 *  - fast path, O(1): nothing structural happened since it was built (the host's `rev` is the
 *    same — every tree/order change bumps it, open/close does not), the leaf is the same node with
 *    the same `slots` array and length, the same pile overlay, and the row size is the same;
 *  - otherwise its rows are compared with the leaf, O(rows) integer compares and no allocation:
 *    groups are mutated in place (ClusterManager.drain filters `slots`, the overlay refills a
 *    pile's `slots` without replacing the array), so identity alone cannot say "unchanged". A
 *    block that still matches is restamped and reused, so a change to one bucket re-rows that
 *    bucket only.
 * Rows fit their content (see rowHeights.ts), so a row's size is its measured height once it has
 * been on screen, and the row size handed in is only the estimate for the rows never measured.
 * Measured heights are looked up per image (a pile row by its first image) when rows are made,
 * so a re-rowed leaf keeps them. `resize` sets every cached row back to an estimate, in place.
 *
 * Pure on purpose (no Vue, no stores): the scroller adapts it, and the tests drive it.
 */
import type { Group, GroupIndex } from '@/core/group/types'
import type { PileData } from '@/core/sha1Piles'
import type { PileRowLine, RowLine, ScrollerLine } from '../types'

export interface GridLineHost {
    readonly index: GroupIndex
    readonly pileIndex: Map<number, PileData>
    readonly rev: number
}

interface GridBlock {
    rev: number
    group: Group
    slots: number[]
    count: number
    pile: PileData | undefined
    size: number
    lines: ScrollerLine[]
}

// The rows of a leaf, flat: one per slot. Ids stay `<group>-img:<instance>` — unique (the same
// image can sit in several groups) and stable across rebuilds, which RecycleScroller's key-field
// and the per-cell keys rely on; a string per row is only paid when the block is (re)built.
// The height last measured for a row showing this image, if any.
export type MeasuredHeight = (instanceId: number) => number | undefined

const NOT_MEASURED: MeasuredHeight = () => undefined

// The image a grid row shows the values of: its own, or a pile's first.
export function rowInstanceId(line: ScrollerLine, ids: ArrayLike<number>): number | undefined {
    if (line.type === 'image') return (line as RowLine).data.id
    if (line.type === 'pile') return ids[(line as PileRowLine).data.slots[0]]
    return undefined
}

function flatRows(group: Group, ids: ArrayLike<number>, size: number, measured: MeasuredHeight): ScrollerLine[] {
    const lines: ScrollerLine[] = new Array(group.slots.length)
    for (let i = 0; i < group.slots.length; i++) {
        const instanceId = ids[group.slots[i]]
        lines[i] = {
            id: group.id + '-img:' + instanceId,
            data: { id: instanceId, imageUrl: '' },
            type: 'image',
            size: measured(instanceId) ?? size,
            index: i,
            groupId: group.id,
        } as RowLine
    }
    return lines
}

function pileRows(group: Group, pile: PileData, ids: ArrayLike<number>, size: number, measured: MeasuredHeight): ScrollerLine[] {
    const pileCount = pile.bounds.length - 1
    const lines: ScrollerLine[] = new Array(pileCount)
    for (let i = 0; i < pileCount; i++) {
        const slots = pile.order.slice(pile.bounds[i], pile.bounds[i + 1])
        lines[i] = {
            id: group.id + '-sha1:' + ids[slots[0]],
            data: { groupId: group.id, pileIndex: i, slots },
            type: 'pile',
            size: measured(ids[slots[0]]) ?? size,
        } as PileRowLine
    }
    return lines
}

// Do these rows still draw exactly this leaf (same images, same piles, same order)?
function sameRows(lines: ScrollerLine[], group: Group, pile: PileData | undefined, ids: ArrayLike<number>): boolean {
    if (!pile) {
        const slots = group.slots
        if (lines.length !== slots.length) return false
        for (let i = 0; i < slots.length; i++) {
            const line = lines[i]
            if (line.type !== 'image' || line.groupId !== group.id || (line as RowLine).data.id !== ids[slots[i]]) return false
        }
        return true
    }
    const pileCount = pile.bounds.length - 1
    if (lines.length !== pileCount) return false
    for (let i = 0; i < pileCount; i++) {
        const line = lines[i]
        if (line.type !== 'pile') return false
        const handle = (line as PileRowLine).data
        const from = pile.bounds[i], to = pile.bounds[i + 1]
        if (handle.groupId !== group.id || handle.slots.length !== to - from) return false
        for (let j = 0; j < handle.slots.length; j++) if (handle.slots[j] !== pile.order[from + j]) return false
    }
    return true
}

const NO_LINES: ScrollerLine[] = []

export class GridLineCache {
    private blocks = new Map<number, GridBlock>()
    private host: GridLineHost | undefined

    // The rows open leaf `group` draws (none when it holds no image). `size` is the estimate for
    // the rows `measured` has no height for.
    leafLines(host: GridLineHost, group: Group, ids: ArrayLike<number>, size: number, measured = NOT_MEASURED): ScrollerLine[] {
        if (host !== this.host) {
            this.blocks.clear()
            this.host = host
        }
        if (!group.slots.length) return NO_LINES
        const pile = host.pileIndex.get(group.id)
        const block = this.blocks.get(group.id)
        if (block && block.size === size) {
            if (block.rev === host.rev && block.group === group && block.slots === group.slots
                && block.count === group.slots.length && block.pile === pile) return block.lines
            if (sameRows(block.lines, group, pile, ids)) {
                this.stamp(block, host, group, pile)
                return block.lines
            }
        }
        const lines = pile ? pileRows(group, pile, ids, size, measured) : flatRows(group, ids, size, measured)
        const next = { lines, size } as GridBlock
        this.stamp(next, host, group, pile)
        this.blocks.set(group.id, next)
        return lines
    }

    private stamp(block: GridBlock, host: GridLineHost, group: Group, pile: PileData | undefined) {
        block.rev = host.rev
        block.group = group
        block.slots = group.slots
        block.count = group.slots.length
        block.pile = pile
    }

    // The rows' layout changed (row height, columns): every cached row goes back to the estimate
    // `size`, in place, except those in `keep` — the rows on screen, which measure themselves
    // again when their height changes and are still right when it does not. Whether any changed.
    resize(size: number, keep?: ReadonlySet<ScrollerLine>): boolean {
        let changed = false
        for (const block of this.blocks.values()) {
            block.size = size
            for (const line of block.lines) {
                if (line.size === size || keep?.has(line)) continue
                line.size = size
                changed = true
            }
        }
        return changed
    }

    // Drop the blocks of groups the tree no longer holds. O(cached leaves).
    prune(host: GridLineHost) {
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
