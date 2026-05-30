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

    let batchTimer: ReturnType<typeof setTimeout> | null = null

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

        const ids = new Set<number>()
        const propIds = new Set<number>()
        for (const reg of registrations.values()) {
            for (const id of reg.instanceIds) ids.add(id)
            for (const pid of reg.propIds) propIds.add(pid)
        }

        if (ids.size === 0 || propIds.size === 0) return

        try {
            const { data } = await projectApi.get('/instances/values', {
                params: { ids: [...ids].join(','), prop_ids: [...propIds].join(',') },
            })
            applyFetchedValues(data)
        } catch (e) {
            console.error('fetchAll failed', e)
        }
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
                if (value == undefined) continue
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
                if (value == undefined) continue
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
                if (value == undefined) continue
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