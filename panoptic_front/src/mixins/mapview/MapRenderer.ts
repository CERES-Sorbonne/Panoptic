import * as THREE from 'three'
import { useDataStore } from '@/data/dataStore'
import { MapControls } from './MapControl'
import { ImageAtlas, PointData, ZoomParams } from '@/data/models'
import { SpatialIndex } from './SpatialIndex'
import { HDLayer } from './HDLayer'
import { AtlasLayerManager } from './AtlasLayerManager'
import { LassoLayer } from './LassoLayer'

export class MapRenderer {
    private container: HTMLElement
    private scene: THREE.Scene
    private camera!: THREE.OrthographicCamera
    private renderer!: THREE.WebGLRenderer
    private controls!: MapControls
    private requestID: number | null = null
    private resizeObserver: ResizeObserver
    private frustumSize = 20

    private hoveredId: number | null = null
    private zoomParams: ZoomParams = { h: 8.0, z1: 0.05, z2: 1.0 }

    public atlasLayers: AtlasLayerManager
    private hdLayer: HDLayer
    private lassoLayer: LassoLayer
    private spatialIndex = new SpatialIndex()

    private globalUniforms = {
        uZoom: { value: 1.0 }
    }

    public onPointSelection: ((points: PointData[]) => void) | null = null

    constructor(container: HTMLElement, baseImgUrl: string) {
        this.container = container
        this.scene = new THREE.Scene()
        this.scene.background = new THREE.Color(0xFFFFFF)

        this.initCamera()
        this.initRenderer()

        this.atlasLayers = new AtlasLayerManager(this.scene)
        this.atlasLayers.setZoomParams(this.zoomParams)

        this.hdLayer = new HDLayer(this.scene, baseImgUrl)
        this.hdLayer.setZoomReference(this.globalUniforms.uZoom)
        this.hdLayer.setZoomParams(this.zoomParams)

        this.lassoLayer = new LassoLayer(this.scene, this.spatialIndex, (points) => {
            if (this.onPointSelection) this.onPointSelection(points)
        })

        this.controls = new MapControls(this.camera, this.renderer.domElement, this.lassoLayer, this.spatialIndex)

        this.resizeObserver = new ResizeObserver(() => this.onResize())
        this.resizeObserver.observe(this.container)

        this.animate()
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
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight)
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
        this.renderer.outputColorSpace = THREE.SRGBColorSpace
        this.renderer.setClearColor(0xffffff, 1)
        this.container.appendChild(this.renderer.domElement)
    }

    public async createMap(atlas: ImageAtlas, points: PointData[]) {
        const dataStore = useDataStore()
        this.spatialIndex.initTree(points)

        await this.atlasLayers.loadLayers(
            atlas,
            points,
            dataStore.baseUrl,
            this.globalUniforms.uZoom
        )
    }

    public animate() {
        this.requestID = requestAnimationFrame(() => this.animate())

        if (this.globalUniforms.uZoom.value !== this.camera.zoom) {
            this.globalUniforms.uZoom.value = this.camera.zoom
        }

        if (this.hdLayer) {
            this.hdLayer.updateAnimations()
            const rect = this.getCameraRect()
            const pointsInView = this.spatialIndex.getPointsInRect(rect)

            // HD Detail threshold
            if (this.camera.zoom > 2.0 && pointsInView.length < 100) {
                this.hdLayer.show(pointsInView)
            } else {
                this.hdLayer.show([])
            }
        }

        this.updateHoverState()
        // console.log(this.controls.getMouseWorldPos())
        this.renderer.render(this.scene, this.camera)
    }

    private updateHoverState() {
        const foundPoint = this.controls.getHoveredPoint(this.zoomParams)
        const foundId = foundPoint ? foundPoint.id! : null

        if(foundId) {
            this.hdLayer.hover(foundPoint)
        } else {
            this.hdLayer.unhover()
        }
    }

    public setMouseMode(mode: string) {
        this.controls.setMode(mode)
    }

    public updateTints() {
        this.atlasLayers.updateTints()
        this.hdLayer.updateTints()
    }

    public updateBorder() {
        this.atlasLayers.updateBorderColors()
        this.atlasLayers.updateBorderWidths()
        this.hdLayer.updateBorder()
    }

    public updatePosition() {
        this.atlasLayers.updatePositions()
    }

    public setShowAsPoint(show: boolean) {
        this.atlasLayers.setShowAsPoint(show)
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

    public getCameraRect() {
        const zoom = this.camera.zoom
        return {
            minX: (this.camera.left / zoom) + this.camera.position.x,
            maxX: (this.camera.right / zoom) + this.camera.position.x,
            minY: (this.camera.bottom / zoom) + this.camera.position.y,
            maxY: (this.camera.top / zoom) + this.camera.position.y
        }
    }

    public dispose() {
        if (this.requestID) cancelAnimationFrame(this.requestID)
        this.resizeObserver.disconnect()
        this.controls.dispose()
        this.renderer.dispose()
        this.atlasLayers.dispose()
        this.hdLayer?.dispose()
        this.scene.clear()
    }
}