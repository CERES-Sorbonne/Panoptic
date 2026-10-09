// Group regions of the grid layout. `cellGroup` holds, for each cell (row * cols + col), the index
// of the group drawn there, or -1 for an empty cell. Outside the grid counts as empty.

export interface Island {
    group: number
    size: number
    // Cell the label goes on: the island's cell closest to its centroid, so it stays inside
    // islands that wrap around a hole or bend.
    c: number
    r: number
}

// Values per stroke in groupStrokes' output.
export const STROKE_STRIDE = 7

/**
 * Outline strokes of the groups, laid inside each group along its edge against another group or
 * an empty cell: where two groups touch there is one stroke on each side, each of its own group.
 * Flat [x0, y0, x1, y1, nx, ny, group, ...]: a segment in cell units (cell (c, r) spans
 * [c, c + 1) × [r, r + 1)), the unit normal pointing into the group's cells, the group index.
 * Consecutive cell edges of one group along a line are merged into one stroke.
 */
export function groupStrokes(cellGroup: Int32Array, cols: number, rows: number): number[] {
    const g = (c: number, r: number) => (c < 0 || r < 0 || c >= cols || r >= rows) ? -1 : cellGroup[r * cols + c]
    const res: number[] = []
    // One line (x = k across rows, or y = k across columns), one side of it.
    const scan = (length: number, side: (i: number) => number, other: (i: number) => number,
        push: (start: number, end: number, group: number) => void) => {
        let start = -1, group = -1
        for (let i = 0; i <= length; i++) {
            const here = i < length ? side(i) : -1
            const edge = here >= 0 && here !== other(i)
            if (start >= 0 && (!edge || here !== group)) {
                push(start, i, group)
                start = -1
            }
            if (edge && start < 0) {
                start = i
                group = here
            }
        }
    }
    for (let c = 0; c <= cols; c++) {
        scan(rows, r => g(c - 1, r), r => g(c, r), (r0, r1, group) => res.push(c, r0, c, r1, -1, 0, group))
        scan(rows, r => g(c, r), r => g(c - 1, r), (r0, r1, group) => res.push(c, r0, c, r1, 1, 0, group))
    }
    for (let r = 0; r <= rows; r++) {
        scan(cols, c => g(c, r - 1), c => g(c, r), (c0, c1, group) => res.push(c0, r, c1, r, 0, -1, group))
        scan(cols, c => g(c, r), c => g(c, r - 1), (c0, c1, group) => res.push(c0, r, c1, r, 0, 1, group))
    }
    return res
}

// 4-connected runs of cells of one group, largest first.
export function groupIslands(cellGroup: Int32Array, cols: number, rows: number): Island[] {
    const n = cols * rows
    const islandOf = new Int32Array(n).fill(-1)
    const stack = new Int32Array(n)
    const found: { group: number, size: number, sumC: number, sumR: number }[] = []

    for (let start = 0; start < n; start++) {
        const group = cellGroup[start]
        if (group < 0 || islandOf[start] >= 0) continue
        const id = found.length
        const island = { group, size: 0, sumC: 0, sumR: 0 }
        found.push(island)
        let top = 0
        stack[top++] = start
        islandOf[start] = id
        while (top > 0) {
            const cell = stack[--top]
            const c = cell % cols, r = (cell - c) / cols
            island.size++
            island.sumC += c
            island.sumR += r
            const visit = (next: number) => {
                if (islandOf[next] < 0 && cellGroup[next] === group) {
                    islandOf[next] = id
                    stack[top++] = next
                }
            }
            if (c > 0) visit(cell - 1)
            if (c < cols - 1) visit(cell + 1)
            if (r > 0) visit(cell - cols)
            if (r < rows - 1) visit(cell + cols)
        }
    }

    const best = new Float64Array(found.length).fill(Infinity)
    const res: Island[] = found.map(f => ({ group: f.group, size: f.size, c: 0, r: 0 }))
    for (let cell = 0; cell < n; cell++) {
        const id = islandOf[cell]
        if (id < 0) continue
        const f = found[id]
        const c = cell % cols, r = (cell - c) / cols
        const d = (c - f.sumC / f.size) ** 2 + (r - f.sumR / f.size) ** 2
        if (d < best[id]) {
            best[id] = d
            res[id].c = c
            res[id].r = r
        }
    }
    return res.sort((a, b) => b.size - a.size)
}
