/**
 * Thresholds sit below what the layout measures today (see bench.ts), so a failure means a real
 * loss of neighbourhood or separation, not noise.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { computeGridAssignment, type GridAssignment } from '@/mixins/mapview/GridLayout'
import { blobCloud, uniformCloud } from '../harness/data'
import { distanceCorrelation, foreignAdjacency, knnPreservation } from '../harness/metrics'

// Share of each label's points that sit in its largest 4-connected patch, worst label.
function worstCohesion(a: GridAssignment, labels: Int32Array): number {
    const cell = new Int32Array(a.cols * a.rows).fill(-1)
    for (let i = 0; i < labels.length; i++) cell[a.row[i] * a.cols + a.col[i]] = i
    const seen = new Uint8Array(labels.length)
    const largest = new Map<number, number>()
    const total = new Map<number, number>()
    for (let i = 0; i < labels.length; i++) total.set(labels[i], (total.get(labels[i]) ?? 0) + 1)
    for (let s = 0; s < labels.length; s++) {
        if (seen[s]) continue
        seen[s] = 1
        let size = 0
        const stack = [s]
        while (stack.length) {
            const i = stack.pop()!
            size++
            const c = a.col[i], r = a.row[i]
            for (const [dc, dr] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
                const nc = c + dc, nr = r + dr
                if (nc < 0 || nr < 0 || nc >= a.cols || nr >= a.rows) continue
                const j = cell[nr * a.cols + nc]
                if (j >= 0 && !seen[j] && labels[j] === labels[s]) { seen[j] = 1; stack.push(j) }
            }
        }
        largest.set(labels[s], Math.max(largest.get(labels[s]) ?? 0, size))
    }
    let worst = 1
    for (const [label, n] of total) worst = Math.min(worst, largest.get(label)! / n)
    return worst
}

test('grid: a uniform cloud keeps its geometry', () => {
    const c = uniformCloud(1000)
    const a = computeGridAssignment(c.xs, c.ys)
    assert.ok(distanceCorrelation(c.xs, c.ys, a) > 0.99)
    assert.ok(knnPreservation(c.xs, c.ys, a) > 0.65)
})

test('grid: blobs keep their neighbourhoods and their distances', () => {
    const c = blobCloud(1000, 8)
    const a = computeGridAssignment(c.xs, c.ys)
    const spearman = distanceCorrelation(c.xs, c.ys, a)
    const knn = knnPreservation(c.xs, c.ys, a)
    assert.ok(spearman > 0.9, `spearman ${spearman}`)
    assert.ok(knn > 0.5, `knn ${knn}`)
})

test('grid: each blob stays in one piece', () => {
    for (const d of [1, 1.5, 2]) {
        const c = blobCloud(2000, 8, 5)
        const cohesion = worstCohesion(computeGridAssignment(c.xs, c.ys, d), c.labels)
        assert.ok(cohesion > 0.95, `d=${d}: worst blob keeps ${cohesion} of its points together`)
    }
})

test('grid: distinct blobs barely touch, less so with more empty cells', () => {
    const c = blobCloud(2000, 8)
    const foreign = [1, 1.5, 2].map(d => foreignAdjacency(computeGridAssignment(c.xs, c.ys, d), c.labels))
    assert.ok(foreign[1] < 0.05, `d=1.5: ${foreign[1]}`)
    assert.ok(foreign[2] < 0.02, `d=2: ${foreign[2]}`)
    assert.ok(foreign[0] > foreign[1] && foreign[1] > foreign[2], `${foreign}`)

    const far = blobCloud(2000, 3, 2, 12)
    assert.equal(foreignAdjacency(computeGridAssignment(far.xs, far.ys, 1.5), far.labels), 0, 'three far blobs never touch')
})
