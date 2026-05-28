/**
 * ColumnStore — decoupled, non-reactive typed-array storage for 1M-scale datasets.
 *
 * Two-layer architecture:
 *   - This store: raw typed arrays, no Vue overhead, EventEmitter for changes.
 *   - fullColumnStatus: the only reactive object — observed by Vue for loading indicators.
 *
 * Property value columns are lazy. Slot map and metadata are built by init(), which
 * streams the same endpoint as dataStore independently so both can be initialised
 * in parallel from projectStore.
 *
 * See: panoptic_front/notes/new_data_store_design.md
 */

import { defineStore } from 'pinia'
import { markRaw, reactive } from 'vue'
import { PropertyType } from './models'
import { EventEmitter, isFinished } from '@/utils/utils'
import { apiStreamLoadState, projectApi } from './apiProjectRoutes'

// ─── Types ────────────────────────────────────────────────────────────────────

type TagSparse = (number[] | null)[]
type TagCSR    = { offsets: Int32Array; values: Int32Array }

export type ColumnData =
    | { kind: 'numeric'; data: Float64Array }
    | { kind: 'bool';    data: Uint8Array }      // 255 = unset/null
    | { kind: 'string';  data: (string | null)[] }
    | { kind: 'tag';     sparse: TagSparse; csr?: TagCSR }

export interface ChangePayload {
    propIds:     number[]
    instanceIds: number[]
}

interface PendingCall {
    resolve: () => void
    reject:  (err: unknown) => void
}

interface SlotInitData {
    id:       number
    sha1:     string
    folderId: number
    width:    number
    height:   number
}

// ─── Constants ────────────────────────────────────────────────────────────────

export const INSTANCE_VALUES_DEBOUNCE_MS  = 50
export const INCREMENTAL_UPDATE_THRESHOLD = 10_000

const DELETED_ID = -999999999

// Reserved negative property IDs for always-loaded metadata columns.
// These are passed to requireInstanceValues / readSlot exactly like property IDs —
// the store resolves them from the metadata arrays without a network fetch.
export const META = {
    WIDTH:     -1,
    HEIGHT:    -2,
    SHA1:      -3,
    FOLDER_ID: -4,
} as const

function isMetaId(id: number): boolean {
    return id === META.WIDTH || id === META.HEIGHT || id === META.SHA1 || id === META.FOLDER_ID
}

// ─── Pure helpers ─────────────────────────────────────────────────────────────

function propertyKind(type: PropertyType): ColumnData['kind'] {
    if (type === PropertyType.number || type === PropertyType.date || type === PropertyType.color) return 'numeric'
    if (type === PropertyType.checkbox) return 'bool'
    if (type === PropertyType.multi_tags || type === PropertyType.tag) return 'tag'
    return 'string'
}

