import * as THREE from 'three'
import KDBush from 'kdbush'
import simplify from 'simplify'
import { getBoundingRect } from '@/utils/utils'
import classifyPoint from 'robust-point-in-polygon'
import { PointData } from './useMapLogic'
import { PointIndex } from '@/data/models'
import { SpatialIndex } from './SpatialIndex'

interface ScreenPoint {
    x: number
    y: number
}

export class LassoLayer {
    private scene: THREE.Scene
    private spatialIndex: SpatialIndex
    private onLassoComplete: (points: PointData[]) => void
    
    private lassoPoints: THREE.Vector3[] = []
    private lastScreenPos: ScreenPoint | null = null
    private lassoMesh: THREE.Mesh | null = null
    private lassoLine: THREE.Line | null = null
    private clearTimeoutId: number | null = null
    
    // Visual Config
    private readonly FILL_COLOR = 0x00aaff
    private readonly FILL_OPACITY = 0.3
    private readonly STROKE_COLOR = 0x0077cc
    
    // Smoothing & Filtering Config
    private readonly MIN_PIXEL_DIST_SQ = 100 // 10 pixels squared
    private readonly CURVE_TENSION = 0.5
    private readonly SMOOTHNESS_MULTIPLIER = 10

    constructor(
        scene: THREE.Scene,
        spatialIndex: SpatialIndex,
        onLassoComplete: (points: PointData[]) => void
    ) {
        this.scene = scene
        this.spatialIndex = spatialIndex
        this.onLassoComplete = onLassoComplete
    }

    /**
     * Initializes the Three.js mesh and line objects if they don't exist.
     */
    private initMesh() {
        if (!this.lassoMesh) {
            const material = new THREE.MeshBasicMaterial({
                color: this.FILL_COLOR,
                transparent: true,
                opacity: this.FILL_OPACITY,
                side: THREE.DoubleSide,
                depthTest: false,
            })
            this.lassoMesh = new THREE.Mesh(new THREE.BufferGeometry(), material)
            this.lassoMesh.renderOrder = 999
            this.scene.add(this.lassoMesh)
        }

        if (!this.lassoLine) {
            const material = new THREE.LineBasicMaterial({
                color: this.STROKE_COLOR,
                depthTest: false
            })
            this.lassoLine = new THREE.Line(new THREE.BufferGeometry(), material)
            this.lassoLine.renderOrder = 999
            this.scene.add(this.lassoLine)
        }
    }

    /**
     * Starts a new lasso drawing sequence.
     */
    public start(worldPoint: THREE.Vector3, screenPoint: ScreenPoint) {
        if (this.clearTimeoutId) {
            clearTimeout(this.clearTimeoutId)
            this.clearTimeoutId = null
        }

        this.initMesh()

        this.lassoPoints = [worldPoint]
        this.lastScreenPos = screenPoint

        if (this.lassoMesh) this.lassoMesh.visible = true
        if (this.lassoLine) this.lassoLine.visible = true

        this.updateGeometry()
    }

    /**
     * Records a new point only if the mouse has moved a sufficient distance in screen space.
     */
    public move(worldPoint: THREE.Vector3, screenPoint: ScreenPoint) {
        if (this.lassoPoints.length === 0 || !this.lastScreenPos) return

        // Screen-space distance check
        const dx = screenPoint.x - this.lastScreenPos.x
        const dy = screenPoint.y - this.lastScreenPos.y
        const distSq = dx * dx + dy * dy

        if (distSq < this.MIN_PIXEL_DIST_SQ) return

        // Valid point: add to world list and update last known screen position
        this.lassoPoints.push(worldPoint)
        this.lastScreenPos = screenPoint

        this.updateGeometry()
    }

    /**
     * Finalizes the lasso, emits the polygon data, and clears the visuals immediately.
     */
    public end() {
        if (this.lassoPoints.length < 3) {
            this.clear()
            return
        }

        // 1. Calculate the final closed smooth geometry (updates visuals)
        const finalPolygonPoints = this.updateGeometry(true)

        // 2. Emit the result to the consumer
        this.computeSelectedPoints(finalPolygonPoints)

        // 3. Clear any potential old timer
        if (this.clearTimeoutId) {
            clearTimeout(this.clearTimeoutId)
            this.clearTimeoutId = null
        }

        // 4. Immediately clear the visual elements
        this.clear()
    }

