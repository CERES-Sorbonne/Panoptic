import * as THREE from 'three'
import { Props } from '@/components/mapview/ImageMap.vue'
import KDBush from 'kdbush'
import simplify from 'simplify'
import { getBoundingRect } from '@/utils/utils'
import classifyPoint from 'robust-point-in-polygon'
import { PointData } from './useMapLogic'

// --- Interface Definitions ---

interface LassoLogicParams {
    scene: THREE.Scene
    props: Props,
    tree: { t: KDBush }
    updateView: () => void
    /** Callback fired when the lasso is completed, providing the resulting closed polygon points in World space. */
    onLassoComplete: (points: PointData[]) => void
}

interface ScreenPoint {
    x: number
    y: number
}

// --- Core Composable ---

export function useLassoLogic({ scene, props, tree, updateView, onLassoComplete }: LassoLogicParams) {
    let lassoPoints: THREE.Vector3[] = []
    let lastScreenPos: ScreenPoint | null = null

    let lassoMesh: THREE.Mesh | null = null
    let lassoLine: THREE.Line | null = null
    let clearTimeoutId: number | null = null

    // Visual Config
    const FILL_COLOR = 0x00aaff
    const FILL_OPACITY = 0.3
    const STROKE_COLOR = 0x0077cc

    // Smoothing & Filtering Config
    const MIN_PIXEL_DIST_SQ = 100 // 10 pixels squared: only add point if mouse moved > 10px
    const CURVE_TENSION = 0.5
    const SMOOTHNESS_MULTIPLIER = 10 // Resolution of interpolated points per raw point

    /**
     * Initializes the Three.js mesh and line objects if they don't exist.
     */
    const initMesh = () => {
        if (!lassoMesh) {
            const material = new THREE.MeshBasicMaterial({
                color: FILL_COLOR,
                transparent: true,
                opacity: FILL_OPACITY,
                side: THREE.DoubleSide,
                depthTest: false,
            })
            lassoMesh = new THREE.Mesh(new THREE.BufferGeometry(), material)
            lassoMesh.renderOrder = 999
            scene.add(lassoMesh)
        }

        if (!lassoLine) {
            const material = new THREE.LineBasicMaterial({
                color: STROKE_COLOR,
                depthTest: false
            })
            lassoLine = new THREE.Line(new THREE.BufferGeometry(), material)
            lassoLine.renderOrder = 999
            scene.add(lassoLine)
        }
    }

    /**
     * Starts a new lasso drawing sequence.
     */
    const start = (worldPoint: THREE.Vector3, screenPoint: ScreenPoint) => {
        if (clearTimeoutId) {
            clearTimeout(clearTimeoutId)
            clearTimeoutId = null
        }

        initMesh()

        lassoPoints = [worldPoint]
        lastScreenPos = screenPoint

        if (lassoMesh) lassoMesh.visible = true
        if (lassoLine) lassoLine.visible = true

        updateGeometry()
    }

    /**
     * Records a new point only if the mouse has moved a sufficient distance in screen space.
     */
    const move = (worldPoint: THREE.Vector3, screenPoint: ScreenPoint) => {
        if (lassoPoints.length === 0 || !lastScreenPos) return

        // Screen-space distance check
        const dx = screenPoint.x - lastScreenPos.x
        const dy = screenPoint.y - lastScreenPos.y
        const distSq = dx * dx + dy * dy

        if (distSq < MIN_PIXEL_DIST_SQ) return

        // Valid point: add to world list and update last known screen position
        lassoPoints.push(worldPoint)
        lastScreenPos = screenPoint

        updateGeometry()
    }

    /**
     * Finalizes the lasso, emits the polygon data, and clears the visuals immediately.
     */
    const end = () => {
        if (lassoPoints.length < 3) {
            clearLasso()
            return
        }

        // 1. Calculate the final closed smooth geometry (updates visuals)
        const finalPolygonPoints = updateGeometry(true)

        // 2. Emit the result to the consumer
        computeSelectedPoints(finalPolygonPoints)

        // 3. Clear any potential old timer
        if (clearTimeoutId) {
            clearTimeout(clearTimeoutId)
            clearTimeoutId = null
        }

        // 4. Immediately clear the visual elements
        clearLasso()

        // 5. Force a render update
        updateView()
    }

    /**
     * Generates smooth geometry using Catmull-Rom Splines and updates the meshes.
     * @param closeLoop If true, connects the last point to the first.
     * @returns The generated smooth points (World Coordinates).
     */
    const updateGeometry = (closeLoop = false): THREE.Vector3[] => {
        if (!lassoMesh || !lassoLine || lassoPoints.length === 0) return []

        let smoothPoints: THREE.Vector3[] = []

        if (lassoPoints.length > 2) {
            const curve = new THREE.CatmullRomCurve3(lassoPoints)
            curve.closed = closeLoop
            curve.curveType = 'centripetal'
            curve.tension = CURVE_TENSION
            const divisions = lassoPoints.length * SMOOTHNESS_MULTIPLIER
            smoothPoints = curve.getPoints(divisions)
        } else {
            smoothPoints = [...lassoPoints]
            if (closeLoop) smoothPoints.push(lassoPoints[0])
        }

        // 1. Updates for Fill (Mesh)
        const shape = new THREE.Shape()
        if (smoothPoints.length > 0) {
            shape.moveTo(smoothPoints[0].x, smoothPoints[0].y)
            for (let i = 1; i < smoothPoints.length; i++) {
                shape.lineTo(smoothPoints[i].x, smoothPoints[i].y)
            }
        }

        lassoMesh.geometry.dispose()
        lassoMesh.geometry = new THREE.ShapeGeometry(shape)

        // 2. Updates for Outline (Line)
        lassoLine.geometry.dispose()
        lassoLine.geometry = new THREE.BufferGeometry().setFromPoints(smoothPoints)

        updateView()

        return smoothPoints
    }

    /**
     * Clears all visual elements and resets internal state.
     */
    const clearLasso = () => {
        if (lassoMesh) {
            lassoMesh.visible = false
            // Dispose geometry to prevent memory leak
            if (lassoMesh.geometry) lassoMesh.geometry.dispose()
        }
        if (lassoLine) {
            lassoLine.visible = false
            // Dispose geometry to prevent memory leak
            if (lassoLine.geometry) lassoLine.geometry.dispose()
        }
        lassoPoints = []
        lastScreenPos = null
    }

    /**
     * Cleans up all Three.js resources and timers.
     */
    const cleanup = () => {
        if (clearTimeoutId) clearTimeout(clearTimeoutId)

        if (lassoMesh) {
            scene.remove(lassoMesh)
            if (lassoMesh.geometry) lassoMesh.geometry.dispose()
            if (lassoMesh.material instanceof THREE.Material) lassoMesh.material.dispose()
        }

        if (lassoLine) {
            scene.remove(lassoLine)
            if (lassoLine.geometry) lassoLine.geometry.dispose()
            if (lassoLine.material instanceof THREE.Material) lassoLine.material.dispose()
        }
    }

    function computeSelectedPoints(polygon) {
        polygon = simplify(polygon, 0.1)

        const rect = getBoundingRect(polygon)
        const pointIdsToTest = tree.t.range(rect.minX, rect.minY, rect.maxX, rect.maxY)
        
        const pointIndex: {[pId: number]: PointData} = {}
        props.points.forEach(p => pointIndex[p.id] = p)
        const pointsToTest = pointIdsToTest.map(id => pointIndex[id])

        console.log(pointIdsToTest.length)
        const formatedPolygon = polygon.map(p => [p.x, p.y])
        let selectedPoints = pointsToTest.filter(p => classifyPoint(formatedPolygon, [p.x, p.y]) <= 0)
        onLassoComplete(selectedPoints)
    }

    return { start, move, end, cleanup }
}