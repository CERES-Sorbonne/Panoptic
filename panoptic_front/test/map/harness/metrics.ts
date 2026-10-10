import type { GridAssignment } from '@/mixins/mapview/GridLayout'
import { rng } from './data'

export function invalidCells(a: GridAssignment): string[] {
    const problems: string[] = []
    const seen = new Set<number>()
    for (let i = 0; i < a.col.length; i++) {
        const c = a.col[i], r = a.row[i]
        if (c < 0 || c >= a.cols || r < 0 || r >= a.rows) problems.push(`point ${i} out of bounds (${c}, ${r})`)
        const key = r * a.cols + c
        if (seen.has(key)) problems.push(`point ${i} shares cell (${c}, ${r})`)
        seen.add(key)
    }
    return problems
}

function knn(px: ArrayLike<number>, py: ArrayLike<number>, i: number, k: number): number[] {
    const d: [number, number][] = []
    for (let j = 0; j < px.length; j++) {
        if (j === i) continue
        const dx = px[j] - px[i], dy = py[j] - py[i]
        d.push([dx * dx + dy * dy, j])
    }
    d.sort((a, b) => a[0] - b[0] || a[1] - b[1])
    return d.slice(0, k).map(e => e[1])
}

// Mean share of each point's k nearest neighbours in the projection that are still among its k
// nearest in the grid. O(n²): keep n in the low thousands.
export function knnPreservation(xs: ArrayLike<number>, ys: ArrayLike<number>, a: GridAssignment, k = 10): number {
    const n = xs.length
    let kept = 0
    for (let i = 0; i < n; i++) {
        const before = new Set(knn(xs, ys, i, k))
        for (const j of knn(a.col, a.row, i, k)) if (before.has(j)) kept++
    }
    return kept / (n * k)
}

function ranks(values: number[]): number[] {
    const order = values.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0])
    const r = new Array(values.length)
    for (let i = 0; i < order.length;) {
        let j = i
        while (j + 1 < order.length && order[j + 1][0] === order[i][0]) j++
        for (let t = i; t <= j; t++) r[order[t][1]] = (i + j) / 2
        i = j + 1
    }
    return r
}

// Spearman correlation between projection and grid distances over random pairs.
export function distanceCorrelation(xs: ArrayLike<number>, ys: ArrayLike<number>, a: GridAssignment, pairs = 20000, seed = 7): number {
    const rand = rng(seed)
    const n = xs.length
    const before: number[] = [], after: number[] = []
    for (let p = 0; p < pairs; p++) {
        const i = Math.floor(rand() * n), j = Math.floor(rand() * n)
        if (i === j) continue
        before.push(Math.hypot(xs[i] - xs[j], ys[i] - ys[j]))
        after.push(Math.hypot(a.col[i] - a.col[j], a.row[i] - a.row[j]))
    }
    const rb = ranks(before), ra = ranks(after)
    const m = rb.length
    const mean = (m - 1) / 2
    let num = 0, db = 0, da = 0
    for (let t = 0; t < m; t++) {
        num += (rb[t] - mean) * (ra[t] - mean)
        db += (rb[t] - mean) ** 2
        da += (ra[t] - mean) ** 2
    }
    return num / Math.sqrt(db * da)
}

// Share of side-by-side occupied cell pairs whose points carry different labels.
export function foreignAdjacency(a: GridAssignment, labels: ArrayLike<number>): number {
    const cell = new Int32Array(a.cols * a.rows).fill(-1)
    for (let i = 0; i < a.col.length; i++) cell[a.row[i] * a.cols + a.col[i]] = i
    let pairs = 0, foreign = 0
    for (let r = 0; r < a.rows; r++) {
        for (let c = 0; c < a.cols; c++) {
            const i = cell[r * a.cols + c]
            if (i < 0) continue
            const right = c + 1 < a.cols ? cell[r * a.cols + c + 1] : -1
            const up = r + 1 < a.rows ? cell[(r + 1) * a.cols + c] : -1
            for (const j of [right, up]) {
                if (j < 0) continue
                pairs++
                if (labels[i] !== labels[j]) foreign++
            }
        }
    }
    return pairs ? foreign / pairs : 0
}