    /**
     * Generates smooth geometry using Catmull-Rom Splines and updates the meshes.
     * @param closeLoop If true, connects the last point to the first.
     * @returns The generated smooth points (World Coordinates).
     */
    private updateGeometry(closeLoop = false): THREE.Vector3[] {
        if (!this.lassoMesh || !this.lassoLine || this.lassoPoints.length === 0) return []

        let smoothPoints: THREE.Vector3[] = []

        if (this.lassoPoints.length > 2) {
            const curve = new THREE.CatmullRomCurve3(this.lassoPoints)
            curve.closed = closeLoop
            curve.curveType = 'centripetal'
            curve.tension = this.CURVE_TENSION
            const divisions = this.lassoPoints.length * this.SMOOTHNESS_MULTIPLIER
            smoothPoints = curve.getPoints(divisions)
        } else {
            smoothPoints = [...this.lassoPoints]
            if (closeLoop) smoothPoints.push(this.lassoPoints[0])
        }

        // 1. Updates for Fill (Mesh)
        const shape = new THREE.Shape()
        if (smoothPoints.length > 0) {
            shape.moveTo(smoothPoints[0].x, smoothPoints[0].y)
            for (let i = 1; i < smoothPoints.length; i++) {
                shape.lineTo(smoothPoints[i].x, smoothPoints[i].y)
            }
        }

        this.lassoMesh.geometry.dispose()
        this.lassoMesh.geometry = new THREE.ShapeGeometry(shape)

        // 2. Updates for Outline (Line)
        this.lassoLine.geometry.dispose()
        this.lassoLine.geometry = new THREE.BufferGeometry().setFromPoints(smoothPoints)

        return smoothPoints
    }

    /**
     * Clears all visual elements and resets internal state.
     */
    public clear() {
        if (this.lassoMesh) {
            this.lassoMesh.visible = false
            if (this.lassoMesh.geometry) this.lassoMesh.geometry.dispose()
        }
        if (this.lassoLine) {
            this.lassoLine.visible = false
            if (this.lassoLine.geometry) this.lassoLine.geometry.dispose()
        }
        this.lassoPoints = []
        this.lastScreenPos = null
    }

    /**
     * Computes which points fall within the lasso polygon and emits them.
     */
    private computeSelectedPoints(polygon: THREE.Vector3[]) {
        const simplifiedPolygon = simplify(polygon, 0.1)

        const rect = getBoundingRect(simplifiedPolygon)
        const pointsToTest = this.spatialIndex.getPointsInRect(rect)
        
        const formattedPolygon = simplifiedPolygon.map(p => [p.x, p.y])
        const selectedPoints = pointsToTest.filter(p => 
            classifyPoint(formattedPolygon, [p.x, p.y]) <= 0
        )
        
        this.onLassoComplete(selectedPoints)
    }

    /**
     * Updates the reference to the spatial tree and points array.
     * Call this when the data changes.
     */
    // public updateData(tree: KDBush, points: PointData[]) {
    //     this.tree = tree
    //     this.points = points
    // }

    /**
     * Cleans up all Three.js resources and timers.
     */
    public dispose() {
        if (this.clearTimeoutId) clearTimeout(this.clearTimeoutId)

        if (this.lassoMesh) {
            this.scene.remove(this.lassoMesh)
            if (this.lassoMesh.geometry) this.lassoMesh.geometry.dispose()
            if (this.lassoMesh.material instanceof THREE.Material) {
                this.lassoMesh.material.dispose()
            }
            this.lassoMesh = null
        }

        if (this.lassoLine) {
            this.scene.remove(this.lassoLine)
            if (this.lassoLine.geometry) this.lassoLine.geometry.dispose()
            if (this.lassoLine.material instanceof THREE.Material) {
                this.lassoLine.material.dispose()
            }
            this.lassoLine = null
        }
    }
}