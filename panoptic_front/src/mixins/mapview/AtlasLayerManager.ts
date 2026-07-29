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
    // Guards against a second loadLayers() call starting before a first one's per-sheet texture
    // loads finish: disposeLayers() only clears whatever is in `this.layers` at the moment it
    // runs, it can't stop an older, already-in-flight call from later pushing its own (stale)
    // layers into the same array once its await resolves. Without this, both calls' layers end
    // up coexisting — the stale one built from whatever `points` looked like when it was
    // invoked (e.g. still ungrouped/default-coloured on a fresh reload), sitting at the same
    // positions as the correct, current layers.
    private loadToken = 0

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
        const token = ++this.loadToken
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

        const maxPerSheet = Math.max(...sheetPointsMap.map(v => v.length))

        // Process each sheet
        for (let s = 0; s < atlas.atlasNb; s++) {
            // A newer loadLayers() call started (and already disposed our layers) while we were
            // still working — abandon rather than push stale layers into its result.
            if (token !== this.loadToken) return

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

                // Re-check right after the await too: this is the actual window where a newer
                // call is most likely to have started and finished its own disposeLayers().
                if (token !== this.loadToken) return

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

    public updateDesaturation() {
        this.layers.forEach(l => l.updateDesaturation())
    }

    public updatePositions() {
        this.layers.forEach(l => l.updatePositions())
    }

    public updateBorder() {
        this.layers.forEach(l => l.updateBorder())
    }

    public setShowAsPoint(show: boolean) {
        this.layers.forEach(l => l.setShowAsPoint(show))
    }
}