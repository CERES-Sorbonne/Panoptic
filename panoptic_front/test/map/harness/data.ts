export function rng(seed: number) {
    let s = seed >>> 0
    return () => {
        s = (s + 0x6D2B79F5) >>> 0
        let t = s
        t = Math.imul(t ^ (t >>> 15), t | 1)
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296
    }
}

function gaussian(rand: () => number) {
    const a = Math.max(rand(), 1e-12), b = rand()
    return Math.sqrt(-2 * Math.log(a)) * Math.cos(2 * Math.PI * b)
}

export interface Cloud {
    xs: Float64Array
    ys: Float64Array
    labels: Int32Array
}

export function uniformCloud(n: number, seed = 1): Cloud {
    const rand = rng(seed)
    const xs = new Float64Array(n), ys = new Float64Array(n)
    for (let i = 0; i < n; i++) { xs[i] = rand() * 200 - 100; ys[i] = rand() * 200 - 100 }
    return { xs, ys, labels: new Int32Array(n) }
}

// Blobs of uneven size and spread on a circle of radius 70, like a UMAP of a few classes.
export function blobCloud(n: number, blobs: number, seed = 1, spread = 6): Cloud {
    const rand = rng(seed)
    const weights = Array.from({ length: blobs }, () => 0.5 + rand())
    const total = weights.reduce((a, b) => a + b, 0)
    const xs = new Float64Array(n), ys = new Float64Array(n), labels = new Int32Array(n)
    let i = 0
    for (let b = 0; b < blobs; b++) {
        const count = b === blobs - 1 ? n - i : Math.round(n * weights[b] / total)
        const angle = 2 * Math.PI * b / blobs
        const cx = 70 * Math.cos(angle), cy = 70 * Math.sin(angle)
        const s = spread * (0.6 + 0.8 * rand())
        for (let j = 0; j < count && i < n; j++, i++) {
            xs[i] = cx + s * gaussian(rand)
            ys[i] = cy + s * gaussian(rand)
            labels[i] = b
        }
    }
    return { xs, ys, labels }
}
