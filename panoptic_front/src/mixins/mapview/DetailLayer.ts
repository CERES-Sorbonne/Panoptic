import * as THREE from 'three'
import { PointData, ZoomParams } from '@/data/models'
import { HDImageMaterial } from './HDImageMaterial'
import { IMAGE_RADIUS } from './InstancedImageMaterial'

const sharedPlaneGeo = new THREE.PlaneGeometry(1, 1)

// Above the point's atlas thumbnail (whose z spread stays under 0.1) and below the HD hover
// preview (HD_Z_OFFSET = 1.5, over SELECTED_Z = 1.0).
const DETAIL_Z_OFFSET = 0.2
const DETAIL_RENDER_ORDER = 1000

// Above this many images on screen, only the atlas thumbnails are drawn.
export const MAX_DETAIL_TILES = 300
// Detail images start once a thumbnail is drawn this much bigger than its atlas cell.
const MIN_UPSCALE = 1.25
// Requested sizes (longest side, px). The smallest one that covers the screen size is used.
const SIZES = [128, 256, 512, 1024, 2048]
const MAX_PARALLEL_LOADS = 6
// GPU memory for cached detail textures, mipmaps included.
const TEXTURE_BUDGET_BYTES = 384 * 1024 * 1024
// New tiles per frame: each one uploads its texture on its first draw.
const MAX_NEW_TILES_PER_FRAME = 8
// Opacity a new tile gains per frame as it fades in over its thumbnail.
const FADE_STEP = 0.2

interface CachedTexture {
    texture: THREE.Texture
    bytes: number
    lastUsed: number
}

interface Tile {
    mesh: THREE.Mesh
    material: HDImageMaterial
    key: string
    opacity: number
}

/**
 * Sharper images over the grid's atlas thumbnails. Atlas cells are small, so zoomed-in
 * thumbnails are blurry. Once few enough images are on screen, this layer loads each one at the
 * size it is drawn and puts it over its thumbnail, with the same shape, border, tint and
 * desaturation. The thumbnail stays visible until the image has loaded.
 */
export class DetailLayer {
    private group = new THREE.Group()
    private scene: THREE.Scene
    private baseImgUrl: string
    private zoomRef: { value: number } = { value: 1.0 }
    private zoomParams: ZoomParams = { h: 1.0, z1: 0.1, z2: 0.11 }
    private fill = false
    // Side of an atlas cell, in px.
    private atlasCellSize = 64

    // Points to draw, closest to the screen centre first, and the size to load them at.
    private view: PointData[] = []
    private size = 0
    private dirty = false
    private frame = 0

    private tiles = new Map<PointData, Tile>()
    // Keyed by textureKey(sha1, size).
    private textures = new Map<string, CachedTexture>()
    private loads = new Map<string, AbortController>()
    private failed = new Set<string>()
    private queue: string[] = []
    private textureBytes = 0
    private disposed = false

    constructor(scene: THREE.Scene, baseImgUrl: string) {
        this.scene = scene
        this.baseImgUrl = baseImgUrl
        this.scene.add(this.group)
    }

    public setZoomReference(zoomUniform: { value: number }) {
        this.zoomRef = zoomUniform
    }

    public setZoomParams(params: ZoomParams) {
        this.zoomParams = params
        this.tiles.forEach(tile => tile.material.setZoomParams(params))
    }

    public setFill(fill: boolean) {
        if (fill === this.fill) return
        this.fill = fill
        this.tiles.forEach((tile, p) => this.applyShape(tile, p))
    }

    // New map: its points are new objects, so every tile goes. Loaded textures stay cached.
    public setMap(atlasCellSize: number) {
        this.atlasCellSize = atlasCellSize
        this.setView([], 0)
        this.clearTiles()
    }

    // Whether thumbnails drawn `pixelSize` device px wide are worth replacing.
    public wantsDetail(pixelSize: number) {
        return pixelSize > this.atlasCellSize * MIN_UPSCALE
    }

    // `points` closest to the screen centre first; `pixelSize` is their longest side on screen.
    public setView(points: PointData[], pixelSize: number) {
        this.view = points
        this.size = SIZES.find(s => s >= pixelSize) ?? SIZES[SIZES.length - 1]
        this.dirty = true
    }

