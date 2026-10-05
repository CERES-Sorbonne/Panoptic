import { FileSourceIndex, FolderIndex, PropertyType } from '@/data/models'

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

/**
 * Drop deleted tag ids out of one tag column, in place. Returns the slots whose value changed.
 *
 * A tag delete is soft — the tag object is tombstoned so anything still holding its id can
 * resolve a label — but the loaded column keeps the id, and a column that names a tag which no
 * longer exists is wrong data: the tree keeps a group for it until something recomputes, and
 * the group has no label to draw. Scrubbing here is what makes the stored value honest and
 * gives the recompute the exact set of instances to run on.
 *
 * A slot left with no tags becomes null, the same "no value" a slot that never had one holds.
 */
export function stripTagIds(sparse: TagSparse, count: number, drop: Set<number>): number[] {
    if (!drop.size) return []
    const changed: number[] = []
    for (let s = 0; s < count; s++) {
        const tags = sparse[s]
        if (!tags?.length) continue
        let hit = false
        for (let i = 0; i < tags.length; i++) if (drop.has(tags[i])) { hit = true; break }
        if (!hit) continue
        const next = tags.filter(t => !drop.has(t))
        sparse[s] = next.length ? next : null
        changed.push(s)
    }
    return changed
}

/** Slots of one tag column whose value names any of `tagIds`. Read only. */
export function slotsWithTagIds(sparse: TagSparse, count: number, tagIds: Set<number>): number[] {
    if (!tagIds.size) return []
    const hits: number[] = []
    for (let s = 0; s < count; s++) {
        const tags = sparse[s]
        if (!tags?.length) continue
        for (let i = 0; i < tags.length; i++) if (tagIds.has(tags[i])) { hits.push(s); break }
    }
    return hits
}

/**
 * A column built in the browser from columns that are already loaded, instead of streamed.
 * `build` runs once per fill and returns the per-slot reader, so it can prepare lookups first.
 */
export interface DerivedColumn {
    deps: number[]
    build: () => (slot: number) => any
}

/**
 * Per-folder prefix of the `path` metadata: a file path is `prefix + file name`. An IIIF file
 * name is already the full URL, so its prefix is empty. A folder with no path gets no prefix.
 *
 * Mirrors DataReader._file_paths on the backend: keep the two in step.
 */
export function folderPathPrefixes(folders: FolderIndex, sources: FileSourceIndex): Map<number, string> {
    const prefixes = new Map<number, string>()
    for (const key in folders) {
        const folder = folders[key]
        if (folder.sourceId != null && sources[folder.sourceId]?.dtype === 'iiif') prefixes.set(folder.id, '')
        else if (folder.path != null) prefixes.set(folder.id, folder.path + '/')
    }
    return prefixes
}
