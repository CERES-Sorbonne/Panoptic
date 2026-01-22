import * as THREE from 'three'
import { useDataStore } from '@/data/dataStore'
import { MapControls } from './MapControl'
import { ImageAtlas, PointData, ZoomParams } from '@/data/models'
import { SpatialIndex } from './SpatialIndex'
import { HDLayer } from './HDLayer'
import { AtlasLayerManager } from './AtlasLayerManager'
import { LassoLayer } from './LassoLayer'
import { deepCopy, EventEmitter } from '@/utils/utils'

export class MapRenderer {
    private container: HTMLElement
    private scene: THREE.Scene
    private camera!: THREE.OrthographicCamera
    private renderer!: THREE.WebGLRenderer
    private controls!: MapControls
    private requestID: number | null = null
    private resizeObserver: ResizeObserver
    private frustumSize = 20

    private zoomParams: ZoomParams = { h: 5.0, z1: 0.1, z2: 1.1 }

    public atlasLayers: AtlasLayerManager
    private hdLayer: HDLayer
    private lassoLayer: LassoLayer
    private spatialIndex = new SpatialIndex()
    

    private globalUniforms = {
        uZoom: { value: 1.0 }
    }

    public onPointSelection: ((points: PointData[]) => void) | null = null
    
    public onHover = new EventEmitter()

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

    public async createMap(atlas: ImageAtlas, points: PointData[], showAsPoint: boolean) {
        const dataStore = useDataStore()
        this.spatialIndex.initTree(points)

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
            const rect = this.getCameraRect()
            const pointsInView = this.spatialIndex.getPointsInRect(rect)

            // HD Detail threshold
            if (pointsInView.length < 50) {
                this.hdLayer.show(pointsInView)
            } else {
                this.hdLayer.show([])
            }
        }

        this.updateHoverState()
        // console.log(this.controls.getMouseWorldPos())
        // console.log(this.camera.zoom)
        this.renderer.render(this.scene, this.camera)
    }

    private updateHoverState() {
        const foundPoint = this.controls.getHoveredPoint(this.zoomParams)
        const foundId = foundPoint ? foundPoint.id! : null

        if (foundId) {
            this.hdLayer.hover(foundPoint)
            this.onHover.emit(useDataStore().sha1Index[foundPoint.sha1][0].id)
        } else {
            this.hdLayer.unhover()
            this.onHover.emit()
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

    public setZoomParams(imageSize: number, zoomDelay: number) {
        this.zoomParams.h = imageSize / 2
        this.zoomParams.z2 = this.zoomParams.z1 + zoomDelay * 0.2
        this.hdLayer.setZoomParams(this.zoomParams)
        this.atlasLayers.setZoomParams(this.zoomParams)
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
        const { h, z1, z2 } = this.zoomParams;

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

    public lookAtRect(rect: { minX: number, minY: number, maxX: number, maxY: number }) {
        let offset = this.getImageMaxSize()
        let finalRect = deepCopy(rect)
        finalRect.minX -= offset
        finalRect.minY -= offset
        finalRect.maxX += offset
        finalRect.maxY += offset
        this.controls.lookAtRect(finalRect)
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