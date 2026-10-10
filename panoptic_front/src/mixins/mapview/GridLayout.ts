export interface GridAssignment {
    cols: number
    rows: number
    col: Int32Array
    row: Int32Array
}

export const DEFAULT_GRID_DENSITY = 1.5
const MAX_ASPECT = 4

/**
 * Assigns every point its own cell of a cols × rows grid while keeping the layout of the
 * projection: the grid has `density` cells per point, so empty regions of the projection stay
 * empty and distant clusters stay apart.
 *
 * Capacity-constrained recursive bisection: each region is cut at its geometric middle, points go
 * to the side their position falls on, and only when a side is over capacity do the points
 * closest to the cut cross over.
 */
export function computeGridAssignment(xs: ArrayLike<number>, ys: ArrayLike<number>, density = DEFAULT_GRID_DENSITY): GridAssignment {
    const n = xs.length
    const col = new Int32Array(n)
    const row = new Int32Array(n)
    if (n === 0) return { cols: 0, rows: 0, col, row }

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (let i = 0; i < n; i++) {
        const x = xs[i], y = ys[i]
        if (!Number.isFinite(x) || !Number.isFinite(y)) continue
        if (x < minX) minX = x
        if (x > maxX) maxX = x
        if (y < minY) minY = y
        if (y > maxY) maxY = y
    }
    if (minX > maxX) { minX = maxX = 0; minY = maxY = 0 }
    const w = maxX - minX, h = maxY - minY

    let aspect = 1
    if (w > 0 && h > 0) aspect = Math.min(MAX_ASPECT, Math.max(1 / MAX_ASPECT, w / h))
    else if (w > 0) aspect = MAX_ASPECT
    else if (h > 0) aspect = 1 / MAX_ASPECT

    const cells = Math.max(n, Math.ceil(n * Math.max(1, density)))
    const cols = Math.max(1, Math.min(cells, Math.round(Math.sqrt(cells * aspect))))
    const rows = Math.ceil(cells / cols)

    const u = new Float64Array(n)
    const v = new Float64Array(n)
    for (let i = 0; i < n; i++) {
        const x = Number.isFinite(xs[i]) ? xs[i] : (minX + maxX) / 2
        const y = Number.isFinite(ys[i]) ? ys[i] : (minY + maxY) / 2
        u[i] = w > 0 ? (x - minX) / w * cols : cols / 2
        v[i] = h > 0 ? (y - minY) / h * rows : rows / 2
    }

    // Points sorted once along each axis. Every region holds the same points in [lo, hi) of both
    // orders; a split keeps both sorted by partitioning them stably, instead of re-sorting.
    const byU = (a: number, b: number) => (u[a] - u[b]) || (v[a] - v[b]) || (a - b)
    const byV = (a: number, b: number) => (v[a] - v[b]) || (u[a] - u[b]) || (a - b)
    const orderU = new Int32Array(n)
    for (let i = 0; i < n; i++) orderU[i] = i
    const orderV = orderU.slice()
    orderU.sort(byU)
    orderV.sort(byV)
    const isLow = new Uint8Array(n)
    const scratch = new Int32Array(n)

    const partition = (order: Int32Array, lo: number, hi: number) => {
        let w = lo, h = 0
        for (let i = lo; i < hi; i++) {
            const p = order[i]
            if (isLow[p]) order[w++] = p
            else scratch[h++] = p
        }
        order.set(scratch.subarray(0, h), w)
    }

    const place = (c0: number, c1: number, r0: number, r1: number, lo: number, hi: number) => {
        const count = hi - lo
        if (count === 0) return
        const width = c1 - c0, height = r1 - r0
        if (width * height === 1) {
            col[orderU[lo]] = c0
            row[orderU[lo]] = r0
            return
        }
        const splitCols = width >= height
        const key = splitCols ? u : v
        const start = splitCols ? c0 : r0
        const length = splitCols ? width : height
        const across = splitCols ? height : width
        const mid = start + Math.floor(length / 2)

        const sorted = splitCols ? orderU : orderV
        let a = lo, b = hi
        while (a < b) {
            const m = (a + b) >> 1
            if (key[sorted[m]] < mid) a = m + 1
            else b = m
        }
        const capLow = (mid - start) * across
        const capHigh = (start + length - mid) * across
        const k = Math.max(count - capHigh, Math.min(a - lo, capLow))

        for (let i = lo; i < lo + k; i++) isLow[sorted[i]] = 1
        partition(splitCols ? orderV : orderU, lo, hi)
        for (let i = lo; i < lo + k; i++) isLow[sorted[i]] = 0

        if (splitCols) {
            place(c0, mid, r0, r1, lo, lo + k)
            place(mid, c1, r0, r1, lo + k, hi)
        } else {
            place(c0, c1, r0, mid, lo, lo + k)
            place(c0, c1, mid, r1, lo + k, hi)
        }
    }
    place(0, cols, 0, rows, 0, n)

    return { cols, rows, col, row }
}

export interface MapGrid {
    cols: number
    rows: number
    // sha1 -> row * cols + col
    cells: Map<string, number>
}

// Keyed by the map's flat data array, so a reloaded map gets a fresh grid.
const mapGrids = new WeakMap<any[], Map<number, MapGrid>>()
const DENSITIES_PER_MAP = 3

// Grid over every point of a map ([sha1, x, y, ...]), computed once per map and density (the
// last few densities stay cached).
export function mapGrid(data: any[], density = DEFAULT_GRID_DENSITY): MapGrid {
    let byDensity = mapGrids.get(data)
    if (!byDensity) mapGrids.set(data, byDensity = new Map())
    const cached = byDensity.get(density)
    if (cached) {
        byDensity.delete(density)
        byDensity.set(density, cached)
        return cached
    }
    if (byDensity.size >= DENSITIES_PER_MAP) byDensity.delete(byDensity.keys().next().value!)

    const n = Math.floor(data.length / 3)
    const xs = new Float64Array(n), ys = new Float64Array(n)
    for (let i = 0; i < n; i++) {
        xs[i] = data[i * 3 + 1]
        ys[i] = data[i * 3 + 2]
    }
    const a = computeGridAssignment(xs, ys, density)
    const cells = new Map<string, number>()
    for (let i = 0; i < n; i++) cells.set(data[i * 3], a.row[i] * a.cols + a.col[i])
    const grid = { cols: a.cols, rows: a.rows, cells }
    byDensity.set(density, grid)
    return grid
}

// World position of a cell's centre, the grid centred on the origin.
export function cellCenter(grid: MapGrid, cell: number, cellSize: number): [number, number] {
    const col = cell % grid.cols
    const row = Math.floor(cell / grid.cols)
    return [(col - grid.cols / 2 + 0.5) * cellSize, (row - grid.rows / 2 + 0.5) * cellSize]
}
