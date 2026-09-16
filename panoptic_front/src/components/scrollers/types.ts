import { Group, ImageIterator } from "@/core/GroupManager"
import { Instance } from "@/data/models"

export interface ScrollerLine {
    id: string | number
    type: string
    groupId?: number
    data: any
    index?: number
    depth?: number
    size: number
}

export interface GroupLine extends ScrollerLine {
    data: Group
    nbClusters: number
}

export interface ImageLine extends ScrollerLine {
    data: ImageIterator[]
    imageSize: number
    emptyCount: number
    // Per-column inner (image) widths, precomputed by the scroller so the cells add up to
    // exactly the line width. Length == cells-per-line; leading columns may be 1px wider to
    // absorb the flooring remainder. Indexed by column, so empty trailing slots reuse the
    // same entry as the column they sit under.
    cardWidths: number[]
}

export interface RowLine extends ScrollerLine {
    data: Instance,
}

// A sha1 pile row in the grid. `data` is a lightweight handle into the leaf's pile
// overlay (no per-sha1 Group is materialized anymore).
export interface PileHandle {
    groupId: number
    pileIndex: number
    slots: number[]
}

export interface PileRowLine extends ScrollerLine {
    data: PileHandle
}

export interface ScrollerPileLine extends ScrollerLine {
    data: ImageIterator[]
    imageSize: number
    emptyCount: number
    // See ImageLine.cardWidths — same precomputed per-column widths for pile rows.
    cardWidths: number[]
}

// How a group card renders its images: one representative image, or a mosaic of the first few —
// either one large image on the left half plus a grid on the right ('mosaic'), or a plain
// uniform grid over the whole card ('mosaic-large').
export type GroupViewMode = 'single' | 'mosaic' | 'mosaic-large'

// Each mosaic mode's grid (columns × rows) and whether a large image takes the left half, hence
// how many images a card shows: (big ? 1 : 0) + cols * rows. Shared by the scroller (image
// preloading) and the card layout.
export const MOSAIC_GRID: Record<GroupViewMode, { big: boolean, cols: number, rows: number }> = {
    'single': { big: false, cols: 0, rows: 0 },
    'mosaic': { big: true, cols: 1, rows: 2 },
    'mosaic-large': { big: false, cols: 3, rows: 3 },
}

export function mosaicSlotCount(mode: GroupViewMode): number {
    const g = MOSAIC_GRID[mode] ?? MOSAIC_GRID.single
    if (!g.cols || !g.rows) return 1
    return (g.big ? 1 : 0) + g.cols * g.rows
}

export interface ClusterLine extends ScrollerLine {
    data: { group: Group, slot: number }[]
    imageSize: number
    emptyCount: number
    // Per-column inner (image) widths, precomputed by the scroller so the cards add
    // up to exactly the line width. Length == cards-per-line; the leading columns may
    // be 1px wider to absorb the flooring remainder. Indexed by column, so empty
    // trailing slots reuse the same entry as the column they sit under.
    cardWidths: number[]
}
