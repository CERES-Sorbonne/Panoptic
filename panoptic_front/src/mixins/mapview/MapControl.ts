import * as THREE from 'three'
import { LassoLayer } from './LassoLayer'
import { SpatialIndex } from './SpatialIndex'
import { PointData, ZoomParams } from '@/data/models'
import { keyState } from '@/data/composables/keyState'
import { isCellTool } from './GridBrush'

// Wheel delta (px) per brush size step: one notch of a mouse wheel.
const BRUSH_WHEEL_STEP = 100
// Some platforms fire contextmenu on mouseup, possibly over an overlay: it stays blocked this long
// after a right-button gesture.
const CONTEXT_MENU_GRACE_MS = 300

export class MapControls {
    private camera: THREE.OrthographicCamera
    private domElement: HTMLElement
    private spatialIndex: SpatialIndex

    private mode: string = 'pan'
    private isDragging = false
    private isLassoing = false
    private isBrushing = false
    // Space held: a press drags the map whatever the mode.
    private spaceHeld = false
    private brushWheel = 0
    private rightGestureUntil = 0
    private prevPos = { x: 0, y: 0 }
    private mouse = new THREE.Vector2()
    private animationId: number | null = null
    private isMouseInCanvas = false // Track if mouse is inside the canvas

    private lasso: LassoLayer
    public minZoom = 0.002
    public maxZoom = 20
    public zoomSpeed = 0.001

