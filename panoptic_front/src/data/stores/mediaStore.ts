import { defineStore } from 'pinia'
import { computed, ref, shallowRef, triggerRef, watch } from 'vue'
import { useProjectStore } from './projectStore'
import { useColumnStore } from './columnStore'
import { ImageAtlas, MapIndex, PointMap, TaskState, VectorStats, VectorType } from '../models'
import {
    apiDeleteMap, apiDeleteVectorType, apiGenerateAtlas, apiGetAtlas, apiGetMap,
    apiGetVectorStats, apiGetVectorTypes, apiListMaps,
} from '../api/projectApi'

export const useMediaStore = defineStore('mediaStore', () => {

    const vectorTypes = ref<VectorType[]>([])
    const vectorStats = ref<VectorStats>({ count: {}, sha1Count: 0 })
    const maps        = shallowRef<MapIndex>({})
    const atlas       = ref<ImageAtlas>()
    // Whether the atlas has been fetched at least once — `atlas` stays undefined both before
    // that and when the project has none, and only the latter means "no atlas".
    const atlasFetched = ref(false)

    const hasMaps  = computed(() => Object.values(maps.value).length > 0)
    const hasAtlas = computed(() => atlas.value?.id !== undefined)

    // The atlas build task, while one is queued or running (the task list keeps finished ones
    // until dismissed). The `atlas` socket event reloads the atlas when it completes.
    const atlasTask = computed(() => useProjectStore().state?.tasks?.find(t =>
        t.key === 'GenerateAtlasTask' && !t.finished) ?? null)
    const atlasTaskPercent = computed(() => {
        const t = atlasTask.value
        return t && t.total > 0 ? Math.round(100 * t.done / t.total) : 0
    })

    // Unfinished compute task of each vector type, by vector type id. Comes from the task
    // list, so it survives page reloads and includes tasks the plugin queued by itself.
    const vectorTasks = computed(() => {
        const res: Record<number, TaskState> = {}
        for (const t of useProjectStore().state?.tasks ?? []) {
            if (t.vectorTypeId != null && !t.finished) res[t.vectorTypeId] = t
        }
        return res
    })

    function vectorTask(typeId: number): TaskState | null {
        return vectorTasks.value[typeId] ?? null
    }

    // For each vector task, by task id: the part of its `done` that `vectorStats` already
    // counts. Set to the task's `done` at each stats reload. A task without an entry is
    // counted in full if it is finished, and not at all if it is still running.
    let statsCountedDone: Record<string, number> = {}

    // Vectors stored for a vector type: the loaded stats plus what its tasks wrote since.
    // Compute tasks only count vectors once they are written, so this matches the database.
    function vectorCount(typeId: number): number {
        let count = vectorStats.value.count[typeId] ?? 0
        for (const t of useProjectStore().state?.tasks ?? []) {
            if (t.vectorTypeId !== typeId) continue
            const counted = statsCountedDone[t.id]
            if (counted !== undefined) count += t.done - counted
            else if (!t.finished) count += t.done
        }
        return Math.min(count, vectorStats.value.sha1Count)
    }

    // Reload the vector counts when a compute task finishes (or is dismissed). Until the
    // reload returns, the finished task still adds its vectors to the old counts.
    watch(() => Object.values(vectorTasks.value).map(t => t.id), (ids, oldIds) => {
        const gone = oldIds?.filter(id => !ids.includes(id)) ?? []
        if (!gone.length) return
        gone.forEach(id => statsCountedDone[id] ??= 0)
        updateVectorStats()
    })

    // How many of the project's distinct images the atlas holds. Walks every slot, so it only
    // recounts when the atlas reloads or the instance count changes (imports), not on tree ticks.
    const atlasCoverage = computed(() => {
        const columnStore = useColumnStore()
        void columnStore.instanceCount
        const mapping = atlas.value?.sha1Mapping
        const allSha1s = columnStore.sha1s()
        const deleted = columnStore.deletedMask()
        const seen = new Set<string>()
        let inAtlas = 0
        for (let s = 0; s < columnStore.slotCount(); s++) {
            const sha1 = allSha1s[s]
            if (!sha1 || deleted[s] || seen.has(sha1)) continue
            seen.add(sha1)
            if (mapping?.[sha1]) inAtlas++
        }
        return { inAtlas, total: seen.size, missing: seen.size - inAtlas }
    })

    // Set while the generate request is in flight, before the task shows up in the task list,
    // so a double click can't queue two builds.
    const atlasRequested = ref(false)
    async function generateAtlas() {
        if (atlasTask.value || atlasRequested.value) return
        atlasRequested.value = true
        try {
            await apiGenerateAtlas()
        } finally {
            atlasRequested.value = false
        }
    }

    function importVectorTypes(types: VectorType[]) {
        vectorTypes.value = types
    }

    async function loadAtlas() {
        const loaded = await apiGetAtlas(0)
        // GenerateAtlasTask always rewrites atlas id 0 in place, so nothing in the payload
        // distinguishes a rebuilt atlas from the previous one. Stamp a version so the
        // renderer can drop its cached sheet textures instead of reusing stale images.
        if (loaded) loaded.version = Date.now()
        atlas.value = loaded
        atlasFetched.value = true
    }

    async function updateVectorTypes() {
        vectorTypes.value = await apiGetVectorTypes()
    }

    async function deleteVectorType(id: number) {
        await apiDeleteVectorType(id)
        await updateVectorTypes()
    }

    async function updateVectorStats() {
        const stats = await apiGetVectorStats()
        const counted: Record<string, number> = {}
        for (const t of useProjectStore().state?.tasks ?? []) {
            if (t.vectorTypeId != null) counted[t.id] = t.done
        }
        statsCountedDone = counted
        vectorStats.value = stats
    }

    async function loadMaps(mapList?: PointMap[]) {
        let idx = { ...maps.value }
        if (!mapList) {
            mapList = await apiListMaps()
            idx = {}
        }
        if (!mapList) return
        for (const m of mapList) {
            if (!idx[m.id]) idx[m.id] = m
        }
        maps.value = idx
    }

    async function loadMapData(mapId: number) {
        const map = await apiGetMap(mapId)
        maps.value[map.id] = map
        triggerRef(maps)
    }

    async function deleteMap(mapId: number) {
        await apiDeleteMap(mapId)
        await loadMaps()
    }

    async function init() {
        const [vecTypes] = await Promise.all([apiGetVectorTypes(), loadAtlas()])
        importVectorTypes(vecTypes)
    }

    function clear() {
        vectorTypes.value = []
        vectorStats.value = { count: {}, sha1Count: 0 }
        statsCountedDone = {}
        maps.value        = {}
        atlas.value       = undefined
        atlasFetched.value = false
    }

    return {
        // State
        vectorTypes, vectorStats, vectorTasks, maps, atlas, atlasFetched,
        // Computed
        hasMaps, hasAtlas, atlasTask, atlasTaskPercent, atlasCoverage, atlasRequested,
        // Actions
        init, clear, vectorTask, vectorCount,
        importVectorTypes, loadAtlas, generateAtlas,
        updateVectorTypes, deleteVectorType, updateVectorStats,
        loadMaps, loadMapData, deleteMap,
    }
})