function makeColumn(kind: ColumnData['kind'], size: number): ColumnData {
    switch (kind) {
        case 'numeric': {
            const data = new Float64Array(size)
            data.fill(NaN) // NaN = null value; 0 is a real value
            return { kind, data }
        }
        case 'bool':   return { kind, data: new Uint8Array(size).fill(255) }
        case 'string': return { kind, data: new Array(size).fill(null) }
        case 'tag':    return { kind, sparse: new Array(size).fill(null) }
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

function buildInvertedIndex(sparse: TagSparse, count: number): Record<number, number[]> {
    const tmp: Record<number, number[]> = {}
    for (let s = 0; s < count; s++) {
        const tags = sparse[s]
        if (!tags) continue
        for (const t of tags) {
            if (!tmp[t]) tmp[t] = []
            tmp[t].push(s)
        }
    }
    return tmp
}

// ─── Backend API stubs (subset endpoints to be implemented on backend) ────────

async function apiGetInstanceValues(
    ids:     number[],
    propIds: number[]
): Promise<Record<number, Record<number, any>>> {
    const { data } = await projectApi.get('/instances/values', {
        params: { ids: ids.join(','), prop_ids: propIds.join(',') }
    })
    return data
}

async function apiGetFullColumn(propId: number): Promise<{ ids: number[]; values: any[] }> {
    const { data } = await projectApi.get(`/instances/column/${propId}`)
    return data
}

// ─── Store ────────────────────────────────────────────────────────────────────

export const useColumnStore = defineStore('columnStore', () => {

    // ── Slot management ────────────────────────────────────────────────────
    const slotMap = markRaw(new Map<number, number>()) // instanceId → slot
    let slotToId    = new Int32Array(0)
    let slotCount   = 0
    let deletedMask = new Uint8Array(0)

    // ── Metadata columns (always built at init) ────────────────────────────
    const sha1Column: string[] = []
    let folderColumn = new Int32Array(0)
    let widthColumn  = new Int32Array(0)
    let heightColumn = new Int32Array(0)

    // ── Property columns ───────────────────────────────────────────────────
    const columnData:    Record<number, ColumnData> = markRaw({})
    const columnFetched: Record<number, Uint8Array> = markRaw({})
    const _propTypes:    Record<number, PropertyType> = {}

    // The only reactive state — observed by Vue for loading spinners.
    const fullColumnStatus = reactive<Record<number, 'empty' | 'loading' | 'loaded'>>({})
    const _fullColumnPromise: Record<number, Promise<void>> = {}

    // ── Tag inverted index ─────────────────────────────────────────────────
    const tagInverted:         Record<number, Int32Array> = markRaw({})
    const _tagInvertedPromise: Record<number, Promise<void>> = {}

    // ── Selection (non-reactive) ───────────────────────────────────────────
    let selectionMask = new Uint8Array(0)
    const onSelectionChange = new EventEmitter()

    // ── Change emitter ─────────────────────────────────────────────────────
    const onChange = new EventEmitter()

    // ── Reactive instance map — shared across all InstanceData registrations ──
    const instances = reactive<Record<number, { id: number, properties: Record<number, any> }>>({})
    const _registrations = new Map<string, { instanceIds: number[], propIds: number[] }>()

    // ── Batch fetch state ──────────────────────────────────────────────────
    let _batchTimer: ReturnType<typeof setTimeout> | null = null
    const _pendingIds   = new Set<number>()
    const _pendingProps = new Set<number>()
    const _pendingCalls: PendingCall[] = []

    // ─────────────────────────────────────────────────────────────────────────
    // Initialisation — self-contained, called from projectStore
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Streams instance metadata and property types independently from the backend.
     * Called from projectStore.init() in parallel with dataStore.init().
     * Property value columns remain empty (lazy) until required.
     */
    async function init() {
        const instanceBuffer: SlotInitData[] = []
        const propTypeBuffer: Record<number, PropertyType> = {}

        await apiStreamLoadState((result) => {
            if (result.chunk?.instances) {
                for (const inst of result.chunk.instances) {
                    if (inst.id === DELETED_ID) continue
                    instanceBuffer.push({
                        id:       inst.id,
                        sha1:     inst.sha1,
                        folderId: inst.folderId,
                        width:    inst.width,
                        height:   inst.height,
                    })
                }
            }
            if (result.chunk?.properties) {
                for (const prop of result.chunk.properties) {
                    if (prop.id !== DELETED_ID) propTypeBuffer[prop.id] = prop.type
                }
            }
            if (isFinished(result.state)) {
                _buildSlots(instanceBuffer, propTypeBuffer)
            }
        })
    }

    function _buildSlots(instances: SlotInitData[], propTypes: Record<number, PropertyType>) {
        const n = instances.length

        slotToId      = new Int32Array(n)
        deletedMask   = new Uint8Array(n)
        folderColumn  = new Int32Array(n)
        widthColumn   = new Int32Array(n)
        heightColumn  = new Int32Array(n)
        selectionMask = new Uint8Array(n)
        sha1Column.length = n

        slotMap.clear()

        for (let s = 0; s < n; s++) {
            const inst = instances[s]
            slotMap.set(inst.id, s)
            slotToId[s]     = inst.id
            sha1Column[s]   = inst.sha1
            folderColumn[s] = inst.folderId
            widthColumn[s]  = inst.width
            heightColumn[s] = inst.height
        }
        slotCount = n

        for (const [idStr, type] of Object.entries(propTypes)) {
            registerProperty(Number(idStr), type)
        }
    }

    function clear() {
        slotMap.clear()
        slotToId    = new Int32Array(0)
        slotCount   = 0
        deletedMask = new Uint8Array(0)

        sha1Column.length = 0
        folderColumn  = new Int32Array(0)
        widthColumn   = new Int32Array(0)
        heightColumn  = new Int32Array(0)

        for (const k of Object.keys(instances))     delete instances[Number(k)]
        _registrations.clear()

        for (const k of Object.keys(columnData))    delete columnData[Number(k)]
        for (const k of Object.keys(columnFetched)) delete columnFetched[Number(k)]
        for (const k of Object.keys(_propTypes))    delete _propTypes[Number(k)]
        for (const k of Object.keys(fullColumnStatus)) delete fullColumnStatus[Number(k)]
        for (const k of Object.keys(_fullColumnPromise)) delete _fullColumnPromise[Number(k)]
        for (const k of Object.keys(tagInverted))        delete tagInverted[Number(k)]
        for (const k of Object.keys(_tagInvertedPromise)) delete _tagInvertedPromise[Number(k)]

        selectionMask = new Uint8Array(0)
    }

    function registerProperty(propId: number, type: PropertyType) {
        _propTypes[propId] = type
        if (fullColumnStatus[propId] === undefined) {
            fullColumnStatus[propId] = 'empty'
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Synchronous reads
    // ─────────────────────────────────────────────────────────────────────────

    function readSlot(propId: number, slot: number): any {
        if (propId === META.WIDTH)     return widthColumn[slot]
        if (propId === META.HEIGHT)    return heightColumn[slot]
        if (propId === META.SHA1)      return sha1Column[slot]
        if (propId === META.FOLDER_ID) return folderColumn[slot]
        const col = columnData[propId]
        if (!col) return undefined
        switch (col.kind) {
            case 'numeric': return isNaN(col.data[slot]) ? null : col.data[slot]
            case 'bool':    return col.data[slot] === 255 ? null : col.data[slot] === 1
            case 'string':  return col.data[slot]
            case 'tag':     return col.sparse[slot]
        }
    }

    function isFetched(propId: number, slot: number): boolean {
        if (isMetaId(propId)) return slotCount > 0  // metadata is always available after init
        return columnFetched[propId]?.[slot] === 1
    }

    function isSelected(slot: number): boolean {
        return selectionMask[slot] === 1
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Cell writes
    // ─────────────────────────────────────────────────────────────────────────

    function _ensureColumn(propId: number): ColumnData {
        if (!columnData[propId]) {
            const kind = propertyKind(_propTypes[propId] ?? PropertyType.string)
            columnData[propId]    = makeColumn(kind, slotCount)
            columnFetched[propId] = new Uint8Array(slotCount)
        }
        return columnData[propId]
    }

    function _writeSlot(propId: number, slot: number, value: any) {
        const col = _ensureColumn(propId)
        switch (col.kind) {
            case 'numeric':
                col.data[slot] = value == null ? NaN : Number(value)
                break
            case 'bool':
                col.data[slot] = value == null ? 255 : (value ? 1 : 0)
                break
            case 'string':
                col.data[slot] = value ?? null
                break
            case 'tag':
                col.sparse[slot] = Array.isArray(value) ? value : null
                col.csr = undefined // invalidate — rebuilt by next requireFullColumn
                break
        }
        columnFetched[propId][slot] = 1
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Commit application
    // ─────────────────────────────────────────────────────────────────────────

    // ─────────────────────────────────────────────────────────────────────────
    // Instance registration — used by InstanceData components
    // ─────────────────────────────────────────────────────────────────────────

    function register(key: string, instanceIds: number[], propIds: number[]) {
        _registrations.set(key, { instanceIds: [...instanceIds], propIds: [...propIds] })

        // Synchronous pre-fill from typed-array cache
        for (const id of instanceIds) {
            if (!instances[id]) instances[id] = { id, properties: {} }
            const slot = slotMap.get(id)
            if (slot === undefined) continue
            for (const pid of propIds) {
                instances[id].properties[pid] = readSlot(pid, slot)
            }
        }

        // Async fetch for any missing cells — updates instances when done
        if (instanceIds.length && propIds.length) {
            requireInstanceValues(instanceIds, propIds).then(result => {
                for (const [id, values] of result) {
                    const inst = instances[id]
                    if (!inst) continue
                    for (const [pidStr, value] of Object.entries(values)) {
                        inst.properties[Number(pidStr)] = value
                    }
                }
            }).catch(() => {})
        }
    }

    function unregister(key: string) {
        _registrations.delete(key)
    }

    function getFullyLoadedPropIds(): number[] {
        return Object.keys(fullColumnStatus)
            .map(Number)
            .filter(id => fullColumnStatus[id] === 'loaded')
    }

    function getRegisteredPropIds(): number[] {
        const ids = new Set<number>()
        for (const { propIds } of _registrations.values()) {
            for (const id of propIds) {
                if (!isMetaId(id)) ids.add(id)
            }
        }
        return [...ids]
    }

    function getRegisteredInstanceIds(): number[] {
        const ids = new Set<number>()
        for (const { instanceIds } of _registrations.values()) {
            for (const id of instanceIds) ids.add(id)
        }
        return [...ids]
    }

    function applyCommit(updates: Array<{ instanceId: number; propertyId: number; value: any }>) {
        if (updates.length === 0) return

        const dirtyInstances: number[] = []
        const dirtyProps = new Set<number>()

        for (const { instanceId, propertyId, value } of updates) {
            const slot = slotMap.get(instanceId)
            if (slot === undefined) continue
            _writeSlot(propertyId, slot, value)
            dirtyInstances.push(instanceId)
            dirtyProps.add(propertyId)

            const inst = instances[instanceId]
            if (inst) inst.properties[propertyId] = value
        }

        if (dirtyInstances.length === 0) return
        onChange.emit({ propIds: [...dirtyProps], instanceIds: dirtyInstances } satisfies ChangePayload)
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Batch fetch — requireInstanceValues
    // ─────────────────────────────────────────────────────────────────────────

    async function requireInstanceValues(
        instanceIds: number[],
        propIds:     number[]
    ): Promise<Map<number, Record<number, any>>> {
        const needIds   = new Set<number>()
        const needProps = new Set<number>()

        for (const id of instanceIds) {
            const slot = slotMap.get(id)
            if (slot === undefined) continue
            for (const pid of propIds) {
                if (!isFetched(pid, slot)) {
                    needIds.add(id)
                    needProps.add(pid)
                }
            }
        }

        if (needIds.size > 0) {
            await new Promise<void>((resolve, reject) => {
                for (const id  of needIds)   _pendingIds.add(id)
                for (const pid of needProps) _pendingProps.add(pid)
                _pendingCalls.push({ resolve, reject })
                _scheduleBatch()
            })
        }

        const result = new Map<number, Record<number, any>>()
        for (const id of instanceIds) {
            const slot = slotMap.get(id)
            if (slot === undefined) continue
            const record: Record<number, any> = {}
            for (const pid of propIds) record[pid] = readSlot(pid, slot)
            result.set(id, record)
        }
        return result
    }

    function _scheduleBatch() {
        if (_batchTimer !== null) return
        _batchTimer = setTimeout(_flushBatch, 0)
    }

    async function _flushBatch() {
        _batchTimer = null

        const ids   = [..._pendingIds]
        const props = [..._pendingProps]
        const calls = [..._pendingCalls]

        _pendingIds.clear()
        _pendingProps.clear()
        _pendingCalls.length = 0

        if (ids.length === 0) {
            for (const c of calls) c.resolve()
            return
        }

        try {
            const raw = await apiGetInstanceValues(ids, props)

            for (const [idStr, values] of Object.entries(raw)) {
                const slot = slotMap.get(Number(idStr))
                if (slot === undefined) continue
                for (const [pidStr, value] of Object.entries(values)) {
                    _writeSlot(Number(pidStr), slot, value)
                }
            }

            // Mark all requested pairs fetched even if the API returned no value,
            // so we don't re-fetch null/absent values on every render.
            for (const id of ids) {
                const slot = slotMap.get(id)
                if (slot === undefined) continue
                for (const pid of props) {
                    _ensureColumn(pid)
                    columnFetched[pid][slot] = 1
                }
                // Sync into the reactive instances map if this id is registered
                const inst = instances[id]
                if (inst) {
                    for (const pid of props) {
                        inst.properties[pid] = readSlot(pid, slot)
                    }
                }
            }

            for (const c of calls) c.resolve()
        } catch (e) {
            for (const c of calls) c.reject(e)
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Full column fetch — for CollectionManager
    // ─────────────────────────────────────────────────────────────────────────

    async function requireFullColumn(propId: number): Promise<void> {
        if (fullColumnStatus[propId] === 'loaded') return
        if (_fullColumnPromise[propId]) return _fullColumnPromise[propId]

        fullColumnStatus[propId] = 'loading'

        _fullColumnPromise[propId] = (async () => {
            try {
                const { ids, values } = await apiGetFullColumn(propId)

                for (let i = 0; i < ids.length; i++) {
                    const slot = slotMap.get(ids[i])
                    if (slot === undefined) continue
                    _writeSlot(propId, slot, values[i])
                }

                const col = columnData[propId]
                if (col?.kind === 'tag') {
                    col.csr = buildCSR(col.sparse, slotCount)
                }

                fullColumnStatus[propId] = 'loaded'
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
            const tmp = buildInvertedIndex(col.sparse, slotCount)
            for (const [tagIdStr, slots] of Object.entries(tmp)) {
                tagInverted[Number(tagIdStr)] = new Int32Array(slots).sort()
            }
        })()

        return _tagInvertedPromise[propId]
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Selection
    // ─────────────────────────────────────────────────────────────────────────

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

    // ─────────────────────────────────────────────────────────────────────────

    return {
        // Slot management (non-reactive — read typed arrays directly)
        slotMap,
        get slotToId()    { return slotToId },
        get slotCount()   { return slotCount },
        get deletedMask() { return deletedMask },

        // Metadata columns
        sha1Column,
        get folderColumn()  { return folderColumn },
        get widthColumn()   { return widthColumn },
        get heightColumn()  { return heightColumn },

        // Property columns (non-reactive — subscribe to onChange for updates)
        columnData,
        columnFetched,
        tagInverted,

        // Reactive status — the only Vue-observable state in this store
        fullColumnStatus,

        // EventEmitters
        onChange,
        onSelectionChange,

        // Selection (non-reactive)
        get selectionMask() { return selectionMask },

        // Reactive instance map (shared across InstanceData registrations)
        instances,

        // Store API
        init,
        clear,
        register,
        unregister,
        getFullyLoadedPropIds,
        getRegisteredPropIds,
        getRegisteredInstanceIds,
        registerProperty,
        applyCommit,
        requireInstanceValues,
        requireFullColumn,
        requireTagInverted,
        readSlot,
        isFetched,
        isSelected,
        select,
        deselect,
        clearSelection,
    }
})
