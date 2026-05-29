import { defineStore } from 'pinia'
import { computed, ref, shallowRef, triggerRef } from 'vue'
import { ImageAtlas, MapIndex, PointMap, VectorStats, VectorType } from './models'
import {
    apiDeleteMap, apiDeleteVectorType, apiGetAtlas, apiGetMap,
    apiGetVectorStats, apiGetVectorTypes, apiListMaps,
} from './apiProjectRoutes'

export const useMediaStore = defineStore('mediaStore', () => {

    const vectorTypes = ref<VectorType[]>([])
    const vectorStats = ref<VectorStats>({ count: {}, sha1Count: 0 })
    const maps        = shallowRef<MapIndex>({})
    const atlas       = ref<ImageAtlas>()

    const hasMaps  = computed(() => Object.values(maps.value).length > 0)
    const hasAtlas = computed(() => atlas.value?.id !== undefined)

    function importVectorTypes(types: VectorType[]) {
        vectorTypes.value = types
    }

    async function loadAtlas() {
        atlas.value = await apiGetAtlas(0)
    }

    async function updateVectorTypes() {
        vectorTypes.value = await apiGetVectorTypes()
    }

    async function deleteVectorType(id: number) {
        await apiDeleteVectorType(id)
        await updateVectorTypes()
    }

    async function updateVectorStats() {
        vectorStats.value = await apiGetVectorStats()
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
        maps.value        = {}
        atlas.value       = undefined
    }

    return {
        // State
        vectorTypes, vectorStats, maps, atlas,
        // Computed
        hasMaps, hasAtlas,
        // Actions
        init, clear,
        importVectorTypes, loadAtlas,
        updateVectorTypes, deleteVectorType, updateVectorStats,
        loadMaps, loadMapData, deleteMap,
    }
})
