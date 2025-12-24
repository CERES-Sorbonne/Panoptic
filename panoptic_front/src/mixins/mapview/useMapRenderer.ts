import { onMounted, onUnmounted, type Ref } from 'vue'
import { MapRenderer } from './MapRenderer'
import { ImageAtlas } from '@/data/models'
import { apiGetAtlas } from '@/data/apiProjectRoutes'
import { PointData } from './useMapLogic'

export function useMapRenderer(containerRef: Ref<HTMLElement | null>, points: PointData[]) {
    let renderer: MapRenderer | null = null
    let atlas: ImageAtlas | null = null
    console.log('lalalalaall')

    onMounted(async () => {
        console.log('mounted')
        if (containerRef.value) {
            console.log('init useMapRednerer    ')
            // Initialize the engine with the DOM element
            renderer = new MapRenderer(containerRef.value)

            atlas = await apiGetAtlas(0)
            renderer.createMap(atlas, points)

            // Start the loop
            renderer.animate()
        }
    })

    onUnmounted(() => {
        if (renderer) {
            renderer.dispose()
            renderer = null
        }
    })

    return {
        renderer
    }
}