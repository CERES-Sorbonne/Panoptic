import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import type { GroupScoreList, PointData } from '@/data/models'
import { applyScoreThreshold, effectiveThreshold, isPointHidden, scoreBounds, scoreQuality } from '@/mixins/mapview/ScoreFilter'
import { SpatialIndex } from '@/mixins/mapview/SpatialIndex'

function scores(over: Partial<GroupScoreList> = {}): GroupScoreList {
    return { valueIndex: {}, min: 0, max: 1, maxIsBest: true, description: '', ...over }
}

function point(x: number, y = 0) {
    return { x, y, opacity: 1 } as PointData
}

describe('scoreQuality', () => {
    it('keeps a 0-1 score as is', () => {
        assert.equal(scoreQuality(0.7, scores()), 0.7)
    })
    it('normalises to the declared range and clamps out of it', () => {
        assert.equal(scoreQuality(15, scores({ min: 10, max: 20 })), 0.5)
        assert.equal(scoreQuality(25, scores({ min: 10, max: 20 })), 1)
        assert.equal(scoreQuality(5, scores({ min: 10, max: 20 })), 0)
    })
    it('flips distances, where the lowest is the best', () => {
        assert.equal(scoreQuality(0, scores({ maxIsBest: false })), 1)
        assert.equal(scoreQuality(1, scores({ maxIsBest: false })), 0)
    })
})

describe('scoreBounds', () => {
    it('spans the scores present and skips points without one', () => {
        assert.deepEqual(scoreBounds([0.6, NaN, 0.9, 0.5]), { min: 0.5, max: 0.9 })
    })
    it('is null without any score', () => {
        assert.equal(scoreBounds([]), null)
        assert.equal(scoreBounds([NaN]), null)
    })
})

describe('effectiveThreshold', () => {
    const bounds = { min: 0.5, max: 0.9 }
    it('leaves a threshold in bounds', () => {
        assert.equal(effectiveThreshold(0.7, bounds), 0.7)
    })
    it('starts halfway through the scores', () => {
        assert.equal(effectiveThreshold(undefined, { min: 0.5, max: 1 }), 0.75)
    })
    it('clamps up to the lowest score', () => {
        assert.equal(effectiveThreshold(0, bounds), 0.5)
    })
    it('keeps the best images when a previous search left it above them', () => {
        assert.equal(effectiveThreshold(0.95, bounds), 0.9)
    })
    it('has nothing to clamp to without scores', () => {
        assert.equal(effectiveThreshold(0.7, null), 0)
    })
})

describe('applyScoreThreshold', () => {
    it('keeps the points at or above the threshold', () => {
        const pts = [point(0), point(1), point(2)]
        assert.equal(applyScoreThreshold(pts, Float64Array.of(0.4, 0.7, 0.9), 0.7), 2)
        assert.deepEqual(pts.map(isPointHidden), [true, false, false])
    })
    it('hides a point without a score at any threshold', () => {
        const pts = [point(0)]
        assert.equal(applyScoreThreshold(pts, [NaN], 0), 0)
        assert.equal(isPointHidden(pts[0]), true)
    })
    it('brings points back when the threshold drops', () => {
        const pts = [point(0)]
        applyScoreThreshold(pts, [0.5], 0.8)
        applyScoreThreshold(pts, [0.5], 0.3)
        assert.equal(pts[0].opacity, 1)
    })
})

describe('SpatialIndex and hidden points', () => {
    it('leaves them out of queries, and returns them once visible again', () => {
        const pts = [point(0), point(1)]
        const index = new SpatialIndex()
        index.initTree(pts)
        const rect = { minX: -1, minY: -1, maxX: 2, maxY: 1 }
        applyScoreThreshold(pts, [0.2, 0.8], 0.5)
        assert.deepEqual(index.getPointsInRect(rect), [pts[1]])
        applyScoreThreshold(pts, [0.2, 0.8], 0.1)
        assert.equal(index.getPointsInRect(rect).length, 2)
    })
})
