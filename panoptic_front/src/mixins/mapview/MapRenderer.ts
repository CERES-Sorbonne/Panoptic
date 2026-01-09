import * as THREE from 'three'
import { useDataStore } from '@/data/dataStore'
import { MapControls } from './MapControl'
import { ImageAtlas, PointData, ZoomParams } from '@/data/models'
import { SpatialIndex } from './SpatialIndex'
import { HDLayer } from './HDLayer'
import { AtlasLayerManager } from './AtlasLayerManager' // Import the new class
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
    private hoveredId: number
    private zoomParams: ZoomParams = { h: 8.0, z1: 0.1, z2: 1.0 }
    // private pointIndex: PointIndex = {}

    // Replaced array with the Manager instance
    public atlasLayers: AtlasLayerManager

    private hdLayer: HDLayer
    private lassoLayer: LassoLayer
    private spatialIndex = new SpatialIndex()

    private globalUniforms = {
        uZoom: { value: 1.0 }
    }

    public onPointSelection: Function = null

    constructor(container: HTMLElement, baseImgUrl: string) {
        this.container = container
        this.scene = new THREE.Scene()
        this.scene.background = new THREE.Color(0xFFFFFF)

        this.initCamera()
        this.initRenderer()

        // Initialize the manager
        this.atlasLayers = new AtlasLayerManager(this.scene)
        this.atlasLayers.setZoomParams(this.zoomParams)

        this.hdLayer = new HDLayer(this.scene, baseImgUrl)
        this.hdLayer.setZoomReference(this.globalUniforms.uZoom)
        this.hdLayer.setZoomParams(this.zoomParams)

        this.lassoLayer = new LassoLayer(this.scene, this.spatialIndex, (points) => {
            if (this.onPointSelection) {
                this.onPointSelection(points)
            }
        })

        this.controls = new MapControls(this.camera, this.renderer.domElement, this.lassoLayer)
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
        this.container.appendChild(this.renderer.domElement)
    }

    public async createMap(atlas: ImageAtlas, points: PointData[]) {
        const dataStore = useDataStore()

        points.forEach(p => {
            if (p.ratio > 2) {
                // p.ratio = 1 / p.ratio
            }
        })

        // Delegate loading logic to the manager
        await this.atlasLayers.loadLayers(
            atlas,
            points,
            dataStore.baseUrl,
            this.globalUniforms.uZoom
        )

        // Initialize Spatial Index and HD Layer
        this.spatialIndex.initTree(points)
        // this.buildIndex(points)
    }

    private onResize() {
        const w = this.container.clientWidth
        const h = this.container.clientHeight
        const aspect = w / h
        this.camera.left = (this.frustumSize * aspect) / -2
        this.camera.right = (this.frustumSize * aspect) / 2
        this.camera.top = this.frustumSize / 2
        this.camera.bottom = this.frustumSize / -2
        this.camera.updateProjectionMatrix()
        this.renderer.setSize(w, h)
    }

    public animate() {
        this.requestID = requestAnimationFrame(() => this.animate())

        if (this.globalUniforms.uZoom.value !== this.camera.zoom) {
            this.globalUniforms.uZoom.value = this.camera.zoom;
        }

        if (this.hdLayer) {
            this.hdLayer.updateAnimations()
            const rect = this.getCameraRect()
            const pointsInView = this.spatialIndex.getPointsInRect(rect)

            if (this.camera.zoom > 2.0 && pointsInView.length < 100) {
                this.hdLayer.show(pointsInView)
                // this.atlasManager.hide()
            } else {
                this.hdLayer.show([])
                // this.atlasManager.show()
            }
        }
        this.updateHoverRectangular()
        this.renderer.render(this.scene, this.camera)
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

        // Clean up via manager
        this.atlasLayers.dispose()
        if (this.hdLayer) {
            this.hdLayer.dispose()
            this.hdLayer = undefined
        }

        this.scene.clear()
    }

    public updateHoverRectangular() {

        const mouseMode = this.controls.getMode()
        if (mouseMode.startsWith('lasso')) {
            if (this.hoveredId) {
                this.hdLayer.unhover(this.hoveredId)
                this.hoveredId = null
            }
            return
        }

        const worldPos = this.controls.getMouseWorldPos();
        const currentZoom = this.camera.zoom;

        // These should match what you pass to updateAllZoomParams(h, z1, z2)
        const h = this.zoomParams.h;
        const z1 = this.zoomParams.z1;
        const z2 = this.zoomParams.z2;

        // 1. Calculate the Dynamic Scale Factor (Replicating Shader Logic)
        let zoomScale = h;
        if (currentZoom >= z1 && currentZoom < z2) {
            zoomScale = h * (z1 / currentZoom);
        } else if (currentZoom >= z2) {
            zoomScale = h * (z1 / z2);
        }

        // 2. Broad phase (Adjust search area based on dynamic scale)
        const searchArea = zoomScale;
        const nearbyPoints = this.spatialIndex.getPointsInRect({
            minX: worldPos.x - searchArea,
            maxX: worldPos.x + searchArea,
            minY: worldPos.y - searchArea,
            maxY: worldPos.y + searchArea
        });

        // 3. Sort by distance
        nearbyPoints.sort((a, b) => {
            const distA = Math.pow(a.x - worldPos.x, 2) + Math.pow(a.y - worldPos.y, 2);
            const distB = Math.pow(b.x - worldPos.x, 2) + Math.pow(b.y - worldPos.y, 2);
            return distA - distB;
        });

        // 4. Narrow phase: Check actual boundaries with dynamic scale
        let foundId: number | null = null
        let foundPoint: PointData | null = null

        for (const p of nearbyPoints) {
            // Calculate scale factor to fit in 1.0 x 1.0 box
            let scale;
            if (p.ratio > 1.0) {
                // Landscape: constrain by width (1.0)
                scale = 1.0 / p.ratio;
            } else {
                // Portrait/Square: constrain by height (1.0)
                scale = 1.0;
            }

            // Apply zoom and constraint to get final scale
            const finalScale = zoomScale * scale;
            // Calculate actual dimensions based on aspect ratio
            let width, height;
            if (p.ratio > 1.0) {
                // Landscape: width = 1.0 * finalScale, height = (1.0 / ratio) * finalScale
                width = 1.0 * finalScale;
                height = (1.0 / p.ratio) * finalScale;
            } else {
                // Portrait/Square: width = ratio * finalScale, height = 1.0 * finalScale
                width = p.ratio * finalScale;
                height = 1.0 * finalScale;
            }

            const halfW = width;
            const halfH = height;

            if (worldPos.x >= p.x - halfW && worldPos.x <= p.x + halfW &&
                worldPos.y >= p.y - halfH && worldPos.y <= p.y + halfH) {
                foundId = p.id!;
                foundPoint = p
                break;
            }
        }

        // 5. Apply hover/unhover logic
        if (foundId !== this.hoveredId) {
            if (this.hoveredId !== null) this.hdLayer?.unhover(this.hoveredId);
            this.hoveredId = foundId;
            if (this.hoveredId !== null) this.hdLayer?.hover(foundPoint);
        }
    }

    public setMouseMode(mode: string) {
        this.controls.setMode(mode)
    }

    public updateTints() {
        this.atlasLayers.updateTints()
        this.hdLayer.updateTints()
    }



    // clearIndex() {
    //     Object.keys(this.pointIndex).forEach(k => delete this.pointIndex[k])
    // }

    // buildIndex(points: PointData[]) {
    //     for(let point of points) {
    //         this.pointIndex[point.id] = point
    //     }
    // }
}