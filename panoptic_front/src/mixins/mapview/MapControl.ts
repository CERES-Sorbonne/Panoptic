import * as THREE from 'three'
import { LassoLayer } from './LassoLayer'
import { SpatialIndex } from './SpatialIndex'
import { PointData, ZoomParams } from '@/data/models'

export class MapControls {
    private camera: THREE.OrthographicCamera
    private domElement: HTMLElement
    private spatialIndex: SpatialIndex

    private mode: string = 'pan'
    private isDragging = false
    private isLassoing = false
    private prevPos = { x: 0, y: 0 }
    private mouse = new THREE.Vector2()
    private animationId: number | null = null

    private lasso: LassoLayer
    public minZoom = 0.01
    public maxZoom = 20
    public zoomSpeed = 0.001

    public onUpdate: () => void = () => { }

    constructor(
        camera: THREE.OrthographicCamera, 
        domElement: HTMLElement, 
        lassoLayer: LassoLayer,
        spatialIndex: SpatialIndex
    ) {
        this.camera = camera
        this.domElement = domElement
        this.lasso = lassoLayer
        this.spatialIndex = spatialIndex
        this.init()
    }

    private init() {
        this.domElement.addEventListener('wheel', this.handleWheel, { passive: false })
        this.domElement.addEventListener('mousedown', this.handleMouseDown)
        window.addEventListener('mousemove', this.handleMouseMove)
        window.addEventListener('mouseup', this.handleMouseUp)
    }

    private handleMouseMove = (e: MouseEvent) => {
        const rect = this.domElement.getBoundingClientRect()
        this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
        this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1

        if (this.isLassoing) {
            this.lasso.move(this.getMouseWorldPos(), { x: e.clientX, y: e.clientY })
            this.onUpdate()
            return
        }

        if (this.isDragging && this.mode === 'pan') {
            const dx = e.clientX - this.prevPos.x
            const dy = e.clientY - this.prevPos.y
            const worldWidth = (this.camera.right - this.camera.left) / this.camera.zoom
            const worldHeight = (this.camera.top - this.camera.bottom) / this.camera.zoom

            this.camera.position.x -= dx * (worldWidth / rect.width)
            this.camera.position.y += dy * (worldHeight / rect.height)
            this.prevPos = { x: e.clientX, y: e.clientY }
            this.onUpdate()
        }
    }

    public getHoveredPoint(zoomParams: ZoomParams): PointData | null {
        if (this.mode.startsWith('lasso')) return null

        const worldPos = this.getMouseWorldPos()
        const currentZoom = this.camera.zoom
        const { h, z1, z2 } = zoomParams

        // Replicate shader scaling logic
        let zoomScale = h
        if (currentZoom >= z1 && currentZoom < z2) {
            zoomScale = h * (z1 / currentZoom)
        } else if (currentZoom >= z2) {
            zoomScale = h * (z1 / z2)
        }

        const nearbyPoints = this.spatialIndex.getPointsInRect({
            minX: worldPos.x - zoomScale,
            maxX: worldPos.x + zoomScale,
            minY: worldPos.y - zoomScale,
            maxY: worldPos.y + zoomScale
        })

        // Sort by distance to find top-most/closest
        nearbyPoints.sort((a, b) => {
            const distA = Math.pow(a.x - worldPos.x, 2) + Math.pow(a.y - worldPos.y, 2)
            const distB = Math.pow(b.x - worldPos.x, 2) + Math.pow(b.y - worldPos.y, 2)
            return distA - distB
        })

        for (const p of nearbyPoints) {
            const vW = p.ratio > 1.0 ? 1.0 : p.ratio
            const vH = p.ratio > 1.0 ? 1.0 / p.ratio : 1.0
            const halfW = (vW * zoomScale) / 2.0
            const halfH = (vH * zoomScale) / 2.0

            if (worldPos.x >= p.x - halfW && worldPos.x <= p.x + halfW &&
                worldPos.y >= p.y - halfH && worldPos.y <= p.y + halfH) {
                return p
            }
        }
        return null
    }

