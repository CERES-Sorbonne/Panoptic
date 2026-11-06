import * as THREE from 'three'
import { AtlasLayer } from './AtlasLayer'
import { ImageAtlas, PointData, ZoomParams } from '@/data/models'

// Sheets downloading and decoding at the same time. Chromium decodes ImageBitmaps off the main
// thread and in parallel, so a load no longer costs the sum of every sheet's decode.
const SHEET_CONCURRENCY = 4

const BITMAP_OPTIONS: ImageBitmapOptions = {
    // WebGL ignores UNPACK_FLIP_Y for bitmaps, so flip while decoding instead
    imageOrientation: 'flipY',
    // what three.js uploads an <img> sRGB texture with: straight alpha, no colour conversion
    premultiplyAlpha: 'none',
    colorSpaceConversion: 'none',
}

async function loadSheet(url: string): Promise<THREE.Texture> {
    const res = await fetch(url)
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`)
    const blob = await res.blob()

    let texture: THREE.Texture
    try {
        const bitmap = await createImageBitmap(blob, BITMAP_OPTIONS)
        texture = new THREE.Texture(bitmap)
        texture.flipY = false
        // The bitmap pins the decoded sheet (16 MB) in memory: free it once it is on the GPU.
        texture.onUpdate = () => bitmap.close()
    } catch {
        // Browsers without createImageBitmap options. Uploading an <img> decodes it on the
        // main thread, so this path is slower.
        const objectUrl = URL.createObjectURL(blob)
        try {
            texture = await new THREE.TextureLoader().loadAsync(objectUrl)
        } finally {
            URL.revokeObjectURL(objectUrl)
        }
    }
    texture.colorSpace = THREE.SRGBColorSpace
    texture.generateMipmaps = true
    texture.minFilter = THREE.LinearMipmapLinearFilter
    texture.needsUpdate = true
    return texture
}

function freeTexture(texture: THREE.Texture) {
    texture.dispose()
    // a bitmap that never reached the GPU is still holding its pixels
    if (typeof ImageBitmap !== 'undefined' && texture.image instanceof ImageBitmap) texture.image.close()
}

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
    // loadLayers() entry: sheets load over many awaits, so a point/image toggle mid-load must
    // reach the layers that don't exist yet, not just the ones already built.
    private _showAsPoint = false
    private _fill = false
    private _pointSize = 1
    
    // Loaded sheet textures, keyed by atlas id, version and sheet index. They belong to this
    // manager's renderer: their pixels are freed once uploaded, so another WebGL context could
    // not upload them again.
    private textureCache = new Map<string, THREE.Texture>()
    // Sheets still downloading, under the same keys. A newer loadLayers() call (map switch,
    // regrouping) reuses them instead of starting a second download.
    private pendingTextures = new Map<string, Promise<THREE.Texture>>()
    // Atlas versions fully loaded at least once this session (see wasAtlasLoaded).
    private static loadedAtlases = new Set<string>()
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
            this.clearAtlasFromCache(atlas.id, this.currentAtlasVersion)
        }

        this.currentAtlasId = atlas.id
        this.currentAtlasVersion = atlas.version

        // Group points by sheet index
        const sheetPointsMap: PointData[][] = Array.from({ length: atlas.atlasNb }, () => [])
        for (let p of points) {
            if (!atlas.sha1Mapping[p.sha1]) continue
            let sheetIndex = atlas.sha1Mapping[p.sha1][0]
            sheetPointsMap[sheetIndex].push(p)
        }

        const maxPerSheet = Math.max(...sheetPointsMap.map(v => v.length))
        const sheets: number[] = []
        sheetPointsMap.forEach((sheetPoints, s) => {
            if (sheetPoints.length === 0) return
            sheets.push(s)
            // Assign order for instanced rendering. Done for every sheet up front, since sheets
            // finish loading in any order.
            sheetPoints.forEach((p, i) => p.order = (s * maxPerSheet) + i)
        })

        const progress: AtlasLoadProgress = { loaded: 0, failed: 0, total: sheets.length }
        const report = () => { if (token === this.loadToken) this.onProgress?.({ ...progress }) }
        report()

        let next = 0
        const loadNext = async () => {
            while (next < sheets.length) {
                // A newer loadLayers() call started (and already disposed our layers) while we
                // were still working — abandon rather than push stale layers into its result.
                if (token !== this.loadToken) return
                const s = sheets[next++]
                try {
                    const texture = await this.sheetTexture(atlas, s, baseUrl)
                    // Re-check right after the await too: this is the actual window where a newer
                    // call is most likely to have started and finished its own disposeLayers().
                    if (token !== this.loadToken) return
                    this.addLayer(atlas, texture, sheetPointsMap[s], s, zoomUniform)
                    progress.loaded++
                } catch (error) {
                    if (token !== this.loadToken) return
                    console.error(`Failed to load atlas sheet ${s}:`, error)
                    progress.failed++
                }
                report()
            }
        }
        await Promise.all(Array.from({ length: Math.min(SHEET_CONCURRENCY, sheets.length) }, loadNext))

        if (token === this.loadToken && progress.failed === 0) {
            AtlasLayerManager.loadedAtlases.add(`${atlas.id}_${atlas.version ?? 0}`)
        }
    }

    /**
     * The texture of one sheet: from the cache, from a download already running, or downloaded.
     */
    private sheetTexture(atlas: ImageAtlas, sheetIndex: number, baseUrl: string): Promise<THREE.Texture> {
        const key = this.getCacheKey(atlas, sheetIndex)
        const cached = this.textureCache.get(key)
        if (cached) return Promise.resolve(cached)
        const running = this.pendingTextures.get(key)
        if (running) return running

        // The version query param busts the browser's HTTP cache: the sheet path is
        // identical across rebuilds, so without it we can be served the old PNG.
        const url = `${baseUrl}atlas_sheet/${atlas.id}/${sheetIndex}`
            + (atlas.version !== undefined ? `?v=${atlas.version}` : '')
        const promise: Promise<THREE.Texture> = loadSheet(url).then(texture => {
            // Dropped while downloading (rebuilt atlas, unmounted view): nothing will use it.
            if (this.pendingTextures.get(key) !== promise) {
                freeTexture(texture)
                throw new Error(`atlas sheet ${key} dropped`)
            }
            this.pendingTextures.delete(key)
            this.textureCache.set(key, texture)
            return texture
        }, error => {
            if (this.pendingTextures.get(key) === promise) this.pendingTextures.delete(key)
            throw error
        })
        this.pendingTextures.set(key, promise)
        return promise
    }

    private addLayer(atlas: ImageAtlas, texture: THREE.Texture, points: PointData[], sheetIndex: number, zoomUniform: { value: number }) {
        const layer = new AtlasLayer(atlas, texture, points, sheetIndex)
        layer.setZoomReference(zoomUniform)

        // Set initial visibility state
        layer.mesh.visible = this._isVisible
        layer.setZoomParams(this._zoomParams)
        layer.setShowAsPoint(this._showAsPoint)
        layer.setFill(this._fill)
        layer.setPointSize(this._pointSize)
        this.layers.push(layer)

        this.scene.add(layer.mesh)
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
        // stops any running loadLayers() call
        this.loadToken++
        this.disposeLayers()
        this.textureCache.forEach(freeTexture)
        this.textureCache.clear()
        // running downloads free their texture when they land
        this.pendingTextures.clear()
    }

    /**
     * Whether this atlas version was fully loaded before in this session, by any map view.
     * Loading it again skips the download (browser cache) and decodes off the main thread.
     */
    public static wasAtlasLoaded(atlas: ImageAtlas): boolean {
        return AtlasLayerManager.loadedAtlases.has(`${atlas.id}_${atlas.version ?? 0}`)
    }

    /**
     * Clears textures for a specific atlas from the cache. Pass a version to only drop that
     * one generation's sheets, or omit it to drop every generation of the atlas.
     */
    private clearAtlasFromCache(atlasId: number, version?: number) {
        const prefix = version !== undefined ? `${atlasId}_${version}_` : `${atlasId}_`
        for (const [key, texture] of [...this.textureCache]) {
            if (!key.startsWith(prefix)) continue
            freeTexture(texture)
            this.textureCache.delete(key)
        }
        for (const key of [...this.pendingTextures.keys()]) {
            if (key.startsWith(prefix)) this.pendingTextures.delete(key)
        }
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

    public updateOpacity() {
        this.layers.forEach(l => l.updateOpacity())
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

    public setPointSize(size: number) {
        this._pointSize = size
        this.layers.forEach(l => l.setPointSize(size))
    }

    public setFill(fill: boolean) {
        this._fill = fill
        this.layers.forEach(l => l.setFill(fill))
    }
}