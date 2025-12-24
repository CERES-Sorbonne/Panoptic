import * as THREE from 'three'
import { useDataStore } from '@/data/dataStore'
import { MapControls } from './MapControl'
import { InstancedImageMaterial } from './InstancedImageMaterial'
import { apiGetAtlas } from '@/data/apiProjectRoutes'
import { ImageAtlas } from '@/data/models'
import { AtlasLayer } from './AtlasLayer'
import { PointData } from './useMapLogic'

export class MapRenderer {
    private container: HTMLElement
    private scene: THREE.Scene
    private camera!: THREE.OrthographicCamera
    private renderer!: THREE.WebGLRenderer
    private controls!: MapControls
    private requestID: number | null = null
    private resizeObserver: ResizeObserver
    private mapImage!: THREE.Mesh
    private frustumSize = 20
    private layers: AtlasLayer[] = []

    constructor(container: HTMLElement) {
        this.container = container
        this.scene = new THREE.Scene()
        this.scene.background = new THREE.Color(0xFFFFFF)

        this.initCamera()
        this.initRenderer()

        // Initialize our clean custom controls
        this.controls = new MapControls(this.camera, this.renderer.domElement)
        this.controls.onUpdate = () => this.triggerRender()

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
    }

    private initRenderer() {
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight)
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

        // Accurate Color Settings
        this.renderer.toneMapping = THREE.NoToneMapping
        this.renderer.outputColorSpace = THREE.SRGBColorSpace

        this.container.appendChild(this.renderer.domElement)
    }

    private addImage() {
        const loader = new THREE.TextureLoader()
        const url = useDataStore().baseUrl + 'spritesheet'

        const texture = loader.load(url, (tex) => {
            tex.colorSpace = THREE.SRGBColorSpace
            this.triggerRender()
        })

        const geometry = new THREE.PlaneGeometry(10, 10)
        const material = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        })

        this.mapImage = new THREE.Mesh(geometry, material)
        this.scene.add(this.mapImage)
    }

    public async createMap(atlas: ImageAtlas, points: PointData[]) {
        console.log('create map')
        this.clearLayers();

        const loader = new THREE.TextureLoader();
        const baseUrl = useDataStore().baseUrl;
        console.log(points.map(p => p.color))

        const sheetPointsMap = new Array(atlas.atlasNb)
        for (let i = 0; i < atlas.atlasNb; i++) {
            sheetPointsMap[i] = []
        }
        console.log(points.length)
        for (let p of points) {
            if(!atlas.sha1Mapping[p.sha1]) continue
            let sheetIndex = atlas.sha1Mapping[p.sha1][0]
            console.log(sheetIndex)
            sheetPointsMap[sheetIndex].push(p)
        }
        // atlas.atlasNb is the total count of sheets
        for (let s = 0; s < atlas.atlasNb; s++) {

            const sheetPoints = sheetPointsMap[s]
            console.log(sheetPoints)
            if (sheetPoints.length === 0) continue;

            // Load the specific sheet image
            const textureUrl = `${baseUrl}atlas_sheet/${atlas.id}/${s}`;
            console.log(textureUrl)
            try {
                const texture = await loader.loadAsync(textureUrl);
                texture.colorSpace = THREE.SRGBColorSpace;
                // Best for pixel art/icons to prevent blurring
                texture.magFilter = THREE.NearestFilter;
                texture.minFilter = THREE.NearestFilter;
                texture.generateMipmaps = false; // Mipmaps are a major cause of bleeding at a distance
                texture.wrapS = THREE.ClampToEdgeWrapping;
                texture.wrapT = THREE.ClampToEdgeWrapping;

                const layer = new AtlasLayer(atlas, texture, sheetPoints, s);
                this.layers.push(layer);
                this.scene.add(layer.mesh);
            } catch (error) {
                console.error(`Failed to load atlas sheet ${s}:`, error);
            }
        }
        console.log(this.layers)
        this.triggerRender();
    }

    private clearLayers() {
        this.layers.forEach(l => {
            this.scene.remove(l.mesh)
            l.dispose()
        })
        this.layers = []
    }

    private triggerRender() {
        // In a class, we just render directly or set a flag
        this.renderer.render(this.scene, this.camera)
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
        this.triggerRender()
    }

    public animate() {
        this.requestID = requestAnimationFrame(() => this.animate())
        // If you have animations (like the rotating cube), call them here
        this.renderer.render(this.scene, this.camera)
    }

    public dispose() {
        if (this.requestID) cancelAnimationFrame(this.requestID)
        this.resizeObserver.disconnect()
        this.controls.dispose()
        this.renderer.dispose()
        this.clearLayers()

        this.mapImage.geometry.dispose()
        if (this.mapImage.material instanceof THREE.Material) {
            this.mapImage.material.dispose()
        }

        this.scene.clear()
        if (this.container.contains(this.renderer.domElement)) {
            this.container.removeChild(this.renderer.domElement)
        }
    }

}