    public updatePositions() {
        this.tiles.forEach((tile, p) => tile.mesh.position.set(p.x, p.y, p.z + DETAIL_Z_OFFSET))
    }

    public updateStyles() {
        this.tiles.forEach((tile, p) => this.applyStyle(tile, p))
    }

    // Once per frame: applies a changed view or newly loaded images, and fades in new tiles.
    public tick() {
        if (this.dirty) this.sync()
        this.tiles.forEach(tile => {
            if (tile.opacity >= 1) return
            tile.opacity = Math.min(1, tile.opacity + FADE_STEP)
            tile.material.opacity = tile.opacity
        })
    }

    private sync() {
        this.dirty = false
        const now = ++this.frame
        const shown = new Set<PointData>()
        const missing: string[] = []
        let created = 0

        for (const p of this.view) {
            const key = textureKey(p.sha1, this.size)
            if (!this.textures.has(key)) missing.push(p.sha1)
            const best = this.bestTexture(p.sha1)
            if (!best) continue
            const cached = this.textures.get(best)!
            cached.lastUsed = now

            let tile = this.tiles.get(p)
            if (!tile) {
                if (created >= MAX_NEW_TILES_PER_FRAME) {
                    this.dirty = true
                    continue
                }
                tile = this.createTile(p, best, cached.texture)
                created++
            } else if (tile.key !== best) {
                tile.key = best
                tile.material.map = cached.texture
                this.applyShape(tile, p)
            }
            tile.mesh.position.set(p.x, p.y, p.z + DETAIL_Z_OFFSET)
            shown.add(p)
        }

        this.tiles.forEach((tile, p) => { if (!shown.has(p)) this.removeTile(p, tile) })
        this.requestLoads(missing)
        this.evict(now)
    }

    // The cached image closest to the wanted size, preferring bigger ones.
    private bestTexture(sha1: string): string | null {
        const wanted = SIZES.indexOf(this.size)
        for (let i = wanted; i < SIZES.length; i++) {
            const key = textureKey(sha1, SIZES[i])
            if (this.textures.has(key)) return key
        }
        for (let i = wanted - 1; i >= 0; i--) {
            const key = textureKey(sha1, SIZES[i])
            if (this.textures.has(key)) return key
        }
        return null
    }

    private createTile(p: PointData, key: string, texture: THREE.Texture): Tile {
        const material = new HDImageMaterial({ map: texture, transparent: true })
        material.setZoomReference(this.zoomRef)
        material.setZoomParams(this.zoomParams)
        material.setTintBorder(true)
        material.opacity = 0

        const mesh = new THREE.Mesh(sharedPlaneGeo, material)
        mesh.renderOrder = DETAIL_RENDER_ORDER
        // The shader sizes the quad, so the geometry's bounds say nothing about what is on screen.
        mesh.frustumCulled = false
        this.group.add(mesh)

        const tile = { mesh, material, key, opacity: 0 }
        this.applyShape(tile, p)
        this.applyStyle(tile, p)
        this.tiles.set(p, tile)
        return tile
    }

    // Same shape as the atlas thumbnail: the whole image with rounded corners, or a centred
    // square crop in a filled grid. The texture is not flipped on upload, so v is reversed here.
    private applyShape(tile: Tile, p: PointData) {
        const m = tile.material
        if (this.fill) {
            const image = tile.material.map!.image as ImageBitmap
            const ratio = image.width / image.height
            const sx = ratio > 1 ? 1 / ratio : 1
            const sy = ratio > 1 ? 1 : ratio
            m.setRatio(1)
            m.setRadius(0)
            m.setUvTransform(sx, -sy, (1 - sx) / 2, 1 - (1 - sy) / 2)
        } else {
            m.setRatio(p.ratio)
            m.setRadius(IMAGE_RADIUS)
            m.setUvTransform(1, -1, 0, 1)
        }
    }

    private applyStyle(tile: Tile, p: PointData) {
        const m = tile.material
        m.setBorder(p.border ?? 0, p.borderColor ?? '#000000')
        m.setTint(p.tint, p.tintAlpha)
        m.setDesaturate(p.desaturate)
    }

