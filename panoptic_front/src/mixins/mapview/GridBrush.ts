import type { Cell } from './GridSnake'

// Mouse modes driving the cell cursor: selection, and the tag brush.
export function isCellTool(mode: string) {
    return mode === 'cells' || mode === 'paint'
}

// Inclusive bounds, in cells.
export interface CellRect { c0: number, r0: number, c1: number, r1: number }

export const MAX_BRUSH_SIZE = 128
// Below this size the brush grows one cell per wheel notch, above it by a ratio.
const LINEAR_BRUSH_SIZES = 8
const BRUSH_GROWTH = 1.25

// Position in cell units: cell (c, r) spans [c, c + 1) × [r, r + 1). The grid is centred on the
// origin (see GridLayout.cellCenter).
export function worldToGrid(x: number, y: number, cols: number, rows: number, cellSize: number) {
    return { u: x / cellSize + cols / 2, v: y / cellSize + rows / 2 }
}

export function cellAt(u: number, v: number): Cell {
    return { c: Math.floor(u), r: Math.floor(v) }
}

// Square brush of `size` cells around a position: centred on the cell under it for odd sizes, on
// the nearest cell corner for even ones.
export function brushRectAt(u: number, v: number, size: number): CellRect {
    const c0 = Math.round(u - size / 2)
    const r0 = Math.round(v - size / 2)
    return { c0, r0, c1: c0 + size - 1, r1: r0 + size - 1 }
}

export function rectBetween(a: Cell, b: Cell): CellRect {
    return { c0: Math.min(a.c, b.c), r0: Math.min(a.r, b.r), c1: Math.max(a.c, b.c), r1: Math.max(a.r, b.r) }
}

export function clipRect(rect: CellRect, cols: number, rows: number): CellRect | null {
    const c0 = Math.max(0, rect.c0), r0 = Math.max(0, rect.r0)
    const c1 = Math.min(cols - 1, rect.c1), r1 = Math.min(rows - 1, rect.r1)
    return c0 <= c1 && r0 <= r1 ? { c0, r0, c1, r1 } : null
}

// Cells of the segment a → b (Bresenham), both ends included.
export function lineCells(a: Cell, b: Cell): Cell[] {
    const res: Cell[] = []
    const dc = Math.abs(b.c - a.c), dr = Math.abs(b.r - a.r)
    const sc = a.c < b.c ? 1 : -1, sr = a.r < b.r ? 1 : -1
    let c = a.c, r = a.r, err = dc - dr
    for (;;) {
        res.push({ c, r })
        if (c === b.c && r === b.r) return res
        const e2 = 2 * err
        if (e2 > -dr) { err -= dr; c += sc }
        if (e2 < dc) { err += dc; r += sr }
    }
}

export function nextBrushSize(size: number, dir: 1 | -1): number {
    let next: number
    if (dir > 0) next = size < LINEAR_BRUSH_SIZES ? size + 1 : Math.round(size * BRUSH_GROWTH)
    else next = size <= LINEAR_BRUSH_SIZES ? size - 1 : Math.max(LINEAR_BRUSH_SIZES, Math.round(size / BRUSH_GROWTH))
    return Math.max(1, Math.min(MAX_BRUSH_SIZE, next))
}

/**
 * The cells one gesture covers on a cols × rows grid: a brush dragged across it, or a rectangle.
 * A fast drag jumps several cells between two mouse events, so each stamp joins the previous one
 * with a line of stamps.
 */
export class CellStroke {
    readonly cols: number
    readonly rows: number
    // 1 for each covered cell, indexed row * cols + col.
    readonly marks: Uint8Array
    private last: Cell | null = null

    constructor(cols: number, rows: number) {
        this.cols = cols
        this.rows = rows
        this.marks = new Uint8Array(cols * rows)
    }

    // Brush of `size` cells at a position, joined to the previous stamp.
    public stamp(u: number, v: number, size: number) {
        const rect = brushRectAt(u, v, size)
        const corner = { c: rect.c0, r: rect.r0 }
        const path = this.last ? lineCells(this.last, corner) : [corner]
        for (const p of path) this.fill({ c0: p.c, r0: p.r, c1: p.c + size - 1, r1: p.r + size - 1 })
        this.last = corner
    }

    // Covers exactly the rectangle between two cells, dropping what it covered before.
    public setRect(a: Cell, b: Cell) {
        this.marks.fill(0)
        this.fill(rectBetween(a, b))
    }

    public cells(): number[] {
        const res: number[] = []
        for (let i = 0; i < this.marks.length; i++) if (this.marks[i]) res.push(i)
        return res
    }

    private fill(rect: CellRect) {
        const clipped = clipRect(rect, this.cols, this.rows)
        if (!clipped) return
        for (let r = clipped.r0; r <= clipped.r1; r++) {
            this.marks.fill(1, r * this.cols + clipped.c0, r * this.cols + clipped.c1 + 1)
        }
    }
}