    public onUpdate: () => void = () => { }
    // A pan-mode press released without moving the camera.
    public onClick: () => void = () => { }
    // Cell tools ('cells', 'paint'): left press adds, right press removes, Shift draws a rectangle.
    public onBrushStart: (world: THREE.Vector3, remove: boolean, rect: boolean) => void = () => { }
    public onBrushMove: (world: THREE.Vector3, rect: boolean) => void = () => { }
    public onBrushEnd: () => void = () => { }
    public onBrushCancel: () => void = () => { }
    public onBrushResize: (dir: 1 | -1) => void = () => { }
    private downPos = { x: 0, y: 0 }

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
        this.domElement.addEventListener('mouseenter', this.handleMouseEnter)
        this.domElement.addEventListener('mouseleave', this.handleMouseLeave)
        window.addEventListener('contextmenu', this.handleContextMenu, true)
        window.addEventListener('mousemove', this.handleMouseMove)
        window.addEventListener('mouseup', this.handleMouseUp)
        window.addEventListener('keydown', this.handleKeyDown)
        window.addEventListener('keyup', this.handleKeyUp)
        window.addEventListener('blur', this.handleBlur)
    }

    // Right click removes in the lasso and cell tools. Firefox still opens its menu on
    // Shift + right click: it never sends that one to the page.
    private handleContextMenu = (e: MouseEvent) => {
        const overCanvas = e.target instanceof Node && this.domElement.contains(e.target)
        if (this.isLassoing || this.isBrushing || performance.now() < this.rightGestureUntil
            || (overCanvas && this.usesRightButton())) e.preventDefault()
    }

    private usesRightButton() {
        return isCellTool(this.mode) || this.mode === 'lasso'
    }

    private handleKeyDown = (e: KeyboardEvent) => {
        if (e.code !== 'Space' || isTyping(e)) return
        // Keeps the page from scrolling and a focused button from firing.
        if (this.isMouseInCanvas || this.isDragging) e.preventDefault()
        if (this.spaceHeld) return
        this.spaceHeld = true
        this.updateCursor()
    }

    private handleKeyUp = (e: KeyboardEvent) => {
        if (e.code !== 'Space' || !this.spaceHeld) return
        this.spaceHeld = false
        this.updateCursor()
    }

    private handleBlur = () => {
        this.spaceHeld = false
        this.updateCursor()
    }

    private handleMouseEnter = () => {
        this.isMouseInCanvas = true
    }

    private handleMouseLeave = () => {
        this.isMouseInCanvas = false
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

        if (this.isBrushing) {
            this.onBrushMove(this.getMouseWorldPos(), e.shiftKey)
            this.onUpdate()
            return
        }

        if (this.isDragging) {
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

    // When set, hover keeps following the cursor while something covers the canvas (the Ctrl
    // zoom overlay): that overlay fires the canvas's mouseleave, which would otherwise drop the
    // hovered point and with it the overlay itself. The cursor still has to be over the canvas.
    public hoverThroughOverlays = false
    // Thumbnails are square crops (AtlasLayer fill), so the hit box is the full square.
    public fillCells = false

    public getHoveredPoint(zoomParams: ZoomParams): PointData | null {
        if (this.mode.startsWith('lasso')) return null
        
        if (!this.isOverCanvas()) return null

        const worldPos = this.getMouseWorldPos()
        const zoomScale = this.zoomScale(zoomParams)

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
            if (this.contains(p, worldPos, zoomScale)) return p
        }
        return null
    }

    public isOverCanvas() {
        return this.isMouseInCanvas || (this.hoverThroughOverlays
            && Math.abs(this.mouse.x) <= 1 && Math.abs(this.mouse.y) <= 1)
    }

    // Whether the cursor is over the point's thumbnail, grown by `scale` (the hover preview).
    public isMouseOver(p: PointData, zoomParams: ZoomParams, scale = 1): boolean {
        if (this.mode.startsWith('lasso') || !this.isOverCanvas()) return false
        return this.contains(p, this.getMouseWorldPos(), this.zoomScale(zoomParams) * scale)
    }

    // Replicates the shader's thumbnail size at the current zoom.
    private zoomScale({ h, z1, z2 }: ZoomParams) {
        const currentZoom = this.camera.zoom
        if (currentZoom >= z2) return h * (z1 / z2)
        if (currentZoom >= z1) return h * (z1 / currentZoom)
        return h
    }

    private contains(p: PointData, pos: { x: number, y: number }, size: number) {
        const ratio = this.fillCells ? 1.0 : p.ratio
        const halfW = (ratio > 1.0 ? 1.0 : ratio) * size / 2.0
        const halfH = (ratio > 1.0 ? 1.0 / ratio : 1.0) * size / 2.0
        return Math.abs(pos.x - p.x) <= halfW && Math.abs(pos.y - p.y) <= halfH
    }

    private handleWheel = (e: WheelEvent) => {
        e.preventDefault()
        // keyState.ctrl follows the real key: a trackpad pinch sends ctrlKey wheel events without
        // it, and keeps zooming.
        if (isCellTool(this.mode) && keyState.ctrl) {
            this.brushWheel += e.deltaMode === WheelEvent.DOM_DELTA_LINE ? e.deltaY * 33 : e.deltaY
            if (Math.abs(this.brushWheel) >= BRUSH_WHEEL_STEP) {
                this.onBrushResize(this.brushWheel < 0 ? 1 : -1)
                this.brushWheel = 0
            }
            return
        }
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
        if (this.isBrushing) return
        if (this.mode === 'pan' || this.spaceHeld) {
            this.isDragging = true
            this.prevPos = { x: e.clientX, y: e.clientY }
            this.downPos = { x: e.clientX, y: e.clientY }
        } else if (this.mode === 'lasso' && (e.button === 0 || e.button === 2)) {
            this.isLassoing = true
            this.lasso.start(this.getMouseWorldPos(), { x: e.clientX, y: e.clientY }, e.button === 2)
        } else if (isCellTool(this.mode) && (e.button === 0 || e.button === 2)) {
            this.isBrushing = true
            this.onBrushStart(this.getMouseWorldPos(), e.button === 2, e.shiftKey)
        }
        this.updateCursor()
        this.onUpdate()
    }

    private handleMouseUp = (e: MouseEvent) => {
        if (e.button === 2 && (this.isLassoing || this.isBrushing)) this.rightGestureUntil = performance.now() + CONTEXT_MENU_GRACE_MS
        if (this.isLassoing) {
            this.isLassoing = false
            this.lasso.end()
        }
        if (this.isBrushing) {
            this.isBrushing = false
            this.onBrushEnd()
        }
        if (this.isDragging && this.mode === 'pan' && Math.hypot(e.clientX - this.downPos.x, e.clientY - this.downPos.y) < 5) {
            this.onClick()
        }
        this.isDragging = false
        this.updateCursor()
        this.onUpdate()
    }

    public setMode(mode: string) {
        if (this.isLassoing) this.lasso.clear()
        if (this.isBrushing) this.onBrushCancel()
        this.isLassoing = false
        this.isBrushing = false
        this.isDragging = false
        this.mode = mode
        this.updateCursor()
    }

    public getMode() { return this.mode }

    private updateCursor() {
        if (this.isDragging) this.domElement.style.cursor = 'grabbing'
        else if (this.mode === 'pan' || (this.spaceHeld && !this.isLassoing && !this.isBrushing)) this.domElement.style.cursor = 'grab'
        else if (this.isLassoing || this.mode.startsWith('lasso') || isCellTool(this.mode)) this.domElement.style.cursor = 'crosshair'
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

    public panTo(x: number, y: number) {
        if (this.animationId) cancelAnimationFrame(this.animationId)
        this.animationId = null
        this.camera.position.x = x
        this.camera.position.y = y
        this.onUpdate()
    }

    public lookAtRect(
        rect: { minX: number, minY: number, maxX: number, maxY: number },
        duration: number = 500,
        // Screen-space strips (in CSS pixels) covered by floating UI — e.g. the group-list island
        // on the right — that the rect must stay clear of. Both the fit and the pan target need
        // to work off the shrunken *usable* area, not the full container.
        padding: { left?: number, right?: number, top?: number, bottom?: number } = {}
    ) {
        // 1. Calculate Target Position and Zoom
        const centerX = (rect.minX + rect.maxX) / 2
        const centerY = (rect.minY + rect.maxY) / 2
        const rectWidth = rect.maxX - rect.minX
        const rectHeight = rect.maxY - rect.minY

        const viewWidth = this.camera.right - this.camera.left
        const viewHeight = this.camera.top - this.camera.bottom

        const containerWidth = this.domElement.clientWidth
        const containerHeight = this.domElement.clientHeight
        const leftFrac = containerWidth ? (padding.left ?? 0) / containerWidth : 0
        const rightFrac = containerWidth ? (padding.right ?? 0) / containerWidth : 0
        const topFrac = containerHeight ? (padding.top ?? 0) / containerHeight : 0
        const bottomFrac = containerHeight ? (padding.bottom ?? 0) / containerHeight : 0
        const usableWidthFrac = Math.max(0.1, 1 - leftFrac - rightFrac)
        const usableHeightFrac = Math.max(0.1, 1 - topFrac - bottomFrac)

        const zoomX = (viewWidth * usableWidthFrac) / rectWidth
        const zoomY = (viewHeight * usableHeightFrac) / rectHeight

        // Calculate final targets
        const targetZoom = Math.max(this.minZoom, Math.min(this.maxZoom, Math.min(zoomX, zoomY) * 0.9)) // 0.9 for some padding

        // Shift the camera off the rect's true center so the rect lands centered in the USABLE
        // region instead — e.g. with a right-side overlay, the camera sits right of the rect so
        // the rect itself renders left of the obscured strip.
        const shiftX = (viewWidth / targetZoom) * (rightFrac - leftFrac) / 2
        const shiftY = (viewHeight / targetZoom) * (topFrac - bottomFrac) / 2
        const targetPos = new THREE.Vector3(centerX + shiftX, centerY + shiftY, this.camera.position.z)

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
        this.domElement.removeEventListener('mouseenter', this.handleMouseEnter)
        this.domElement.removeEventListener('mouseleave', this.handleMouseLeave)
        window.removeEventListener('contextmenu', this.handleContextMenu, true)
        window.removeEventListener('mousemove', this.handleMouseMove)
        window.removeEventListener('mouseup', this.handleMouseUp)
        window.removeEventListener('keydown', this.handleKeyDown)
        window.removeEventListener('keyup', this.handleKeyUp)
        window.removeEventListener('blur', this.handleBlur)
    }
}

function isTyping(e: KeyboardEvent) {
    const el = e.target as HTMLElement | null
    return !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)
}