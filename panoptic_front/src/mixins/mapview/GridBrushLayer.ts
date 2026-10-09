import * as THREE from 'three'
import { PointData } from '@/data/models'
import { brushRectAt, cellAt, CellStroke, rectBetween, worldToGrid, type CellRect } from './GridBrush'
import type { Cell } from './GridSnake'

export interface BrushGrid {
    cols: number
    rows: number
    cellSize: number
    // For each cell (row * cols + col), the index in `points` of the image drawn there, or -1.
    cellPoint: Int32Array
    points: PointData[]
}

const ADD_COLOR = new THREE.Color('#5dacff')
const REMOVE_COLOR = new THREE.Color('#d63939')
const ADD_FRAME = new THREE.Color('#0077cc')
const COVER_ALPHA = 130
const CURSOR_ALPHA = 0.12
// Over the detail tiles (1000), under the HD hover preview (2000+).
const RENDER_ORDER = 1500

/**
 * Cell tool of the grid layout: a square cursor of a few cells, dragged to cover cells or, from a
 * Shift press, a rectangle. The images under the covered cells are tinted during the gesture and
 * handed to `onCommit` when it ends.
 */
export class GridBrushLayer {
    private scene: THREE.Scene
    private onCommit: (points: PointData[], remove: boolean) => void
    private group = new THREE.Group()
    private plane = new THREE.PlaneGeometry(1, 1)

    // Covered cells: one texel per cell, laid over the whole grid.
    private cover: THREE.Mesh
    private coverMaterial = new THREE.MeshBasicMaterial({ transparent: true, depthTest: false, depthWrite: false })
    private coverTexture: THREE.DataTexture | null = null

    private cursor: THREE.Mesh
    private cursorMaterial = new THREE.MeshBasicMaterial({ transparent: true, opacity: CURSOR_ALPHA, depthTest: false, depthWrite: false })
    private cursorFrameMaterial = new THREE.LineBasicMaterial({ transparent: true, depthTest: false, depthWrite: false })

    private grid: BrushGrid | null = null
    private size = 1
    private stroke: CellStroke | null = null
    private remove = false
    private rectStart: Cell | null = null
    private pressCell: Cell = { c: 0, r: 0 }
    private cursorKey = ''

