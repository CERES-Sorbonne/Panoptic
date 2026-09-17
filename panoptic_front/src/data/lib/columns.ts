import { PropertyType } from '@/data/models'

export type TagSparse = (number[] | null)[]
export type TagCSR = { offsets: Int32Array; values: Int32Array }

export type ColumnData =
    | { kind: 'numeric'; data: Float64Array }
    | { kind: 'bool'; data: Uint8Array }
    | { kind: 'string'; data: (string | null)[] }
    | { kind: 'tag'; sparse: TagSparse; csr?: TagCSR }

export function propertyKind(type: PropertyType): ColumnData['kind'] {
    if (
        type === PropertyType.number || type === PropertyType.date ||
        type === PropertyType.color || type === PropertyType._width ||
        type === PropertyType._height || type === PropertyType._id
    ) return 'numeric'
    if (type === PropertyType.checkbox) return 'bool'
    if (type === PropertyType.multi_tags || type === PropertyType.tag) return 'tag'
    return 'string'
}

export function makeColumn(kind: ColumnData['kind'], size: number): ColumnData {
    switch (kind) {
        case 'numeric': {
            const data = new Float64Array(size)
            data.fill(NaN)
            return { kind, data }
        }
        case 'bool': return { kind, data: new Uint8Array(size).fill(255) }
        case 'string': return { kind, data: new Array(size).fill(null) }
        case 'tag': return { kind, sparse: new Array(size).fill(null) }
    }
}

export function growColumn(col: ColumnData, oldSize: number, newSize: number): ColumnData {
    switch (col.kind) {
        case 'numeric': {
            const data = new Float64Array(newSize).fill(NaN)
            data.set(col.data)
            return { kind: 'numeric', data }
        }
        case 'bool': {
            const data = new Uint8Array(newSize).fill(255)
            data.set(col.data)
            return { kind: 'bool', data }
        }
        case 'string': {
            const data: (string | null)[] = new Array(newSize).fill(null)
            for (let i = 0; i < oldSize; i++) data[i] = col.data[i]
            return { kind: 'string', data }
        }
        case 'tag': {
            const sparse: TagSparse = new Array(newSize).fill(null)
            for (let i = 0; i < oldSize; i++) sparse[i] = col.sparse[i]
            return { kind: 'tag', sparse }
        }
    }
}

export function buildCSR(sparse: TagSparse, count: number): TagCSR {
    const offsets = new Int32Array(count + 1)
    let total = 0
    for (let s = 0; s < count; s++) {
        total += sparse[s]?.length ?? 0
        offsets[s + 1] = total
    }
    const values = new Int32Array(total)
    let pos = 0
    for (let s = 0; s < count; s++) {
        const tags = sparse[s]
        if (tags) for (const t of tags) values[pos++] = t
    }
    return { offsets, values }
}
