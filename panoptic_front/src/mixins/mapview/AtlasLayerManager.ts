import * as THREE from 'three'
import { AtlasLayer } from './AtlasLayer'
import { ImageAtlas, PointData, ZoomParams } from '@/data/models'

export class AtlasLayerManager {
    private scene: THREE.Scene
    private layers: AtlasLayer[] = []
    private _isVisible: boolean = true
    private _zoomParams: ZoomParams
    
    // Cache for loaded textures, keyed by atlas ID and sheet index
    private static textureCache = new Map<string, THREE.Texture>()
    private currentAtlasId: number | null = null

    constructor(scene: THREE.Scene) {
        this.scene = scene
    }

    /**
     * Generates a cache key for a specific atlas sheet
     */
    private getCacheKey(atlasId: number, sheetIndex: number): string {
        return `${atlasId}_${sheetIndex}`
    }

    /**
     * Loads textures and creates layers for the given atlas and points.
     * Reuses cached textures if the atlas ID matches the previous one.
     */
    public async loadLayers(
        atlas: ImageAtlas,
        points: PointData[],
        baseUrl: string,
        zoomUniform: { value: number },
        showAsPoint: boolean
    ) {
        const isAtlasChanged = this.currentAtlasId !== atlas.id
        
        // Only dispose layers, not textures (they're cached)
        this.disposeLayers()
        
        // If atlas changed, we could optionally clear old atlas textures from cache
        // For now, we keep all textures cached to support quick switching between multiple atlases
        
        this.currentAtlasId = atlas.id

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

            const cacheKey = this.getCacheKey(atlas.id, s)
            const textureUrl = `${baseUrl}atlas_sheet/${atlas.id}/${s}`
            
            // Assign order for instanced rendering if needed
            sheetPoints.forEach((p, i) => p.order = (s * maxPerSheet) + i)

            try {
                let texture: THREE.Texture
                
                // Check if texture is already cached
                if (AtlasLayerManager.textureCache.has(cacheKey)) {
                    texture = AtlasLayerManager.textureCache.get(cacheKey)!
                } else {
                    // Load new texture and cache it
                    texture = await loader.loadAsync(textureUrl)
                    texture.colorSpace = THREE.SRGBColorSpace
                    texture.generateMipmaps = true
                    texture.minFilter = THREE.LinearMipmapLinearFilter
                    
                    AtlasLayerManager.textureCache.set(cacheKey, texture)
                }

                const layer = new AtlasLayer(atlas, texture, sheetPoints, s)
                layer.setZoomReference(zoomUniform)

                // Set initial visibility state
                layer.mesh.visible = this._isVisible
                layer.setZoomParams(this._zoomParams)
                layer.setShowAsPoint(showAsPoint)
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

    /**
     * Disposes only the layers (meshes, geometries, materials) but keeps textures cached
     */
    private disposeLayers() {
        this.layers.forEach(l => {
            this.scene.remove(l.mesh)
            l.dispose()
        })
        this.layers = []
    }

    /**
     * Full cleanup including textures - call this when the component unmounts
     */
    public dispose() {
        this.disposeLayers()
        // Note: We don't clear the static texture cache here by default
        // to allow reuse across manager instances
    }

    /**
     * Clears the entire texture cache - useful for memory management
     * Call this when you want to free up GPU memory
     */
    public static clearTextureCache() {
        AtlasLayerManager.textureCache.forEach(texture => {
            texture.dispose()
        })
        AtlasLayerManager.textureCache.clear()
    }

    /**
     * Clears textures for a specific atlas from the cache
     */
    public static clearAtlasFromCache(atlasId: string) {
        const keysToDelete: string[] = []
        AtlasLayerManager.textureCache.forEach((texture, key) => {
            if (key.startsWith(`${atlasId}_`)) {
                texture.dispose()
                keysToDelete.push(key)
            }
        })
        keysToDelete.forEach(key => AtlasLayerManager.textureCache.delete(key))
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
    
    public updateBorderWidths() {
        this.layers.forEach(l => l.updateBorderWidths())
    }

    public setShowAsPoint(show: boolean) {
        this.layers.forEach(l => l.setShowAsPoint(show))
    }
}