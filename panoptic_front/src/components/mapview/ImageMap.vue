<template>
    <div class="point-cloud-wrapper">
        <div ref="canvasContainer" class="canvas-container"></div>

        <div v-if="isLoading" class="loading-overlay">
            Processing points...
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
// Assume useDataStore is available and correctly imported
import { useDataStore } from '@/data/dataStore'
import { BoundingBox, PointData, useMapLogic } from '@/mixins/mapview/useMapLogic'
import { MapGroup } from '@/data/models'

const data = useDataStore()

// ----------------------------------------------------------------------
// PROPS / TYPES
// ----------------------------------------------------------------------

export interface Props {
    points: PointData[]
    pointSize?: number
    backgroundColor?: number | string
    showImages: boolean
    showPoints: boolean
    showBoxes: boolean
    baseImageSize: number
    maxImageSize: number
    minImageSize: number,
    groups: MapGroup[],
    selectedGroups: { [groupId: number]: boolean }
    selectedPoints: {[sha1: string]: boolean}
}

const props = withDefaults(defineProps<Props>(), {
    points: () => [],
    pointSize: 0.10,
    backgroundColor: 0x1a1a1a,
    baseImageSize: 5,
    maxImageSize: 200,
    minImageSize: 20,
})

// ----------------------------------------------------------------------
// STATE (UI / DOM Only)
// ----------------------------------------------------------------------

const canvasContainer = ref<HTMLDivElement | null>(null)
const isLoading = ref(false)

// ----------------------------------------------------------------------
// LOGIC HOOK (External)
// ----------------------------------------------------------------------

const {
    init,
    cleanup,
    processPoints,
    updateShowImages,
    updateShowPoints,
    updateView,
    renderBoundingBoxesInstanced,
    updateShowBoxes,
    // ASSUME the composable now exposes a function to toggle label visibility
    updateShowLabels
} = useMapLogic({
    dataStore: data,
    isLoadingRef: isLoading,
    props: props
})

// ----------------------------------------------------------------------
// LIFECYCLE
// ----------------------------------------------------------------------

onMounted(() => {
    if (canvasContainer.value) {
        init(canvasContainer.value)
        processPoints(props.points) // Initial load
    }
})

onUnmounted(() => {
    cleanup()
})

// ----------------------------------------------------------------------
// WATCHERS
// ----------------------------------------------------------------------

watch(() => props.points, (newPoints) => {
    processPoints(newPoints)
})

watch(() => props.backgroundColor, (newColor) => {
    // The THREE.js logic now handles the color update internally
    // This requires exposing a function from the composable, or passing the prop directly.
    // For simplicity, we'll let the composable manage its own color update via props access.
})

watch(() => props.showImages, (active) => {
    updateShowImages(active)
    updateView()
})

watch(() => props.showPoints, (active) => {
    updateShowPoints(active)
    updateView()
})

watch(() => [props.baseImageSize, props.maxImageSize, props.minImageSize], () => {
    // Changing the image size parameters requires re-evaluating visible images
    updateView()
    // The logic to rebuild images should be handled inside usePointCloudViz on prop change
})

watch(() => props.groups, () => {
    renderBoundingBoxesInstanced()
    // processPoints(props.points)
})

watch(() => props.showBoxes, (active) => {
    // 1. Re-render the boxes (if needed, which renderBoundingBoxesInstanced likely does)
    renderBoundingBoxesInstanced();

    // 2. Toggle the visibility of the HTML/CSS labels
    updateShowLabels(active); // NEW WATCHER CALL

    updateView()
})

watch(() => props.groups, () => renderBoundingBoxesInstanced())

// ----------------------------------------------------------------------
// EXPORTS
// ----------------------------------------------------------------------

defineExpose({
    render: () => {
        processPoints(props.points)
    },
    updatePoints: () => {
        processPoints(props.points)
    },
    updateShowBoxes

})
</script>

<style scoped>
.point-cloud-wrapper {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background-color: #1a1a1a;
}

.canvas-container {
    width: 100%;
    height: 100%;
}

.loading-overlay {
    position: absolute;
    bottom: 20px;
    right: 20px;
    padding: 8px 16px;
    background: rgba(0, 0, 0, 0.7);
    color: white;
    border-radius: 4px;
    font-family: sans-serif;
    font-size: 12px;
    pointer-events: none;
}
</style>