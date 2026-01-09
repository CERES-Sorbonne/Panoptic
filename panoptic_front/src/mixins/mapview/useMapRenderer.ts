import { onMounted, onUnmounted, shallowRef, type Ref } from 'vue'
import { MapRenderer } from './MapRenderer'
import { ImageAtlas, PointData } from '@/data/models'
import { apiGetAtlas } from '@/data/apiProjectRoutes'
import { useDataStore } from '@/data/dataStore'

export function useMapRenderer(containerRef: Ref<HTMLElement | null>, points: PointData[]) {
    let map = shallowRef<MapRenderer>()
    let atlas: ImageAtlas | null = null

    onMounted(async () => {
        if (containerRef.value) {
            console.log('init useMapRednerer    ')
            // Initialize the engine with the DOM element
            map.value = new MapRenderer(containerRef.value, useDataStore().baseImgUrl)

            atlas = await apiGetAtlas(0)
            map.value.createMap(atlas, points)

            // Start the loop
            map.value.animate()
        }
    })

    onUnmounted(() => {
        if (map.value) {
            map.value.dispose()
            map.value = null
        }
    })

    return {
        map
    }
}