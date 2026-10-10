import * as THREE from 'three'
import { groupIslands, groupStrokes, STROKE_STRIDE, type Island } from './GridRegions'

export interface RegionGrid {
    cols: number
    rows: number
    cellSize: number
    // Group index per cell (row * cols + col), -1 for an empty cell.
    cellGroup: Int32Array
    groups: { name: string, color: string }[]
}

// Outline thickness on screen (px), capped at a share of a cell so that, zoomed out, a stroke
// never spills over the next cells.
const STROKE_PX = 3
const STROKE_MAX_CELL = 0.25
// Over the detail tiles (1000), under the cell tool (1500).
const RENDER_ORDER = 1400
// Labels show while thumbnails are drawn smaller than this (px): zoomed in, the images speak for
// themselves and a label would cover them.
const LABEL_MAX_CELL_PX = 40
// An island gets a label once it is about this wide on screen (px).
const LABEL_MIN_ISLAND_PX = 60
const MAX_LABELS = 60
// Rough label box (px) for the overlap test, without measuring the DOM every frame.
const LABEL_CHAR_PX = 7
const LABEL_PAD_PX = 26
const LABEL_HEIGHT_PX = 22

/**
 * Group outlines of the grid layout, in each group's colour, and the group's name over each large
 * enough island at low zoom, so the map reads like a geographic one. Outlines are drawn in the
 * scene; labels are HTML over the canvas so the text stays sharp.
 */
