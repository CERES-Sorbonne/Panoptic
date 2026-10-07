import * as THREE from 'three'
import { useDataStore } from '@/data/stores/dataStore'
import { MapControls } from './MapControl'
import { ImageAtlas, PointData, ZoomParams } from '@/data/models'
import { SpatialIndex } from './SpatialIndex'
import { HDLayer } from './HDLayer'
import { DetailLayer, MAX_DETAIL_TILES } from './DetailLayer'
import { HoverPointLayer } from './HoverPointLayer'
import { AtlasLayerManager } from './AtlasLayerManager'
import { LassoLayer } from './LassoLayer'
import { SnakeLayer } from './SnakeLayer'
import { deepCopy, EventEmitter } from '@/utils/utils'
import { useColumnStore } from '@/data/stores/columnStore'

// Side of the square a thumbnail always fits in, in world units (its largest size, at low zoom).
export function imageWorldSize(imageSize: number) {
    return imageSize / 50.0
}

export class MapRenderer {
    private container: HTMLElement
    private scene: THREE.Scene
    private camera!: THREE.OrthographicCamera
    private renderer!: THREE.WebGLRenderer
    private controls!: MapControls
    private requestID: number | null = null
    private resizeObserver: ResizeObserver
    private frustumSize = 20

    private zoomParams: ZoomParams = { h: 5.0, z1: 0.1, z2: 0.11 }
    // Grid with square thumbnails: each one fills its whole cell, with no gap to its neighbours.
    private fillCells = false

    public atlasLayers: AtlasLayerManager
    private hdLayer: HDLayer
    private detailLayer: DetailLayer
    // Sharper images over the thumbnails when zoomed in. Only in the grid, where images never
    // overlap: in the scatter a tile would cover the neighbours drawn in front of its thumbnail.
    private detailEnabled = false
    // Camera state the detail view was last computed for.
    private detailViewKey = ''
    private hoverPointLayer: HoverPointLayer
    private lassoLayer: LassoLayer
    public snakeLayer: SnakeLayer
    // Off while the snake easter egg runs, so the HD preview never covers the board.
    private hoverEnabled = true
    // World point the camera glides towards each frame (the snake's head), if any.
    private follow: { x: number, y: number } | null = null
    private spatialIndex = new SpatialIndex()
    

    private globalUniforms = {
        uZoom: { value: 1.0 }
    }

    public onPointSelection: ((points: PointData[]) => void) | null = null

    public onHover = new EventEmitter()

    // In point mode, points are plain coloured dots with no detail to magnify — the side-panel
    // inspector (fed by onHover below) already shows the hovered image, so the enlarged HD
    // preview would just be a redundant floating photo. Suppress it there.
    private showAsPoint = false

    constructor(container: HTMLElement, baseImgUrl: string) {
        this.container = container
        this.scene = new THREE.Scene()
        this.scene.background = new THREE.Color(0xFFFFFF)

        this.initCamera()
        this.initRenderer()

        this.atlasLayers = new AtlasLayerManager(this.scene)
        this.atlasLayers.setZoomParams(this.activeZoomParams())

        this.hdLayer = new HDLayer(this.scene, baseImgUrl)
        this.hdLayer.setZoomReference(this.globalUniforms.uZoom)
        this.hdLayer.setZoomParams(this.activeZoomParams())

        this.detailLayer = new DetailLayer(this.scene, baseImgUrl)
        this.detailLayer.setZoomReference(this.globalUniforms.uZoom)
        this.detailLayer.setZoomParams(this.activeZoomParams())

        this.hoverPointLayer = new HoverPointLayer(this.scene)
        this.hoverPointLayer.setZoomReference(this.globalUniforms.uZoom)
        this.hoverPointLayer.setZoomParams(this.activeZoomParams())

        this.lassoLayer = new LassoLayer(this.scene, this.spatialIndex, (points) => {
            if (this.onPointSelection) this.onPointSelection(points)
        })

        this.snakeLayer = new SnakeLayer(this.scene)

        this.controls = new MapControls(this.camera, this.renderer.domElement, this.lassoLayer, this.spatialIndex)

        this.resizeObserver = new ResizeObserver(() => this.onResize())
        this.resizeObserver.observe(this.container)
    }

    private initCamera() {
        const aspect = this.container.clientWidth / this.container.clientHeight
        this.camera = new THREE.OrthographicCamera(
            (this.frustumSize * aspect) / -2,
            (this.frustumSize * aspect) / 2,
            this.frustumSize / 2,
            this.frustumSize / -2,
            0.1,
            1000
        )
        this.camera.position.z = 10
        this.camera.zoom = 0.08
        this.camera.updateProjectionMatrix()
        this.globalUniforms.uZoom.value = this.camera.zoom
    }

