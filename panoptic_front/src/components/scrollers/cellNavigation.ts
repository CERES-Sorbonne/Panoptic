// Tab / Shift-Tab between property cells, read off the scroller's own line list.
//
// This used to go through inputStore: every mounted row registered itself under its image order,
// and Tab jumped to the next registered one. Now only the edited cell has an editor, so there is
// nothing mounted to register — and the scroller already holds the display order in full. Pure on
// purpose (no Vue, no stores): the scrollers adapt their lines to `CellLines` and the walk itself
// is tested on plain arrays.

// One property cell of one image as a scroller shows it. The group is part of the identity: the
// same image can be drawn in several groups, and each copy is its own cell.
export interface CellTarget {
    instanceId: number
    groupId: number
}

export interface CellPosition {
    line: number
    index: number
    cell: CellTarget
}

// Read access to a scroller's lines in display order, without materializing a cell list:
// `cells(line)` is how many cells of the navigated property that line draws (0 for a group
// header, or a line that does not show the property at all).
export interface CellLines {
    count: number
    cells(line: number): number
    at(line: number, index: number): CellTarget
}

export function sameTarget(a: CellTarget, b: CellTarget) {
    return !!a && !!b && a.instanceId === b.instanceId && a.groupId === b.groupId
}

// Where `from` is drawn. `hint` is a line to start looking at (the first line of its group, when
// the scroller knows it), so a long list is not scanned from the top on every key press; the
// rest of the list is still searched if the hint is wrong.
export function findCell(lines: CellLines, from: CellTarget, hint = 0): CellPosition | undefined {
    const start = Math.max(0, Math.min(hint, lines.count))
    const scan = (lo: number, hi: number) => {
        for (let l = lo; l < hi; l++) {
            const n = lines.cells(l)
            for (let i = 0; i < n; i++) {
                const cell = lines.at(l, i)
                if (sameTarget(cell, from)) return { line: l, index: i, cell }
            }
        }
        return undefined
    }
    return scan(start, lines.count) ?? scan(0, start)
}

// The cell before or after `from` in display order, skipping lines without one. Undefined at
// either end of the list (no wrap-around), and when `from` is not drawn at all.
export function adjacentCell(lines: CellLines, from: CellTarget, backwards: boolean, hint = 0): CellPosition | undefined {
    const pos = findCell(lines, from, hint)
    if (!pos) return undefined
    const step = backwards ? -1 : 1

    const index = pos.index + step
    if (index >= 0 && index < lines.cells(pos.line)) {
        return { line: pos.line, index, cell: lines.at(pos.line, index) }
    }
    for (let l = pos.line + step; l >= 0 && l < lines.count; l += step) {
        const n = lines.cells(l)
        if (!n) continue
        const i = backwards ? n - 1 : 0
        return { line: l, index: i, cell: lines.at(l, i) }
    }
    return undefined
}

// Scroll position that brings the line [top, top + size) fully into a viewport of `height` at
// `scrollTop`, moving as little as possible; undefined when it is already in view. A line taller
// than the viewport is aligned on its top.
export function revealOffset(top: number, size: number, scrollTop: number, height: number): number | undefined {
    if (top < scrollTop) return top
    if (top + size > scrollTop + height) return size > height ? top : top + size - height
    return undefined
}

// The same walk over a scroller that has no flat line list (VirtualScroller): lines are opaque
// handles, found from the cell and stepped through one by one. `find` locates the cell itself (the
// scroller knows its group and can compute its line), so nothing is scanned from the top.
export interface CellWalk<L> {
    find(from: CellTarget): { line: L, index: number } | undefined
    cells(line: L): number
    at(line: L, index: number): CellTarget
    next(line: L): L | null
    prev(line: L): L | null
}

export interface CellAt<L> {
    line: L
    index: number
    cell: CellTarget
}

// At most this many lines are stepped over looking for the next one with a cell (group headers,
// closed groups): past that the walk gives up rather than freeze on a huge run of empty groups.
const MAX_STEPS = 100_000

export function adjacentCellIn<L>(walk: CellWalk<L>, from: CellTarget, backwards: boolean): CellAt<L> | undefined {
    const pos = walk.find(from)
    if (!pos) return undefined
    const index = pos.index + (backwards ? -1 : 1)
    if (index >= 0 && index < walk.cells(pos.line)) return { line: pos.line, index, cell: walk.at(pos.line, index) }
    let line = backwards ? walk.prev(pos.line) : walk.next(pos.line)
    for (let steps = 0; line !== null && steps < MAX_STEPS; steps++) {
        const n = walk.cells(line)
        if (n) {
            const i = backwards ? n - 1 : 0
            return { line, index: i, cell: walk.at(line, i) }
        }
        line = backwards ? walk.prev(line) : walk.next(line)
    }
    return undefined
}