    constructor(scene: THREE.Scene, onCommit: (points: PointData[], remove: boolean) => void) {
        this.scene = scene
        this.onCommit = onCommit
        this.cover = new THREE.Mesh(this.plane, this.coverMaterial)
        this.cover.renderOrder = RENDER_ORDER
        this.cover.visible = false

        this.cursor = new THREE.Mesh(this.plane, this.cursorMaterial)
        const loop = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(-0.5, -0.5, 0), new THREE.Vector3(0.5, -0.5, 0),
            new THREE.Vector3(0.5, 0.5, 0), new THREE.Vector3(-0.5, 0.5, 0),
        ])
        this.cursor.add(new THREE.LineLoop(loop, this.cursorFrameMaterial))
        this.cursor.renderOrder = RENDER_ORDER + 1
        this.cursor.children[0].renderOrder = RENDER_ORDER + 2
        this.cursor.visible = false

        this.group.add(this.cover, this.cursor)
        this.scene.add(this.group)
        this.setColors()
    }

    public get active() {
        return this.stroke != null
    }

    public setGrid(grid: BrushGrid | null) {
        this.cancel()
        this.grid = grid
        this.cursor.visible = false
        this.cursorKey = ''
        if (!grid) return
        const { cols, rows, cellSize } = grid
        const img = this.coverTexture?.image
        if (!img || img.width !== cols || img.height !== rows) {
            this.coverTexture?.dispose()
            this.coverTexture = new THREE.DataTexture(new Uint8Array(cols * rows * 4), cols, rows, THREE.RGBAFormat)
            this.coverTexture.magFilter = THREE.NearestFilter
            this.coverTexture.minFilter = THREE.NearestFilter
            this.coverTexture.colorSpace = THREE.SRGBColorSpace
            this.coverTexture.needsUpdate = true
            this.coverMaterial.map = this.coverTexture
            this.coverMaterial.needsUpdate = true
        }
        this.cover.scale.set(cols * cellSize, rows * cellSize, 1)
    }

    public setSize(size: number) {
        this.size = size
        this.cursorKey = ''
    }

    // Cursor position (world), or null when the pointer is off the map. Called every frame.
    public hover(world: { x: number, y: number } | null) {
        if (!this.grid || !world) {
            if (!this.stroke) this.cursor.visible = false
            this.cursorKey = ''
            return
        }
        const { u, v } = this.toGrid(world)
        const rect = this.rectStart ? rectBetween(this.rectStart, cellAt(u, v)) : brushRectAt(u, v, this.size)
        const key = `${rect.c0},${rect.r0},${rect.c1},${rect.r1}`
        if (key === this.cursorKey) return
        this.cursorKey = key
        this.placeCursor(rect)
    }

    public start(world: { x: number, y: number }, remove: boolean, rect: boolean) {
        if (!this.grid) return
        this.stroke = new CellStroke(this.grid.cols, this.grid.rows)
        this.remove = remove
        this.setColors()
        const { u, v } = this.toGrid(world)
        this.pressCell = cellAt(u, v)
        this.rectStart = null
        this.cursorKey = ''
        this.move(world, rect)
    }

    // Shift pressed during a drag turns it into a rectangle from the press cell: Firefox keeps the
    // context menu for Shift + right press, but not for a right press then Shift.
    public move(world: { x: number, y: number }, rect = false) {
        if (!this.stroke) return
        if (rect && !this.rectStart) this.rectStart = this.pressCell
        const { u, v } = this.toGrid(world)
        if (this.rectStart) this.stroke.setRect(this.rectStart, cellAt(u, v))
        else this.stroke.stamp(u, v, this.size)
        this.paintCover()
        this.hover(world)
    }

    public end() {
        const stroke = this.stroke
        const grid = this.grid
        const remove = this.remove
        this.cancel()
        if (!stroke || !grid) return
        const points: PointData[] = []
        for (const cell of stroke.cells()) {
            const i = grid.cellPoint[cell]
            if (i >= 0) points.push(grid.points[i])
        }
        if (points.length) this.onCommit(points, remove)
    }

    public cancel() {
        this.stroke = null
        this.rectStart = null
        this.remove = false
        this.cover.visible = false
        this.cursorKey = ''
        this.setColors()
    }

    private toGrid(world: { x: number, y: number }) {
        const { cols, rows, cellSize } = this.grid!
        return worldToGrid(world.x, world.y, cols, rows, cellSize)
    }

    private placeCursor(rect: CellRect) {
        const { cols, rows, cellSize } = this.grid!
        const w = rect.c1 - rect.c0 + 1, h = rect.r1 - rect.r0 + 1
        this.cursor.position.set((rect.c0 + w / 2 - cols / 2) * cellSize, (rect.r0 + h / 2 - rows / 2) * cellSize, 0)
        this.cursor.scale.set(w * cellSize, h * cellSize, 1)
        this.cursor.visible = true
    }

    // Tints the covered cells that hold an image: those are what the gesture will act on.
    private paintCover() {
        const texture = this.coverTexture
        if (!this.stroke || !this.grid || !texture) return
        const data = texture.image.data as Uint8Array
        const color = this.remove ? REMOVE_COLOR : ADD_COLOR
        const r = Math.round(color.r * 255), g = Math.round(color.g * 255), b = Math.round(color.b * 255)
        const marks = this.stroke.marks
        const cellPoint = this.grid.cellPoint
        for (let i = 0; i < marks.length; i++) {
            const o = i * 4
            if (marks[i] && cellPoint[i] >= 0) {
                data[o] = r; data[o + 1] = g; data[o + 2] = b; data[o + 3] = COVER_ALPHA
            } else {
                data[o + 3] = 0
            }
        }
        texture.needsUpdate = true
        this.cover.visible = true
    }

    private setColors() {
        this.cursorMaterial.color.copy(this.remove ? REMOVE_COLOR : ADD_COLOR)
        this.cursorFrameMaterial.color.copy(this.remove ? REMOVE_COLOR : ADD_FRAME)
    }

    public dispose() {
        this.scene.remove(this.group)
        this.plane.dispose()
        this.coverTexture?.dispose()
        this.coverMaterial.dispose()
        this.cursorMaterial.dispose()
        this.cursorFrameMaterial.dispose()
        ;(this.cursor.children[0] as THREE.LineLoop).geometry.dispose()
    }
}
