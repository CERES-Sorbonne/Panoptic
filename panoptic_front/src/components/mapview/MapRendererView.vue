<script setup lang="ts">
import { apiGetAtlas } from '@/data/apiProjectRoutes';
import { ImageAtlas } from '@/data/models';
import { PointData } from '@/mixins/mapview/useMapLogic';
import { useMapRenderer } from '@/mixins/mapview/useMapRenderer';
import { onMounted, ref } from 'vue';


const props = defineProps<{
    points: PointData[]
}>()

const canvasContainer = ref<HTMLElement>(null)

useMapRenderer(canvasContainer, props.points).renderer

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