    private handleWheel = (e: WheelEvent) => {
        e.preventDefault()
        const before = this.getMouseWorldPos()
        const zoomAmount = e.deltaY * -this.zoomSpeed * this.camera.zoom
        this.camera.zoom = Math.max(this.minZoom, Math.min(this.maxZoom, this.camera.zoom + zoomAmount))
        this.camera.updateProjectionMatrix()

        const after = this.getMouseWorldPos()
        this.camera.position.x += before.x - after.x
        this.camera.position.y += before.y - after.y
        this.onUpdate()
    }

    private handleMouseDown = (e: MouseEvent) => {
        if (this.mode.startsWith('lasso')) {
            this.isLassoing = true
            this.lasso.start(this.getMouseWorldPos(), { x: e.clientX, y: e.clientY })
        } else if (this.mode === 'pan') {
            this.isDragging = true
            this.prevPos = { x: e.clientX, y: e.clientY }
        }
        this.updateCursor()
        this.onUpdate()
    }

    private handleMouseUp = () => {
        if (this.isLassoing) {
            this.isLassoing = false
            this.lasso.end()
        }
        this.isDragging = false
        this.updateCursor()
        this.onUpdate()
    }

    public setMode(mode: string) {
        if (this.isLassoing) this.lasso.clear()
        this.isLassoing = false
        this.isDragging = false
        this.mode = mode
        this.updateCursor()
    }

    public getMode() { return this.mode }

    private updateCursor() {
        if (this.isLassoing || this.mode.startsWith('lasso')) this.domElement.style.cursor = 'crosshair'
        else if (this.isDragging) this.domElement.style.cursor = 'grabbing'
        else if (this.mode === 'pan') this.domElement.style.cursor = 'grab'
        else this.domElement.style.cursor = 'default'
    }

    public getMouseWorldPos(): THREE.Vector3 {
        const worldPos = new THREE.Vector3()
        const worldWidth = (this.camera.right - this.camera.left) / this.camera.zoom
        const worldHeight = (this.camera.top - this.camera.bottom) / this.camera.zoom
        worldPos.x = this.camera.position.x + (this.mouse.x * worldWidth) / 2
        worldPos.y = this.camera.position.y + (this.mouse.y * worldHeight) / 2
        return worldPos
    }

    

public lookAtRect(rect: { minX: number, minY: number, maxX: number, maxY: number }, duration: number = 500) {
    // 1. Calculate Target Position and Zoom
    const centerX = (rect.minX + rect.maxX) / 2
    const centerY = (rect.minY + rect.maxY) / 2
    const rectWidth = rect.maxX - rect.minX
    const rectHeight = rect.maxY - rect.minY

    const viewWidth = this.camera.right - this.camera.left
    const viewHeight = this.camera.top - this.camera.bottom

    const zoomX = viewWidth / rectWidth
    const zoomY = viewHeight / rectHeight
    
    // Calculate final targets
    const targetZoom = Math.max(this.minZoom, Math.min(this.maxZoom, Math.min(zoomX, zoomY) * 0.9)) // 0.9 for some padding
    const targetPos = new THREE.Vector3(centerX, centerY, this.camera.position.z)

    // 2. Capture Starting State
    const startPos = this.camera.position.clone()
    const startZoom = this.camera.zoom
    const startTime = performance.now()

    // 3. Cancel any existing animation
    if (this.animationId) cancelAnimationFrame(this.animationId)

    const animate = (currentTime: number) => {
        const elapsed = currentTime - startTime
        const progress = Math.min(elapsed / duration, 1)

        // 4. Easing function (Optional but recommended: Ease-Out-Cubic)
        const ease = 1 - Math.pow(1 - progress, 3)

        // 5. Interpolate Position
        this.camera.position.lerpVectors(startPos, targetPos, ease)

        // 6. Interpolate Zoom
        this.camera.zoom = startZoom + (targetZoom - startZoom) * ease
        
        this.camera.updateProjectionMatrix()
        this.onUpdate()

        if (progress < 1) {
            this.animationId = requestAnimationFrame(animate)
        } else {
            this.animationId = null
        }
    }

    this.animationId = requestAnimationFrame(animate)
}

    public dispose() {
        this.domElement.removeEventListener('wheel', this.handleWheel)
        this.domElement.removeEventListener('mousedown', this.handleMouseDown)
        window.removeEventListener('mousemove', this.handleMouseMove)
        window.removeEventListener('mouseup', this.handleMouseUp)
    }
}