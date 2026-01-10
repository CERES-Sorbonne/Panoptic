<script setup lang="ts">
import { apiGetAtlas } from '@/data/apiProjectRoutes';
import { ImageAtlas, PointData } from '@/data/models';
import { useTabStore } from '@/data/tabStore';
import { useMapRenderer } from '@/mixins/mapview/useMapRenderer';
import { onMounted, ref, watch } from 'vue';

const tabs = useTabStore()

const groupManager = tabs.getMainTab().collection.groupManager

const props = defineProps<{
    points: PointData[]
    mouseMode: string
}>()

const emits = defineEmits(['selection'])

const canvasContainer = ref<HTMLElement>(null)

const renderer = useMapRenderer(canvasContainer, props.points)

watch(renderer.map, () => renderer.map.value.onPointSelection = (points) => emits('selection', points))

watch(() => props.mouseMode, () => {
    if (renderer.map) {
        renderer.map.value.setMouseMode(props.mouseMode)
    }
})

watch(groupManager.selectedImages, () => {
    console.log('change tints')
    renderer.map.value.updateTints()
})

defineExpose({
    updateTints: () => renderer.map.value.updateTints(),
    updateBorder: () => renderer.map.value.updateBorder(),
    getMap: () => renderer.map.value
})

</script>

<template>
    <div class="point-cloud-wrapper">
        <div ref="canvasContainer" class="canvas-container"></div>
    </div>
</template>

<style scoped>
.point-cloud-wrapper {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background-color: white;
}

.canvas-container {
    width: 100%;
    height: 100%;
}
</style>