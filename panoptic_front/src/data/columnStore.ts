import { defineStore } from 'pinia'
import { markRaw, reactive, ref } from 'vue'
import { LoadResult, PropertyType } from './models'
import { apiStreamInstanceBase, projectApi } from './apiProjectRoutes'
import { EventEmitter } from '@/utils/utils'

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

export const useColumnStore = defineStore('columnStore', () => {

    let _instanceIdPropId: number | null = null
    let _sha1PropId: number | null = null
    let _fileIdPropId: number | null = null

    const slotMap = markRaw(new Map<number, number>())
    let slotCount = 0
    let deletedMask = new Uint8Array(0)
    let selectionMask = new Uint8Array(0)

    let instanceIds = new Int32Array(0)
    let sha1s: (string | null)[] = []
    let fileIds = new Int32Array(0)

    const columnData: Record<number, ColumnData> = markRaw({})
    const columnFetched: Record<number, Uint8Array> = markRaw({})
    const _propTypes: Record<number, PropertyType> = markRaw({})

    const fullColumnStatus = reactive<Record<number, 'empty' | 'loading' | 'loaded'>>({})
    const _fullColumnPromise: Record<number, Promise<void>> = {}

    const tagInverted: Record<number, Int32Array> = markRaw({})
    const _tagInvertedPromise: Record<number, Promise<void>> = {}

    const onSelectionChange = new EventEmitter()
    const isReady = ref(false)
    const instanceCount = ref(0)

    const systemProps = {
        get INSTANCE_ID() { return _instanceIdPropId },
        get SHA1() { return _sha1PropId },
        get FILE_ID() { return _fileIdPropId }
    }

    async function init(instanceIdPropId: number, sha1PropId: number, fileIdPropId: number) {
        _instanceIdPropId = instanceIdPropId
        _sha1PropId = sha1PropId
        _fileIdPropId = fileIdPropId

        registerProperty(instanceIdPropId, PropertyType.number)
        registerProperty(sha1PropId, PropertyType.string)
        registerProperty(fileIdPropId, PropertyType.number)

        fullColumnStatus[instanceIdPropId] = 'loading'
        fullColumnStatus[sha1PropId] = 'loading'
        fullColumnStatus[fileIdPropId] = 'loading'

        await apiStreamInstanceBase((batch) => {
            const oldSize = slotCount
            const newSize = oldSize + batch.ids.length

            const newDeletedMask = new Uint8Array(newSize)
            newDeletedMask.set(deletedMask)
            deletedMask = newDeletedMask

            const newSelectionMask = new Uint8Array(newSize)
            newSelectionMask.set(selectionMask)
            selectionMask = newSelectionMask

            const newInstanceIds = new Int32Array(newSize)
            newInstanceIds.set(instanceIds)
            instanceIds = newInstanceIds

            const newFileIds = new Int32Array(newSize)
            newFileIds.set(fileIds)
            fileIds = newFileIds

            const newSha1s: (string | null)[] = new Array(newSize).fill(null)
            for (let i = 0; i < oldSize; i++) newSha1s[i] = sha1s[i]
            sha1s = newSha1s

            for (const propId of Object.keys(columnData).map(Number)) {
                columnData[propId] = growColumn(columnData[propId], oldSize, newSize)
                const newFetched = new Uint8Array(newSize)
                newFetched.set(columnFetched[propId])
                columnFetched[propId] = newFetched
            }

            for (let i = 0; i < batch.ids.length; i++) {
                const s = oldSize + i
                slotMap.set(batch.ids[i], s)
                instanceIds[s] = batch.ids[i]
                sha1s[s] = batch.sha1s[i]
                fileIds[s] = batch.fileIds[i] ?? 0
            }
            slotCount = newSize
        })

        fullColumnStatus[instanceIdPropId] = 'loaded'
        fullColumnStatus[sha1PropId] = 'loaded'
        fullColumnStatus[fileIdPropId] = 'loaded'

        instanceCount.value = slotCount
        isReady.value = true
    }

    function getRawBuffer(propId: number | null): any {
        if (propId === null) return undefined
        if (propId === _instanceIdPropId) return instanceIds
        if (propId === _sha1PropId) return sha1s
        if (propId === _fileIdPropId) return fileIds

        const col = columnData[propId]
        if (!col) return undefined
        return col.kind === 'tag' ? col.sparse : col.data
    }

    function readSlot(propId: number, slot: number): any {
        if (propId === _instanceIdPropId) return isNaN(instanceIds[slot]) ? null : instanceIds[slot]
        if (propId === _sha1PropId) return sha1s[slot]
        if (propId === _fileIdPropId) return isNaN(fileIds[slot]) ? null : fileIds[slot]

        const col = columnData[propId]
        if (!col) return undefined
        switch (col.kind) {
            case 'numeric': {
                const v = col.data[slot]
                if (isNaN(v)) return null
                if (_propTypes[propId] === PropertyType.date) return new Date(v)
                return v
            }
            case 'bool': return col.data[slot] === 255 ? null : col.data[slot] === 1
            case 'string': return col.data[slot]
            case 'tag': return col.sparse[slot]
        }
    }

    function isFetched(propId: number, slot: number): boolean {
        if (propId === _instanceIdPropId || propId === _sha1PropId || propId === _fileIdPropId) return true
        return columnFetched[propId]?.[slot] === 1
    }

    function ensureColumn(propId: number): ColumnData {
        if (propId === _instanceIdPropId || propId === _sha1PropId || propId === _fileIdPropId) {
            throw new Error(`ensureColumn should not be called directly for system properties.`)
        }
        if (!columnData[propId]) {
            const kind = propertyKind(_propTypes[propId] ?? PropertyType.string)
            columnData[propId] = makeColumn(kind, slotCount)
            columnFetched[propId] = new Uint8Array(slotCount)
        }
        return columnData[propId]
    }

    function writeSlot(propId: number, slot: number, value: any) {
        if (propId === _instanceIdPropId) { instanceIds[slot] = value == null ? NaN : Number(value); return }
        if (propId === _sha1PropId) { sha1s[slot] = value ?? null; return }
        if (propId === _fileIdPropId) { fileIds[slot] = value == null ? NaN : Number(value); return }

        const col = ensureColumn(propId)
        switch (col.kind) {
            case 'numeric':
                if (_propTypes[propId] === PropertyType.date && typeof value === 'string') {
                    col.data[slot] = value == null ? NaN : new Date(value).getTime()
                } else {
                    col.data[slot] = value == null ? NaN : Number(value)
                }
                break
            case 'bool':
                col.data[slot] = value == null ? 255 : (value ? 1 : 0)
                break
            case 'string':
                col.data[slot] = value ?? null
                break
            case 'tag':
                col.sparse[slot] = Array.isArray(value) ? value : null
                col.csr = undefined
                break
        }
        columnFetched[propId][slot] = 1
    }

    function registerProperty(propId: number, type: PropertyType) {
        _propTypes[propId] = type
        if (fullColumnStatus[propId] === undefined) {
            fullColumnStatus[propId] = (propId === _instanceIdPropId || propId === _sha1PropId || propId === _fileIdPropId)
                ? 'loaded'
                : 'empty'
        }
    }

    function addInstances(newIds: number[], newSha1s: string[], newFileIds: number[]) {
        if (_instanceIdPropId === null || _sha1PropId === null || _fileIdPropId === null) return

        const oldSize = slotCount
        const newSize = oldSize + newIds.length

        const newDeletedMask = new Uint8Array(newSize)
        newDeletedMask.set(deletedMask)
        deletedMask = newDeletedMask

        const newSelectionMask = new Uint8Array(newSize)
        newSelectionMask.set(selectionMask)
        selectionMask = newSelectionMask

        const newInstanceIdArray = new Int32Array(newSize).fill(NaN)
        newInstanceIdArray.set(instanceIds)
        instanceIds = newInstanceIdArray

        const newFileIdArray = new Int32Array(newSize).fill(NaN)
        newFileIdArray.set(fileIds)
        fileIds = newFileIdArray

        const newSha1Array = new Array(newSize).fill(null)
        for (let i = 0; i < oldSize; i++) newSha1Array[i] = sha1s[i]
        sha1s = newSha1Array

        for (const propId of Object.keys(columnData).map(Number)) {
            columnData[propId] = growColumn(columnData[propId], oldSize, newSize)
            const newFetched = new Uint8Array(newSize)
            newFetched.set(columnFetched[propId])
            columnFetched[propId] = newFetched
        }

        for (let i = 0; i < newIds.length; i++) {
            const s = oldSize + i
            const instanceId = newIds[i]

            slotMap.set(instanceId, s)
            instanceIds[s] = instanceId
            sha1s[s] = newSha1s[i]
            fileIds[s] = newFileIds[i]
        }
        slotCount = newSize
    }

    function markSlotDeleted(instanceId: number) {
        const slot = slotMap.get(instanceId)
        if (slot !== undefined) deletedMask[slot] = 1
    }

    async function requireFullColumn(propId: number): Promise<void> {
        if (fullColumnStatus[propId] === 'loaded') return
        if (_fullColumnPromise[propId]) return _fullColumnPromise[propId]

        if (isReady.value && columnData[propId] !== undefined) {
            fullColumnStatus[propId] = 'loaded'
            return
        }

        fullColumnStatus[propId] = 'loading'
        _fullColumnPromise[propId] = (async () => {
            try {
                const { data } = await projectApi.get(`/instances/column/${propId}`)
                const ids: number[] = data.ids
                const values: any[] = data.values
                for (let i = 0; i < ids.length; i++) {
                    const slot = slotMap.get(ids[i])
                    if (slot !== undefined) writeSlot(propId, slot, values[i])
                }
                const col = columnData[propId]
                if (col?.kind === 'tag') col.csr = buildCSR(col.sparse, slotCount)
                fullColumnStatus[propId] = 'loaded'
            console.log(columnData[propId])
            } catch (e) {
                fullColumnStatus[propId] = 'empty'
                delete _fullColumnPromise[propId]
                throw e
            }
        })()
        return _fullColumnPromise[propId]
    }

    async function requireTagInverted(propId: number): Promise<void> {
        await requireFullColumn(propId)
        if (_tagInvertedPromise[propId]) return _tagInvertedPromise[propId]
        _tagInvertedPromise[propId] = (async () => {
            const col = columnData[propId]
            if (!col || col.kind !== 'tag') return
            const tmp: Record<number, number[]> = {}
            for (let s = 0; s < slotCount; s++) {
                const tags = col.sparse[s]
                if (!tags) continue
                for (const t of tags) {
                    if (!tmp[t]) tmp[t] = []
                    tmp[t].push(s)
                }
            }
            for (const [tagIdStr, slots] of Object.entries(tmp))
                tagInverted[Number(tagIdStr)] = new Int32Array(slots).sort()
        })()
        return _tagInvertedPromise[propId]
    }

    function getFullyLoadedPropIds(): number[] {
        return Object.keys(fullColumnStatus).map(Number).filter(id => fullColumnStatus[id] === 'loaded')
    }

    function getInstancesBySha1(sha1: string): number[] {
        const ids: number[] = []
        const count = slotCount

        for (let i = 0; i < count; i++) {
            if (sha1s[i] === sha1 && !deletedMask[i]) {
                ids.push(instanceIds[i])
            }
        }
        return ids
    }

    function getInstancesByFileId(fileId: number): number[] {
        const ids: number[] = []
        const count = slotCount

        for (let i = 0; i < count; i++) {
            if (fileIds[i] === fileId && !deletedMask[i]) {
                ids.push(instanceIds[i])
            }
        }
        return ids
    }

    function getActivePropIds(): number[] {
        return Object.keys(fullColumnStatus)
            .map(Number)
            .filter(id => fullColumnStatus[id] === 'loaded' || fullColumnStatus[id] === 'loading')
    }

    async function updateFromLoadResult(result: LoadResult): Promise<void> {
        const tasks: Promise<void>[] = []
        
        // Collect all distinct property IDs targeted by this payload
        const targetPropIds = new Set<number>()
        result.instanceValues?.forEach(v => targetPropIds.add(v.propertyId))
        result.imageValues?.forEach(v => targetPropIds.add(v.propertyId))
        result.fileValues?.forEach(v => targetPropIds.add(v.propertyId))

        for (const propId of targetPropIds) {
            const status = fullColumnStatus[propId]

            // DISMISS IF NOT REQUESTED: Ignore updates if column is empty or uninitialized
            if (!status || status === 'empty') {
                continue
            }

            tasks.push((async () => {
                // WAY FOR LOAD TO END IF LOADING: Await the active flight promise before writing updates
                if (status === 'loading' && _fullColumnPromise[propId]) {
                    await _fullColumnPromise[propId]
                }

                // UPDATE WHEN LOADED
                const parseValue = (v: any) => typeof v === 'string' ? JSON.parse(v) : v

                // Process Instance Values
                if (result.instanceValues) {
                    const chunks = result.instanceValues.filter(v => v.propertyId === propId)
                    for (const chunk of chunks) {
                        const ids = (chunk as any).instanceIds || (chunk as any).ids || []
                        for (let i = 0; i < ids.length; i++) {
                            const slot = slotMap.get(Number(ids[i]))
                            if (slot !== undefined) writeSlot(propId, slot, parseValue(chunk.values[i]))
                        }
                    }
                }

                // Process Image SHA1 Values
                if (result.imageValues) {
                    const chunks = result.imageValues.filter(v => v.propertyId === propId)
                    for (const chunk of chunks) {
                        for (let i = 0; i < chunk.sha1s.length; i++) {
                            const matchingIds = getInstancesBySha1(chunk.sha1s[i])
                            const parsed = parseValue(chunk.values[i])
                            for (const id of matchingIds) {
                                const slot = slotMap.get(id)
                                if (slot !== undefined) writeSlot(propId, slot, parsed)
                            }
                        }
                    }
                }

                // Process File ID Values
                if (result.fileValues) {
                    const chunks = result.fileValues.filter(v => v.propertyId === propId)
                    for (const chunk of chunks) {
                        for (let i = 0; i < chunk.fileIds.length; i++) {
                            const matchingIds = getInstancesByFileId(chunk.fileIds[i])
                            const parsed = parseValue(chunk.values[i])
                            for (const id of matchingIds) {
                                const slot = slotMap.get(id)
                                if (slot !== undefined) writeSlot(propId, slot, parsed)
                            }
                        }
                    }
                }

                // Post-update structural cleanup for compression formats
                const col = columnData[propId]
                if (col?.kind === 'tag') {
                    col.csr = buildCSR(col.sparse, slotCount)
                }
            })())
        }

        await Promise.all(tasks)
    }

    function isSelected(slot: number): boolean { return selectionMask[slot] === 1 }

    function select(slots: number[]): void {
        for (const s of slots) selectionMask[s] = 1
        onSelectionChange.emit()
    }

    function deselect(slots: number[]): void {
        for (const s of slots) selectionMask[s] = 0
        onSelectionChange.emit()
    }

    function clearSelection(): void {
        selectionMask.fill(0)
        onSelectionChange.emit()
    }

    function clear() {
        slotMap.clear()
        slotCount = 0
        deletedMask = new Uint8Array(0)
        selectionMask = new Uint8Array(0)
        instanceIds = new Int32Array(0)
        sha1s = []
        fileIds = new Int32Array(0)

        _instanceIdPropId = null
        _sha1PropId = null
        _fileIdPropId = null
        for (const k of Object.keys(columnData)) delete columnData[Number(k)]
        for (const k of Object.keys(columnFetched)) delete columnFetched[Number(k)]
        for (const k of Object.keys(_propTypes)) delete _propTypes[Number(k)]
        for (const k of Object.keys(fullColumnStatus)) delete fullColumnStatus[Number(k)]
        for (const k of Object.keys(_fullColumnPromise)) delete _fullColumnPromise[Number(k)]
        for (const k of Object.keys(tagInverted)) delete tagInverted[Number(k)]
        for (const k of Object.keys(_tagInvertedPromise)) delete _tagInvertedPromise[Number(k)]
        instanceCount.value = 0
        isReady.value = false
    }

    return {
        isReady, instanceCount,
        slotMap,
        slotCount() { return slotCount },
        deletedMask() { return deletedMask },
        selectionMask() { return selectionMask },
        instanceIds() { return instanceIds },
        sha1s() { return sha1s },
        fileIds() { return fileIds },

        columnData, columnFetched, tagInverted,
        fullColumnStatus,
        onSelectionChange,
        systemProps,

        init, getRawBuffer, readSlot, writeSlot, isFetched, ensureColumn,
        addInstances, markSlotDeleted, registerProperty,
        requireFullColumn, requireTagInverted, getFullyLoadedPropIds,
        isSelected, select, deselect, clearSelection,
        getInstancesBySha1, getInstancesByFileId, updateFromLoadResult,
        clear,
    }
})