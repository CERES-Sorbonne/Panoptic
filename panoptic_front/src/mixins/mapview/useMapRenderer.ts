import { onMounted, onUnmounted, shallowRef, type Ref, watch } from 'vue'
import { MapRenderer } from './MapRenderer'
import { useDataStore } from '@/data/dataStore'

/**
 * Controller Composable for the MapRenderer.
 * * @param containerRef - The HTML element reference where the canvas will be mounted.
 * @returns { map } - The reactive reference to the MapRenderer instance.
 */
export function useMapRenderer(containerRef: Ref<HTMLElement | null>) {
    const map = shallowRef<MapRenderer | null>(null)
    const store = useDataStore()

    onMounted(() => {
        if (!containerRef.value) {
            console.error("MapRenderer: Container ref is null on mount.")
            return
        }

        console.log('Initializing MapRenderer...')
        // Initialize the engine with the DOM element
        map.value = new MapRenderer(containerRef.value, store.baseImgUrl)
        
        // Start the animation loop
        map.value.animate()
    })

    onUnmounted(() => {
        if (map.value) {
            console.log('Disposing MapRenderer...')
            map.value.dispose()
            map.value = null
        }
    })

    return {
        map
    }
}