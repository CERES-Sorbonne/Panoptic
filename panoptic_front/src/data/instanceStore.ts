import { defineStore } from 'pinia'
import { markRaw, reactive, ref } from 'vue'
import { deletedID, ImageValuesArray, InstanceValuesArray, FileValuesArray, LoadResult } from './models'
import { projectApi } from './apiProjectRoutes'
import { SERVER_PREFIX } from './apiPanopticRoutes'
import { useColumnStore } from './columnStore'
import { usePanopticStore } from './panopticStore'
import { useDataStore } from './dataStore' // <-- Imported to access property definitions

export interface InstanceEntry {
    id: number
    sha1: string
    imageUrl: string
    properties: Record<number, any>
    selected: boolean

    width?: number
    height?: number
    [systemKey: string]: any // <-- Index signature to allow dynamic direct keys safely
}

type Registration = { instanceIds: number[]; propIds: number[] }

export const useInstanceStore = defineStore('instanceStore', () => {
    const columnStore = useColumnStore()
    const dataStore = useDataStore() // <-- Initialized dataStore

    const instanceData = reactive<Record<number, InstanceEntry>>({})
    const registrations = markRaw(new Map<string, Registration>())
    const registeredInstanceCount = ref(0)

    // Per-pair load tracking. A (instanceId, propId) pair is "available" when it is
    // already loaded (fetched) or currently being requested (inFlight) — in both cases
    // fetchAll skips it. fetched also fixes the null-value gap: a pair the server
    // returns no value for is still marked fetched, so we don't re-request it forever.
    const fetched  = markRaw(new Map<number, Set<number>>())
    const inFlight  = markRaw(new Map<number, Set<number>>())
    // The dataStore.lastSequence value the `fetched` cache is consistent with. When the
    // global sequence advances past this, cached values may be stale (deltas only ship
    // active props), so we drop the whole fetched set and re-request for safety.
    let cachedSequence = 0

    let batchTimer: ReturnType<typeof setTimeout> | null = null

    // --- load-state helpers ---

    function isAvailable(id: number, pid: number): boolean {
        return !!fetched.get(id)?.has(pid) || !!inFlight.get(id)?.has(pid)
    }

    function addPair(map: Map<number, Set<number>>, id: number, pid: number) {
        let set = map.get(id)
        if (!set) { set = new Set<number>(); map.set(id, set) }
        set.add(pid)
    }

    function delPair(map: Map<number, Set<number>>, id: number, pid: number) {
        const set = map.get(id)
        if (!set) return
        set.delete(pid)
        if (set.size === 0) map.delete(id)
    }

    // --- registration ---

    function register(key: string, instanceIds: number[], propIds: number[], projectId: string) {
        registrations.set(key, { instanceIds: [...instanceIds], propIds: [...propIds] })
        updateRegisteredCount()

        // Gather all property definitions to find system properties
        const propertiesList = dataStore?.properties 
            ? Object.values(dataStore.properties) 
            : []

        for (const id of instanceIds) {
            if (instanceData[id]) continue
            const slot = columnStore.slotMap.get(id)
            const sha1 = slot !== undefined ? (columnStore.sha1s()[slot] ?? '') : ''
            // 1. Create the base entry object
            const entry: InstanceEntry = {
                id,
                sha1,
                imageUrl: `${SERVER_PREFIX}/projects/${projectId}/image/by_size/${sha1}`,
                properties: {},
                selected: slot !== undefined ? columnStore.isSelected(slot) : false,
            }

            // 2. Direct root key value assignment
            for (const prop of propertiesList) {
                if (prop && prop.systemKey) {
                    entry[prop.systemKey] = dataStore.getSysField(id, prop.systemKey)
                }
            }
            instanceData[id] = entry
        }

        
        if (instanceIds.length && propIds.length) scheduleFetch()
    }

    function unregister(key: string) {
        registrations.delete(key)
        updateRegisteredCount()
    }

    function updateRegisteredCount() {
        const unique = new Set<number>()
        for (const { instanceIds } of registrations.values())
            for (const id of instanceIds) unique.add(id)
        registeredInstanceCount.value = unique.size
    }

    // --- fetch ---

    function scheduleFetch() {
        if (batchTimer !== null) return
        batchTimer = setTimeout(fetchAll, 0)
    }

    async function fetchAll() {
        batchTimer = null

        // Sequence-based invalidation: if the global watermark advanced past the one our
        // cache is valid for, cached pairs may be stale (deltas only ship active props),
        // so drop the whole fetched set and re-request. instanceData is kept to avoid
        // flicker — values get overwritten when the re-fetch lands.
        const reqSeq = (dataStore.lastSequence as unknown as number) ?? 0
        if (reqSeq > cachedSequence) fetched.clear()

        // Group registrations by their prop-set signature so registrations needing the
        // same props collapse into a single rectangular request, while distinct prop sets
        // stay separate (no Cartesian overfetch across components).
        const groups = new Map<string, { propIds: number[]; ids: Set<number> }>()
        for (const reg of registrations.values()) {
            if (reg.instanceIds.length === 0 || reg.propIds.length === 0) continue
            const propIds = [...new Set(reg.propIds)].sort((a, b) => a - b)
            const sig = propIds.join(',')
            let group = groups.get(sig)
            if (!group) { group = { propIds, ids: new Set<number>() }; groups.set(sig, group) }
            for (const id of reg.instanceIds) group.ids.add(id)
        }

        const tasks: Promise<void>[] = []
        for (const group of groups.values()) {
            // Keep only instances still missing at least one prop in this set.
            const requestIds = [...group.ids].filter(id =>
                group.propIds.some(pid => !isAvailable(id, pid)))
            if (requestIds.length === 0) continue

            // Mark in-flight before awaiting so concurrent fetchAll calls skip these pairs.
            for (const id of requestIds)
                for (const pid of group.propIds) addPair(inFlight, id, pid)

            tasks.push((async () => {
                try {
                    const { data } = await projectApi.post('/instances/values', {
                        ids: requestIds,
                        prop_ids: group.propIds,
                    })
                    applyFetchedValues(data)
                    // Mark every requested pair fetched — including ones absent from the
                    // response (= confirmed empty), so we never re-request them on a whim.
                    for (const id of requestIds)
                        for (const pid of group.propIds) addPair(fetched, id, pid)
                } catch (e) {
                    console.error('fetchAll group failed', e)
                } finally {
                    for (const id of requestIds)
                        for (const pid of group.propIds) delPair(inFlight, id, pid)
                }
            })())
        }

        if (tasks.length === 0) return
        await Promise.all(tasks)
        // Advance the watermark only after a successful pass over all groups.
        if (reqSeq > cachedSequence) cachedSequence = reqSeq
    }

    function applyFetchedValues(raw: Record<number, Record<number, any>>) {
        for (const [idStr, values] of Object.entries(raw)) {
            const id = Number(idStr)
            const slot = columnStore.slotMap.get(id)
            if (slot === undefined) continue

            const entry = instanceData[id]
            if (entry) {
                for (const [pidStr, value] of Object.entries(values)) {
                    const pid = Number(pidStr)
                    entry.properties[pid] = value
                    
                    // Directly update root value if it's a system property
                    const prop = dataStore.properties?.[pid]
                    if (prop?.systemKey) {
                        entry[prop.systemKey] = value
                    }
                }
            }
        }
    }

    // --- mutations ---

    function markDeleted(id: number) {
        if (instanceData[id]) instanceData[id].id = deletedID
    }

    function importInstanceValuesArray(arrays: InstanceValuesArray[]) {
        for (const arr of arrays) {
            const prop = dataStore.properties?.[arr.propertyId]
            for (let i = 0; i < arr.ids.length; i++) {
                const value = JSON.parse(arr.values[i])
                if (value === undefined) continue
                const id = Number(arr.ids[i])
                if (instanceData[id]) {
                    instanceData[id].properties[arr.propertyId] = value
                    if (prop?.systemKey) {
                        instanceData[id][prop.systemKey] = value
                    }
                }
            }
        }
    }

    function importImageValuesArray(arrays: ImageValuesArray[]) {
        for (const arr of arrays) {
            const prop = dataStore.properties?.[arr.propertyId]
            for (let i = 0; i < arr.sha1s.length; i++) {
                const value = JSON.parse(arr.values[i])
                if (value === undefined) continue
                for (const id of columnStore.getInstancesBySha1(arr.sha1s[i])) {
                    if (instanceData[id]) {
                        instanceData[id].properties[arr.propertyId] = value
                        if (prop?.systemKey) {
                            instanceData[id][prop.systemKey] = value
                        }
                    }
                }
            }
        }
    }

    function importFileValuesArray(arrays: FileValuesArray[]) {
        for (const arr of arrays) {
            const prop = dataStore.properties?.[arr.propertyId]
            for (let i = 0; i < arr.fileIds.length; i++) {
                const value = JSON.parse(arr.values[i])
                if (value === undefined) continue
                for (const id of columnStore.getInstancesByFileId(arr.fileIds[i])) {
                    if (instanceData[id]) {
                        instanceData[id].properties[arr.propertyId] = value
                        if (prop?.systemKey) {
                            instanceData[id][prop.systemKey] = value
                        }
                    }
                }
            }
        }
    }

    function updateFromLoadResult(result: LoadResult) {
        const activeProps = new Set<number>()
        for (const reg of registrations.values())
            for (const pid of reg.propIds) activeProps.add(pid)

        if (activeProps.size === 0) return

        const active = (arr: { propertyId: number }[]) => arr.filter(v => activeProps.has(v.propertyId))

        if (result.instanceValues?.length) importInstanceValuesArray(active(result.instanceValues) as InstanceValuesArray[])
        if (result.imageValues?.length) importImageValuesArray(active(result.imageValues) as ImageValuesArray[])
        if (result.fileValues?.length) importFileValuesArray(active(result.fileValues) as FileValuesArray[])
    }

    function clear() {
        for (const k of Object.keys(instanceData)) delete instanceData[Number(k)]
        registrations.clear()
        fetched.clear()
        inFlight.clear()
        cachedSequence = 0
        if (batchTimer !== null) { clearTimeout(batchTimer); batchTimer = null }
        registeredInstanceCount.value = 0
    }

    return {
        instanceData,
        registeredInstanceCount,
        markDeleted,
        register,
        unregister,
        updateFromLoadResult,
        clear,
    }
})