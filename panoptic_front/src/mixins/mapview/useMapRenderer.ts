import { onMounted, onUnmounted, type Ref } from 'vue'
import { MapRenderer } from './MapRenderer'
import { ImageAtlas } from '@/data/models'
import { apiGetAtlas } from '@/data/apiProjectRoutes'

export function useMapRenderer(containerRef: Ref<HTMLElement | null>) {
    let renderer: MapRenderer | null = null
    let atlas: ImageAtlas | null = null

    onMounted(async () => {
        if (containerRef.value) {
            // Initialize the engine with the DOM element
            renderer = new MapRenderer(containerRef.value)

            atlas = await apiGetAtlas(0)
            renderer.createMap(atlas)

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