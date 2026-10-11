/**
 * The grid scroller's content, as a LayoutSource for the VirtualScroller, and its row objects.
 *
 * The grid draws one row per image (or per sha1 pile) of every open leaf, under a header line per
 * leaf. It used to build one row object (and one id string) per image of the whole tree on every
 * version bump. Now the tree is the layout (gridSource: a leaf's row count is its slot or pile
 * count), and a row object is made only for the rows on screen (gridRow), from the leaf itself.
 *
 * Rows fit their content: the VirtualScroller measures them (`measure`) and the layout keeps the
 * sizes per leaf; the row size handed in is the estimate for the rows not measured yet.
 *
 * Pure on purpose (no Vue, no stores): the scroller adapts it, and the tests drive it.
 */
import type { Group, GroupIndex } from '@/core/group/types'
import type { PileData } from '@/core/sha1Piles'
import type { GroupLine, PileRowLine, RowLine } from '../types'
import type { LayoutSource, LineRef, ScrollLayout } from '../virtual/scrollLayout'
import type { CellWalk } from '../cellNavigation'

export interface GridLineHost {
    readonly index: GroupIndex
    readonly pileIndex: Map<number, PileData>
    readonly root?: Group
}

// Height of a leaf's header line.
export const GRID_GROUP_LINE_SIZE = 35

/**
 * The tree as the grid draws it: an inner group has no line of its own (closed, it hides its whole
 * subtree); a leaf has a header (but the root) and, open, one row per image or pile.
 */
export function gridSource(host: () => GridLineHost, rowSize: () => number): LayoutSource {
    const group = (id: number) => host().index[id]
    return {
        root: () => host().root?.id,
        childCount: id => group(id)?.children.length ?? 0,
        child: (id, i) => group(id).children[i].id,
        isOpen: id => !group(id)?.view.closed,
        headerSize: id => {
            const g = group(id)
            return g && !g.children.length && id !== 0 ? GRID_GROUP_LINE_SIZE : 0
        },
        bodyLines: id => {
            const g = group(id)
            if (!g || g.children.length || !g.slots?.length) return 0
            const pile = host().pileIndex.get(id)
            return pile ? pile.bounds.length - 1 : g.slots.length
        },
        lineEstimate: () => rowSize(),
        lineType: (id, index) => index < 0 ? 'group' : host().pileIndex.has(id) ? 'pile' : 'image',
    }
}

export function gridGroupLine(group: Group, previous?: GroupLine): GroupLine {
    // GroupManager rebuilds the tree with new Group objects: a line holding the old one is stale.
    if (previous && previous.data === group) return previous
    return { id: group.id, data: group, type: 'group', size: GRID_GROUP_LINE_SIZE, nbClusters: 10, groupId: group.id }
}

/**
 * Row `ref.index` of leaf `ref.node`: its image (flat leaf) or its pile. `previous` is handed back
 * while it still shows the same thing. Undefined when the leaf no longer has that row.
 */
export function gridRow(host: GridLineHost, ids: ArrayLike<number>, ref: LineRef, previous?: RowLine | PileRowLine): RowLine | PileRowLine | undefined {
    const group = host.index[ref.node]
    if (!group || group.children.length || ref.index < 0) return undefined
    const pile = host.pileIndex.get(ref.node)
    if (pile) {
        if (ref.index >= pile.bounds.length - 1) return undefined
        const from = pile.bounds[ref.index], to = pile.bounds[ref.index + 1]
        if (previous?.type === 'pile') {
            const handle = (previous as PileRowLine).data
            let same = handle.groupId === group.id && handle.pileIndex === ref.index && handle.slots.length === to - from
            for (let j = 0; same && j < handle.slots.length; j++) same = handle.slots[j] === pile.order[from + j]
            if (same) return previous
        }
        const slots = pile.order.slice(from, to)
        return {
            id: group.id + '-sha1:' + ids[slots[0]],
            data: { groupId: group.id, pileIndex: ref.index, slots },
            type: 'pile',
            size: 0,
        } as PileRowLine
    }
    if (ref.index >= group.slots.length) return undefined
    const instanceId = ids[group.slots[ref.index]]
    if (previous?.type === 'image' && previous.groupId === group.id && previous.index === ref.index
        && (previous as RowLine).data.id === instanceId) return previous
    return {
        id: group.id + '-img:' + instanceId,
        data: { id: instanceId, imageUrl: '' },
        type: 'image',
        size: 0,
        index: ref.index,
        groupId: group.id,
    } as RowLine
}

// The image a grid row edits and shows the values of: its own, or a pile's first.
export function rowInstanceId(row: RowLine | PileRowLine, ids: ArrayLike<number>): number | undefined {
    if (row.type === 'pile') return ids[(row as PileRowLine).data.slots[0]]
    return (row as RowLine).data.id
}

// Row of leaf `group` showing `instanceId` (a pile row by its first image), or -1.
export function rowIndexOf(host: GridLineHost, ids: ArrayLike<number>, group: Group, instanceId: number): number {
    const pile = host.pileIndex.get(group.id)
    if (pile) {
        for (let i = 0; i < pile.bounds.length - 1; i++) if (ids[pile.order[pile.bounds[i]]] === instanceId) return i
        return -1
    }
    for (let i = 0; i < group.slots.length; i++) if (ids[group.slots[i]] === instanceId) return i
    return -1
}

// One cell per image or pile row, in display order, for Tab. A pile row edits its first image.
export function gridCellWalk(host: GridLineHost, layout: ScrollLayout, ids: ArrayLike<number>): CellWalk<LineRef> {
    return {
        find: from => {
            const group = host.index[from.groupId]
            if (!group || group.children.length) return undefined
            const index = rowIndexOf(host, ids, group, from.instanceId)
            const line = { node: group.id, index }
            return index >= 0 && layout.isShown(line) ? { line, index: 0 } : undefined
        },
        cells: line => line.index >= 0 && gridRow(host, ids, line) ? 1 : 0,
        at: line => ({ instanceId: rowInstanceId(gridRow(host, ids, line)!, ids)!, groupId: line.node }),
        next: line => layout.next(line),
        prev: line => layout.prev(line),
    }
}
