import type { GroupScoreList, PointData } from '@/data/models'

export interface ScoreBounds {
    min: number
    max: number
}

// A point the score threshold removed: not drawn, and out of reach of hover and selection tools.
export function isPointHidden(p: PointData) {
    return p.opacity === 0
}

// Score within the range the plugin declares: 0 is the worst, 1 the best, whichever way it counts.
export function scoreQuality(value: number, scores: GroupScoreList) {
    const range = scores.max - scores.min
    const t = range > 0 ? Math.min(1, Math.max(0, (value - scores.min) / range)) : value
    return scores.maxIsBest ? t : 1 - t
}

// Range of the scores actually present: a plugin can drop the low ones, leaving no use for that
// part of the slider. NaN marks a point without a score.
export function scoreBounds(qualities: ArrayLike<number>): ScoreBounds | null {
    let min = Infinity
    let max = -Infinity
    for (let i = 0; i < qualities.length; i++) {
        const q = qualities[i]
        if (isNaN(q)) continue
        if (q < min) min = q
        if (q > max) max = q
    }
    return min === Infinity ? null : { min, max }
}

// Unset, the slider starts halfway through the scores present. Once set it is kept across
// searches, whose bounds differ: clamping means a threshold above the best score still shows the
// best images rather than an empty map.
export function effectiveThreshold(threshold: number | undefined, bounds: ScoreBounds | null) {
    if (!bounds) return 0
    if (threshold == null) return (bounds.min + bounds.max) / 2
    return Math.min(bounds.max, Math.max(bounds.min, threshold))
}

// Hides the points under the threshold. Returns how many stay visible.
export function applyScoreThreshold(points: PointData[], qualities: ArrayLike<number>, threshold: number) {
    let shown = 0
    for (let i = 0; i < points.length; i++) {
        const visible = qualities[i] >= threshold
        points[i].opacity = visible ? 1 : 0
        if (visible) shown++
    }
    return shown
}