    private initRenderer() {
        this.renderer = new THREE.WebGLRenderer({
            antialias: true,
            alpha: false,
            powerPreference: "high-performance",
        })
        this.renderer.setPixelRatio(this.targetPixelRatio())
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight)
        this.renderer.outputColorSpace = THREE.SRGBColorSpace
        this.renderer.setClearColor(0xffffff, 1)
        this.container.appendChild(this.renderer.domElement)
    }

    private targetPixelRatio() {
        return Math.min(window.devicePixelRatio, 2)
    }

    // devicePixelRatio changes when the window moves between screens (e.g. FHD -> 4K) or the
    // browser zoom changes, without the container resizing. A stale ratio makes the browser
    // upscale the canvas, which blurs everything, so re-check it every frame (cheap read).
    private syncPixelRatio() {
        const ratio = this.targetPixelRatio()
        if (this.renderer.getPixelRatio() !== ratio) this.renderer.setPixelRatio(ratio)
    }

    public async createMap(atlas: ImageAtlas, points: PointData[], showAsPoint: boolean) {
        const dataStore = useDataStore()
        this.spatialIndex.initTree(points)
        this.showAsPoint = showAsPoint
        this.detailLayer.setMap(atlas.cellWidth)
        this.invalidateDetail()

        await this.atlasLayers.loadLayers(
            atlas,
            points,
            dataStore.baseUrl,
            this.globalUniforms.uZoom,
            showAsPoint
        )
    }

    public animate() {
        this.requestID = requestAnimationFrame(() => this.animate())

        if (this.globalUniforms.uZoom.value !== this.camera.zoom) {
            this.globalUniforms.uZoom.value = this.camera.zoom
        }

        if (this.hdLayer) {
            this.hdLayer.updateAnimations()
            this.hdLayer.tick()
        }
        this.hoverPointLayer.updateAnimations()
        const view = this.getCameraRect()
        this.snakeLayer.tick(performance.now(), view, (view.maxX - view.minX) / Math.max(1, this.container.clientWidth))
        if (this.follow) {
            this.camera.position.x += (this.follow.x - this.camera.position.x) * 0.12
            this.camera.position.y += (this.follow.y - this.camera.position.y) * 0.12
        }

        this.updateHoverState()
        this.syncPixelRatio()
        this.updateDetailView()
        this.detailLayer.tick()
        // console.log(this.controls.getMouseWorldPos())
        // console.log(this.camera.zoom)
        this.renderer.render(this.scene, this.camera)
    }

    private invalidateDetail() {
        this.detailViewKey = ''
    }

    // Recomputes which images get a detail tile when the camera or the canvas changed.
    private updateDetailView() {
        const imageSize = this.getImageMaxSize()
        const pixelRatio = this.renderer.getPixelRatio()
        const { clientWidth, clientHeight } = this.container
        const { zoom, position } = this.camera
        const key = `${zoom},${position.x},${position.y},${clientWidth},${clientHeight},${pixelRatio},${imageSize}`
        if (key === this.detailViewKey) return
        this.detailViewKey = key

        // Longest side of a thumbnail on screen, in device px.
        const pixelSize = imageSize * zoom * clientHeight / this.frustumSize * pixelRatio
        if (!this.detailEnabled || this.showAsPoint || !this.detailLayer.wantsDetail(pixelSize)) {
            this.detailLayer.setView([], 0)
            return
        }
        // Thumbnails are at least this big on screen, so the query returns a few thousand
        // points at most.
        const rect = this.getCameraRect()
        const half = imageSize / 2
        const points = this.spatialIndex.getPointsInRect({
            minX: rect.minX - half, maxX: rect.maxX + half,
            minY: rect.minY - half, maxY: rect.maxY + half
        })
        if (points.length > MAX_DETAIL_TILES) {
            this.detailLayer.setView([], 0)
            return
        }
        const dist = (p: PointData) => (p.x - position.x) ** 2 + (p.y - position.y) ** 2
        points.sort((a, b) => dist(a) - dist(b))
        this.detailLayer.setView(points, pixelSize)
    }

    public setDetailEnabled(enabled: boolean) {
        this.detailEnabled = enabled
        this.invalidateDetail()
    }

    private updateHoverState() {
        const foundPoint = this.hoverEnabled ? this.controls.getHoveredPoint(this.activeZoomParams()) : null

        if (foundPoint) {
            const instanceId = useColumnStore().getInstancesBySha1(foundPoint.sha1)[0]
            if (this.showAsPoint) {
                this.hoverPointLayer.hover(foundPoint)
            } else {
                this.hdLayer.hover(foundPoint)
            }
            this.onHover.emit(instanceId)
        } else {
            this.hdLayer.unhover()
            this.hoverPointLayer.unhover()
            this.onHover.emit()
        }
    }

    public setFollow(target: { x: number, y: number } | null) {
        this.follow = target
    }

    public setHoverEnabled(value: boolean) {
        this.hoverEnabled = value
    }

    public setHoverThroughOverlays(value: boolean) {
        this.controls.hoverThroughOverlays = value
    }

    public setMouseMode(mode: string) {
        this.controls.setMode(mode)
    }

    public updateTints() {
        this.atlasLayers.updateTints()
        this.hdLayer.updateTints()
        this.detailLayer.updateStyles()
    }

    // Grid-thumbnail-only effect (the HD hover preview always shows a point in full colour).
    public updateDesaturation() {
        this.atlasLayers.updateDesaturation()
        this.detailLayer.updateStyles()
    }

    public updateBorder() {
        this.atlasLayers.updateBorder()
        this.hdLayer.updateBorder()
        this.detailLayer.updateStyles()
    }

    public setHoverScale(scale: number) {
        this.hdLayer.setHoverScale(scale)
    }

    public updatePosition() {
        this.atlasLayers.updatePositions()
        this.detailLayer.updatePositions()
    }

    // Points moved (layout switch, grid rescale): re-index them and re-upload their positions.
    public updateLayout(points: PointData[]) {
        this.spatialIndex.initTree(points)
        this.atlasLayers.updatePositions()
        this.hdLayer.updatePositions()
        this.invalidateDetail()
    }

    public getPointsInView(): PointData[] {
        return this.spatialIndex.getPointsInRect(this.getCameraRect())
    }

    // Keeps the same world point under the screen centre when the whole layout is scaled about
    // the origin.
    public scaleCameraPosition(factor: number) {
        this.camera.position.x *= factor
        this.camera.position.y *= factor
    }

    public setFillCells(fill: boolean) {
        this.fillCells = fill
        this.atlasLayers.setFill(fill)
        this.detailLayer.setFill(fill)
        this.controls.fillCells = fill
        this.pushZoomParams()
    }

    public setShowAsPoint(show: boolean) {
        this.showAsPoint = show
        // Toggled mid-hover: drop whatever preview is currently up for the mode we're leaving
        // rather than leaving it stranded until the mouse moves off the point.
        if (show) this.hdLayer.unhover()
        else this.hoverPointLayer.unhover()
        this.atlasLayers.setShowAsPoint(show)
        this.invalidateDetail()
    }

    public setImageSize(imageSize: number) {
        this.zoomParams.h = imageWorldSize(imageSize)
        this.pushZoomParams()
    }

    // Thumbnails shrink from h to h * z1/z2 as the camera zooms in, so scattered images overlap
    // less. Filled grid cells must keep their full size to tile, so z2 = z1 cancels the shrink
    // (the border scale only reads z1 and is unchanged).
    private activeZoomParams(): ZoomParams {
        const { h, z1, z2 } = this.zoomParams
        return { h, z1, z2: this.fillCells ? z1 : z2 }
    }

    private pushZoomParams() {
        const params = this.activeZoomParams()
        this.hdLayer.setZoomParams(params)
        this.hoverPointLayer.setZoomParams(params)
        this.atlasLayers.setZoomParams(params)
        this.detailLayer.setZoomParams(params)
        this.invalidateDetail()
    }

    private onResize() {
        const aspect = this.container.clientWidth / this.container.clientHeight
        this.camera.left = (this.frustumSize * aspect) / -2
        this.camera.right = (this.frustumSize * aspect) / 2
        this.camera.top = this.frustumSize / 2
        this.camera.bottom = this.frustumSize / -2
        this.camera.updateProjectionMatrix()
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight)
    }

    public getImageMaxSize(): number {
        const currentZoom = this.camera.zoom;
        const { h, z1, z2 } = this.activeZoomParams();

        let zoomScale: number;

        // 1. Replicate the zoomScale conditional logic from the Vertex Shader
        if (currentZoom >= z1 && currentZoom < z2) {
            // Linear scaling based on zoom ratio
            zoomScale = h * (z1 / currentZoom);
        } else if (currentZoom >= z2) {
            // Fixed scale cap at z2
            zoomScale = h * (z1 / z2);
        } else {
            // Default height when zoom is low (uZoom < z1)
            zoomScale = h;
        }

        return zoomScale;
    }

    public getCameraRect() {
        const zoom = this.camera.zoom
        return {
            minX: (this.camera.left / zoom) + this.camera.position.x,
            maxX: (this.camera.right / zoom) + this.camera.position.x,
            minY: (this.camera.bottom / zoom) + this.camera.position.y,
            maxY: (this.camera.top / zoom) + this.camera.position.y
        }
    }

    public lookAtRect(
        rect: { minX: number, minY: number, maxX: number, maxY: number },
        padding?: { left?: number, right?: number, top?: number, bottom?: number }
    ) {
        let offset = this.getImageMaxSize()
        let finalRect = deepCopy(rect)
        finalRect.minX -= offset
        finalRect.minY -= offset
        finalRect.maxX += offset
        finalRect.maxY += offset
        this.controls.lookAtRect(finalRect, 500, padding)
    }

    public dispose() {
        if (this.requestID) cancelAnimationFrame(this.requestID)
        this.resizeObserver.disconnect()
        this.controls.dispose()
        this.renderer.dispose()
        this.atlasLayers.dispose()
        this.hdLayer?.dispose()
        this.detailLayer.dispose()
        this.hoverPointLayer?.dispose()
        this.snakeLayer.dispose()
        this.scene.clear()
    }
}