export class GridRegionsLayer {
    private scene: THREE.Scene
    // Each stroke is a quad: two vertices on the cell edge, two pushed into the group's cells by
    // `aOffset * uThickness`, so the thickness follows the zoom without rebuilding the geometry.
    private strokes: THREE.Mesh
    private thickness = { value: 0 }
    private material = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, side: THREE.DoubleSide, depthTest: false, depthWrite: false })
    private overlay: HTMLDivElement
    private labels: HTMLDivElement[] = []

    private grid: RegionGrid | null = null
    private islands: Island[] = []
    private viewKey = ''

    constructor(scene: THREE.Scene, container: HTMLElement) {
        this.scene = scene
        this.material.onBeforeCompile = (shader) => {
            shader.uniforms.uThickness = this.thickness
            shader.vertexShader = 'attribute vec2 aOffset;\nuniform float uThickness;\n' + shader.vertexShader.replace(
                '#include <begin_vertex>',
                '#include <begin_vertex>\ntransformed.xy += aOffset * uThickness;'
            )
        }
        this.strokes = new THREE.Mesh(new THREE.BufferGeometry(), this.material)
        this.strokes.renderOrder = RENDER_ORDER
        this.strokes.frustumCulled = false
        this.strokes.visible = false
        this.scene.add(this.strokes)

        if (getComputedStyle(container).position === 'static') container.style.position = 'relative'
        this.overlay = document.createElement('div')
        Object.assign(this.overlay.style, { position: 'absolute', inset: '0', overflow: 'hidden', pointerEvents: 'none' })
        container.appendChild(this.overlay)
    }

    public setGrid(grid: RegionGrid | null) {
        this.grid = grid
        this.viewKey = ''
        this.strokes.geometry.dispose()
        this.strokes.geometry = new THREE.BufferGeometry()
        this.strokes.visible = !!grid
        this.islands = []
        if (!grid) {
            this.hideLabels(0)
            return
        }
        const { cols, rows, cellSize, cellGroup } = grid
        const strokes = groupStrokes(cellGroup, cols, rows)
        const count = strokes.length / STROKE_STRIDE
        const positions = new Float32Array(count * 6 * 3)
        const offsets = new Float32Array(count * 6 * 2)
        const colors = new Float32Array(count * 6 * 3)
        const groupColors = grid.groups.map(g => new THREE.Color(g.color))
        const fallback = new THREE.Color('#777777')
        for (let s = 0; s < count; s++) {
            const o = s * STROKE_STRIDE
            const x0 = (strokes[o] - cols / 2) * cellSize, y0 = (strokes[o + 1] - rows / 2) * cellSize
            const x1 = (strokes[o + 2] - cols / 2) * cellSize, y1 = (strokes[o + 3] - rows / 2) * cellSize
            const nx = strokes[o + 4], ny = strokes[o + 5]
            const color = groupColors[strokes[o + 6]] ?? fallback
            // Two triangles: edge start, edge end, inner end / edge start, inner end, inner start.
            const corners: [number, number, number][] = [[x0, y0, 0], [x1, y1, 0], [x1, y1, 1], [x0, y0, 0], [x1, y1, 1], [x0, y0, 1]]
            corners.forEach(([x, y, inner], k) => {
                const v = s * 6 + k
                positions[v * 3] = x
                positions[v * 3 + 1] = y
                offsets[v * 2] = nx * inner
                offsets[v * 2 + 1] = ny * inner
                colors[v * 3] = color.r
                colors[v * 3 + 1] = color.g
                colors[v * 3 + 2] = color.b
            })
        }
        this.strokes.geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
        this.strokes.geometry.setAttribute('aOffset', new THREE.BufferAttribute(offsets, 2))
        this.strokes.geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
        this.islands = groupIslands(cellGroup, cols, rows)
    }

    // `view`: the camera's world rect. Called every frame; only re-lays the labels when the view
    // changed.
    public update(view: { minX: number, maxX: number, minY: number, maxY: number }, width: number, height: number) {
        const grid = this.grid
        if (!grid || !width || !height) return
        const key = `${view.minX},${view.maxX},${view.minY},${view.maxY},${width},${height}`
        if (key === this.viewKey) return
        this.viewKey = key

        const pxPerWorld = width / (view.maxX - view.minX)
        const cellPx = grid.cellSize * pxPerWorld
        this.thickness.value = Math.min(STROKE_PX / pxPerWorld, STROKE_MAX_CELL * grid.cellSize)
        if (cellPx >= LABEL_MAX_CELL_PX) {
            this.hideLabels(0)
            return
        }

        const placed: { x0: number, y0: number, x1: number, y1: number }[] = []
        let count = 0
        for (const island of this.islands) {
            if (count >= MAX_LABELS) break
            // Largest first: once islands are too small, the rest are too.
            if (Math.sqrt(island.size) * cellPx < LABEL_MIN_ISLAND_PX) break
            const group = grid.groups[island.group]
            if (!group) continue
            const x = ((island.c + 0.5 - grid.cols / 2) * grid.cellSize - view.minX) * pxPerWorld
            const y = (view.maxY - (island.r + 0.5 - grid.rows / 2) * grid.cellSize) * pxPerWorld
            const w = group.name.length * LABEL_CHAR_PX + LABEL_PAD_PX
            const box = { x0: x - w / 2, y0: y - LABEL_HEIGHT_PX / 2, x1: x + w / 2, y1: y + LABEL_HEIGHT_PX / 2 }
            if (box.x1 < 0 || box.x0 > width || box.y1 < 0 || box.y0 > height) continue
            if (placed.some(b => b.x0 < box.x1 && box.x0 < b.x1 && b.y0 < box.y1 && box.y0 < b.y1)) continue
            placed.push(box)
            this.showLabel(count++, group, x, y)
        }
        this.hideLabels(count)
    }

    private showLabel(i: number, group: { name: string, color: string }, x: number, y: number) {
        let el = this.labels[i]
        if (!el) {
            el = document.createElement('div')
            Object.assign(el.style, {
                position: 'absolute', left: '0', top: '0', display: 'flex', alignItems: 'center', gap: '5px',
                padding: '2px 8px', borderRadius: '10px', whiteSpace: 'nowrap',
                font: '600 12px/16px system-ui, sans-serif', color: '#1f2328',
                background: 'rgba(255, 255, 255, 0.88)', boxShadow: '0 1px 3px rgba(0, 0, 0, 0.18)',
            })
            const dot = document.createElement('span')
            Object.assign(dot.style, { width: '8px', height: '8px', borderRadius: '50%', flexShrink: '0' })
            el.append(dot, document.createElement('span'))
            this.overlay.appendChild(el)
            this.labels[i] = el
        }
        ;(el.firstChild as HTMLElement).style.backgroundColor = group.color
        if (el.lastChild!.textContent !== group.name) el.lastChild!.textContent = group.name
        el.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px) translate(-50%, -50%)`
        el.style.display = 'flex'
    }

    private hideLabels(from: number) {
        for (let i = from; i < this.labels.length; i++) this.labels[i].style.display = 'none'
    }

    public dispose() {
        this.scene.remove(this.strokes)
        this.strokes.geometry.dispose()
        this.material.dispose()
        this.overlay.remove()
    }
}