    private removeTile(p: PointData, tile: Tile) {
        this.group.remove(tile.mesh)
        tile.material.dispose()
        this.tiles.delete(p)
    }

    private clearTiles() {
        this.tiles.forEach((tile, p) => this.removeTile(p, tile))
    }

    // Loads the missing images in view order and cancels the ones no longer wanted.
    private requestLoads(sha1s: string[]) {
        const wanted = new Set(sha1s.map(sha1 => textureKey(sha1, this.size)))
        this.loads.forEach((controller, key) => { if (!wanted.has(key)) controller.abort() })
        this.queue = sha1s
        this.pump()
    }

    private pump() {
        while (this.loads.size < MAX_PARALLEL_LOADS && this.queue.length) {
            const key = textureKey(this.queue.shift()!, this.size)
            if (this.loads.has(key) || this.textures.has(key) || this.failed.has(key)) continue
            this.load(key)
        }
    }

    private async load(key: string) {
        const controller = new AbortController()
        this.loads.set(key, controller)
        const [sha1, size] = parseKey(key)
        try {
            const res = await fetch(`${this.baseImgUrl}by_size/${sha1}?size=${size}`, { signal: controller.signal })
            if (!res.ok) throw new Error(`${res.status}`)
            const bitmap = await downscale(await createImageBitmap(await res.blob()), size)
            if (this.disposed) {
                bitmap.close()
                return
            }
            const texture = new THREE.Texture(bitmap)
            texture.flipY = false
            texture.colorSpace = THREE.SRGBColorSpace
            texture.needsUpdate = true
            const bytes = Math.round(bitmap.width * bitmap.height * 4 * 4 / 3)
            this.textures.set(key, { texture, bytes, lastUsed: this.frame })
            this.textureBytes += bytes
            this.dirty = true
        } catch {
            // Aborted (out of view) or failed: the atlas thumbnail stays. Failures are not retried.
            if (!controller.signal.aborted) this.failed.add(key)
        } finally {
            if (this.loads.get(key) === controller) this.loads.delete(key)
            if (!this.disposed) this.pump()
        }
    }

    // Frees the least recently used textures that no tile shows until under budget.
    private evict(now: number) {
        if (this.textureBytes <= TEXTURE_BUDGET_BYTES) return
        const old = [...this.textures].filter(([, t]) => t.lastUsed < now).sort((a, b) => a[1].lastUsed - b[1].lastUsed)
        const inUse = new Set([...this.tiles.values()].map(t => t.key))
        for (const [key, cached] of old) {
            if (this.textureBytes <= TEXTURE_BUDGET_BYTES) break
            if (inUse.has(key)) continue
            this.disposeTexture(key, cached)
        }
    }

    private disposeTexture(key: string, cached: CachedTexture) {
        cached.texture.dispose()
        ;(cached.texture.image as ImageBitmap).close()
        this.textures.delete(key)
        this.textureBytes -= cached.bytes
    }

    public dispose() {
        this.disposed = true
        this.loads.forEach(controller => controller.abort())
        this.clearTiles()
        this.textures.forEach((cached, key) => this.disposeTexture(key, cached))
        this.scene.remove(this.group)
    }
}

function textureKey(sha1: string, size: number) {
    return `${size}:${sha1}`
}

function parseKey(key: string): [string, number] {
    const i = key.indexOf(':')
    return [key.slice(i + 1), Number(key.slice(0, i))]
}

// The server sends the original file when no stored thumbnail is big enough, which can be far
// bigger than what is drawn.
async function downscale(bitmap: ImageBitmap, size: number): Promise<ImageBitmap> {
    const longest = Math.max(bitmap.width, bitmap.height)
    if (longest <= size * 1.5) return bitmap
    const scale = size / longest
    try {
        const scaled = await createImageBitmap(bitmap, {
            resizeWidth: Math.round(bitmap.width * scale),
            resizeHeight: Math.round(bitmap.height * scale),
            resizeQuality: 'high'
        })
        bitmap.close()
        return scaled
    } catch {
        return bitmap
    }
}
