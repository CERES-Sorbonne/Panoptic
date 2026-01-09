import * as THREE from 'three'
import { AtlasLayer } from './AtlasLayer'
import { ImageAtlas, PointData, ZoomParams } from '@/data/models'

export class AtlasLayerManager {
    private scene: THREE.Scene
    private layers: AtlasLayer[] = []
    private _isVisible: boolean = true
    private _zoomParams: ZoomParams

    constructor(scene: THREE.Scene) {
        this.scene = scene
    }

    /**
     * Loads textures and creates layers for the given atlas and points.
     */
    public async loadLayers(
        atlas: ImageAtlas,
        points: PointData[],
        baseUrl: string,
        zoomUniform: { value: number }
    ) {
        // Cleanup existing layers before loading new ones
        this.dispose()

        const loader = new THREE.TextureLoader()

        // Group points by sheet index
        const sheetPointsMap: PointData[][] = Array.from({ length: atlas.atlasNb }, () => [])
        for (let p of points) {
            if (!atlas.sha1Mapping[p.sha1]) continue
            let sheetIndex = atlas.sha1Mapping[p.sha1][0]
            sheetPointsMap[sheetIndex].push(p)
        }

        let maxPerSheet = Math.max(...sheetPointsMap.map(v => v.length))

        // Process each sheet
        for (let s = 0; s < atlas.atlasNb; s++) {
            const sheetPoints = sheetPointsMap[s]
            if (sheetPoints.length === 0) continue

            const textureUrl = `${baseUrl}atlas_sheet/${atlas.id}/${s}`
            // Assign order for instanced rendering if needed
            sheetPoints.forEach((p, i) => p.order = (s * maxPerSheet) + i)

            try {
                const texture = await loader.loadAsync(textureUrl)
                texture.colorSpace = THREE.SRGBColorSpace
                texture.generateMipmaps = true
                texture.minFilter = THREE.LinearMipmapLinearFilter

                const layer = new AtlasLayer(atlas, texture, sheetPoints, s)
                layer.setZoomReference(zoomUniform)

                // Set initial visibility state
                layer.mesh.visible = this._isVisible
                layer.setZoomParams(this._zoomParams)
                this.layers.push(layer)

                this.scene.add(layer.mesh)
            } catch (error) {
                console.error(`Failed to load atlas sheet ${s}:`, error)
            }
        }
    }

    public show() {
        this._isVisible = true
        this.layers.forEach(l => l.mesh.visible = true)
    }

    public hide() {
        this._isVisible = false
        this.layers.forEach(l => l.mesh.visible = false)
    }

    public dispose() {
        this.layers.forEach(l => {
            this.scene.remove(l.mesh)
            l.dispose()
        })
        this.layers = []
    }

    public setZoomParams(params: ZoomParams) {
        this._zoomParams = params
        this.layers.forEach(l => l.setZoomParams(params))
    }

    public updateTints() {
        this.layers.forEach(l => l.updateTints())
    }

    public updateBorderColors() {
        this.layers.forEach(l => l.updateBorderColors())
    }

    public updatePositions() {
        this.layers.forEach(l => l.updatePositions())
    }
}