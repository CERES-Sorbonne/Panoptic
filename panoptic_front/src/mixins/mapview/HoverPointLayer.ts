import * as THREE from 'three'
import { PointData, ZoomParams } from '@/data/models'

// Same idea as HDLayer's hover preview (a single overlay mesh, not a per-instance attribute on
// the big InstancedMesh) but far cheaper: in point mode there's no image to load or magnify, so
// this is just one small circle that grows on hover, in the point's own colour.
const SCALE_HOVER = 1.6
const LERP_FACTOR = 0.25
const ANIMATION_THRESHOLD = 0.005
// Matches AtlasLayer's point-mode dot radius (InstancedImageMaterial's `pointRadius = 0.45`,
// against a unit quad) so the overlay traces the same size before it grows.
const DOT_RADIUS = 0.45
// Same front-most band as HDLayer's HD_Z_OFFSET. Safe to reuse: the two layers are mutually
// exclusive (MapRenderer only ever hovers one or the other, based on showAsPoint).
const Z_OFFSET = 1.5

export class HoverPointLayer {
    private scene: THREE.Scene
    private geometry = new THREE.CircleGeometry(DOT_RADIUS, 24)
    private material: THREE.MeshBasicMaterial
    private mesh: THREE.Mesh
    private colorHelper = new THREE.Color()

    private zoomRef: { value: number } = { value: 1.0 }
    private zoomParams: ZoomParams = { h: 1.0, z1: 0.1, z2: 0.11 }

    private hoveredPoint: PointData | null = null
    private currentScale = 0.0
    private targetScale = 0.0

    constructor(scene: THREE.Scene) {
        this.scene = scene
        this.material = new THREE.MeshBasicMaterial({ transparent: true, depthTest: true })
        this.mesh = new THREE.Mesh(this.geometry, this.material)
        this.mesh.visible = false
        this.mesh.renderOrder = Number.MAX_SAFE_INTEGER
        this.scene.add(this.mesh)
    }

    public setZoomReference(zoomUniform: { value: number }) {
        this.zoomRef = zoomUniform
    }

    public setZoomParams(params: ZoomParams) {
        this.zoomParams = params
    }

    public hover(point: PointData) {
        this.hoveredPoint = point
        this.targetScale = SCALE_HOVER
        this.mesh.visible = true

        // Match the flat colour AtlasLayer's point-mode shader renders for this exact point
        // (mix(border, tint, tintAlpha)) so growing it doesn't also shift its colour.
        this.colorHelper.set(point.borderColor || '#000000')
        if (point.tint && point.tintAlpha) {
            this.colorHelper.lerp(new THREE.Color(point.tint), point.tintAlpha)
        }
        this.material.color.copy(this.colorHelper)
    }

    public unhover() {
        this.hoveredPoint = null
        this.targetScale = 0.0
    }

    public updateAnimations() {
        if (!this.mesh.visible) return

        const diff = this.targetScale - this.currentScale
        if (Math.abs(diff) > ANIMATION_THRESHOLD) {
            this.currentScale += diff * LERP_FACTOR
        } else {
            this.currentScale = this.targetScale
            if (this.currentScale <= 0) {
                this.mesh.visible = false
                return
            }
        }

        if (this.hoveredPoint) {
            this.mesh.position.set(this.hoveredPoint.x, this.hoveredPoint.y, Z_OFFSET)
        }

        const pointScale = (this.zoomParams.h / 10.0) / this.zoomRef.value
        const finalScale = pointScale * this.currentScale
        this.mesh.scale.set(finalScale, finalScale, 1.0)
    }

    public dispose() {
        this.scene.remove(this.mesh)
        this.geometry.dispose()
        this.material.dispose()
    }
}
