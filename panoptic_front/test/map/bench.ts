/**
 * Grid layout bench (not part of `npm test`): quality metrics on synthetic clouds, then timings.
 *   node test/map/build.mjs && node test/map/.build/bench.mjs
 */
import { computeGridAssignment } from '@/mixins/mapview/GridLayout'
import { blobCloud, uniformCloud, type Cloud } from './harness/data'
import { distanceCorrelation, foreignAdjacency, knnPreservation } from './harness/metrics'

const clouds: [string, Cloud][] = [
    ['uniform 2000', uniformCloud(2000)],
    ['8 blobs 2000', blobCloud(2000, 8)],
    ['3 blobs 2000', blobCloud(2000, 3, 2, 12)],
]

for (const density of [1, 1.5, 2]) {
    for (const [name, c] of clouds) {
        const a = computeGridAssignment(c.xs, c.ys, density)
        console.log(`d=${density} ${name.padEnd(14)} ${a.cols}x${a.rows}`
            + `  knn10=${knnPreservation(c.xs, c.ys, a).toFixed(3)}`
            + `  spearman=${distanceCorrelation(c.xs, c.ys, a).toFixed(3)}`
            + `  foreign=${foreignAdjacency(a, c.labels).toFixed(4)}`)
    }
}

for (const n of [10_000, 50_000, 100_000, 300_000]) {
    const c = blobCloud(n, 20, 3)
    const t = performance.now()
    computeGridAssignment(c.xs, c.ys)
    console.log(`n=${n}: ${(performance.now() - t).toFixed(0)} ms`)
}
