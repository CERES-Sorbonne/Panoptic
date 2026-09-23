export interface VectorDescription {
    source: string
    type: string
    count?: number
}

export interface ProjectVectorDescription {
    vectors: VectorDescription[]
    defaultVectors: VectorDescription
}

export interface VectorType {
    id: number
    source: string
    params: any
}

export interface VectorStats {
    count: { [id: number]: number }
    sha1Count: number
}

export interface Score {
    value: number
    min: number
    max: number
    description: string
    maxIsBest: boolean
}

export interface ScoreList {
    values: number[]
    min: number
    max: number
    description: string
    maxIsBest: boolean
}

export interface GroupScoreList {
    valueIndex: ScoreIndex
    min: number
    max: number
    description: string
    maxIsBest: boolean
}

export interface ScoreIndex {
    [instanceId: number]: number
}

export interface PointMap {
    id: number
    source: string
    name: string
    key: string
    count: number
    data?: any[]
}

export interface MapIndex {
    [mapId: number]: PointMap
}

export interface BoundingBox {
    minX: number
    minY: number
    maxX: number
    maxY: number 
    color: string
}

// Atlas
export interface ImageAtlas {
    id: number
    atlasNb: number
    width: number
    height: number
    cellWidth: number
    cellHeight: number
    sha1Mapping: Record<string, [number, number]>
    // Client-side only: bumped each time the atlas is (re)fetched. The backend always
    // reuses id 0, so this is what tells the renderer that the sheets on disk changed.
    version?: number
}

export interface ZoomParams {
    h: number
    z1: number
    z2: number
}

export interface PointData {
    x: number
    y: number
    z: number
    color: string
    tint?: string,
    tintAlpha: number
    // 0 = full colour, 1 = fully desaturated (per-pixel greyscale, not a flat colour wash — kept
    // separate from tint so "dim this group" and "tint this selection" can compose independently.
    desaturate?: number
    sha1: string
    ratio: number,
    id?: number,
    border?: number
    borderColor?: string
    order: number
}

export interface PointIndex { [pointId: number]: PointData }
