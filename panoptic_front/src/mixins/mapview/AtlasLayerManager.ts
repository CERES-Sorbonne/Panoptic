import * as THREE from 'three'
import { AtlasLayer } from './AtlasLayer'
import { ImageAtlas, PointData, ZoomParams } from '@/data/models'

export interface AtlasLoadProgress {
    loaded: number
    failed: number
    total: number
}

export class AtlasLayerManager {
    private scene: THREE.Scene
    private layers: AtlasLayer[] = []
    private _isVisible: boolean = true
    private _zoomParams: ZoomParams
    // Current display mode, read when each sheet's layer is built rather than captured once at
    // loadLayers() entry: sheets load one await at a time, so a point/image toggle mid-load must
    // reach the layers that don't exist yet, not just the ones already built.
    private _showAsPoint = false
    
    // Cache for loaded textures, keyed by atlas ID and sheet index
    private static textureCache = new Map<string, THREE.Texture>()
    private currentAtlasId: number | null = null
    private currentAtlasVersion: number | undefined = undefined
    // Guards against a second loadLayers() call starting before a first one's per-sheet texture
    // loads finish: disposeLayers() only clears whatever is in `this.layers` at the moment it
    // runs, it can't stop an older, already-in-flight call from later pushing its own (stale)
    // layers into the same array once its await resolves. Without this, both calls' layers end
    // up coexisting — the stale one built from whatever `points` looked like when it was
    // invoked (e.g. still ungrouped/default-coloured on a fresh reload), sitting at the same
    // positions as the correct, current layers.
    private loadToken = 0

    // Sheet-load progress of the current loadLayers() call, reported once when it starts and after
    // every sheet. A superseded call stops reporting, so the numbers always describe the newest load.
    public onProgress: ((progress: AtlasLoadProgress) => void) | null = null

    constructor(scene: THREE.Scene) {
        this.scene = scene
    }

    /**
     * Generates a cache key for a specific atlas sheet
     */
    private getCacheKey(atlas: ImageAtlas, sheetIndex: number): string {
        return `${atlas.id}_${atlas.version ?? 0}_${sheetIndex}`
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
        this._showAsPoint = showAsPoint

        // Only dispose layers, not textures (they're cached)
        this.disposeLayers()

        // Textures are cached per (atlas id, version, sheet). Re-importing a source rewrites
        // atlas id 0's sheets on disk, so the previous version's textures are now garbage —
        // free them instead of letting them leak. Different ids stay cached to support quick
        // switching between multiple atlases.
        if (this.currentAtlasId === atlas.id && this.currentAtlasVersion !== atlas.version) {
            AtlasLayerManager.clearAtlasFromCache(atlas.id, this.currentAtlasVersion)
        }

        this.currentAtlasId = atlas.id
        this.currentAtlasVersion = atlas.version

        const loader = new THREE.TextureLoader()

        // Group points by sheet index
        const sheetPointsMap: PointData[][] = Array.from({ length: atlas.atlasNb }, () => [])
        for (let p of points) {
            if (!atlas.sha1Mapping[p.sha1]) continue
            let sheetIndex = atlas.sha1Mapping[p.sha1][0]
            sheetPointsMap[sheetIndex].push(p)
        }

        const maxPerSheet = Math.max(...sheetPointsMap.map(v => v.length))

        const progress: AtlasLoadProgress = {
            loaded: 0,
            failed: 0,
            total: sheetPointsMap.filter(v => v.length > 0).length,
        }
        const report = () => { if (token === this.loadToken) this.onProgress?.({ ...progress }) }
        report()

        // Process each sheet
        for (let s = 0; s < atlas.atlasNb; s++) {
            // A newer loadLayers() call started (and already disposed our layers) while we were
            // still working — abandon rather than push stale layers into its result.
            if (token !== this.loadToken) return

            const sheetPoints = sheetPointsMap[s]
            if (sheetPoints.length === 0) continue

            const cacheKey = this.getCacheKey(atlas, s)
            // The version query param busts the browser's HTTP cache: the sheet path is
            // identical across rebuilds, so without it we can be served the old PNG.
            const textureUrl = `${baseUrl}atlas_sheet/${atlas.id}/${s}`
                + (atlas.version !== undefined ? `?v=${atlas.version}` : '')

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
                layer.setShowAsPoint(this._showAsPoint)
                this.layers.push(layer)

                this.scene.add(layer.mesh)
                progress.loaded++
            } catch (error) {
                console.error(`Failed to load atlas sheet ${s}:`, error)
                progress.failed++
            }
            report()
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
     * Clears textures for a specific atlas from the cache. Pass a version to only drop that
     * one generation's sheets, or omit it to drop every generation of the atlas.
     */
    public static clearAtlasFromCache(atlasId: number, version?: number) {
        const prefix = version !== undefined ? `${atlasId}_${version}_` : `${atlasId}_`
        const keysToDelete: string[] = []
        AtlasLayerManager.textureCache.forEach((texture, key) => {
            if (key.startsWith(prefix)) {
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
        this._showAsPoint = show
        this.layers.forEach(l => l.setShowAsPoint(show))
    }
}