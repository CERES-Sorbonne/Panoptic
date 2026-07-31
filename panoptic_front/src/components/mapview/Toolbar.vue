<script setup lang="ts">
import { Instance } from '@/data/models'
import PointMapSelection from './PointMapSelection.vue'
import ActionButton2 from '../actions/ActionButton2.vue'
import RangeInput from '../inputs/RangeInput.vue'
import WithToolTip from '../tooltips/withToolTip.vue'
import { useMediaStore } from '@/data/mediaStore'

const media = useMediaStore()

const props = defineProps<{
    selectedMap: number | null
    hasMaps: boolean
    // Images the 'map' action runs on (the collection's current content). A getter, so the
    // list is materialised on click instead of on every tree tick.
    images: () => Instance[]
    // Border width of the rendered images, controlled by the header-bar slider.
    borderWidth: number
    // How much the HD preview grows over the hovered image, same slider treatment.
    hoverScale: number
}>()

const emits = defineEmits([
    'update:selectedMap',
    'update:borderWidth',
    'update:hoverScale',
    'delete:map'
])

function deleteMap() {
    if (props.selectedMap == null) return
    media.deleteMap(props.selectedMap)
}

async function updateMap(event) {
    await media.loadMaps()
    emits('update:selectedMap', event.value.id)
}

</script>

<template>
    <div class="map-header-bar">
        <ActionButton2 action="map" class="bb ps-1 pe-1" style="font-size: 14px;" :no-border="true" @call="updateMap" :images="props.images">
            <i class="bi bi-boxes me-1" /> {{ $t('map.create') }}
        </ActionButton2>

        <div v-if="props.hasMaps" style="min-width: 150px;" class="map-select">
            <PointMapSelection :model-value="props.selectedMap"
                @update:model-value="emits('update:selectedMap', $event)" />
        </div>

        <div v-if="props.hasMaps" class="tool sb" @click="deleteMap" title="Delete map">
            <i class="bi bi-trash" style="opacity: 0.8;"></i>
        </div>

        <WithToolTip v-if="props.hasMaps" message="map.border_width" class="border-width-control d-flex align-items-center">
            <i class="bi bi-border-outer me-1" style="font-size: 13px;"></i>
            <RangeInput :min="0" :max="0.5" :step="0.005" :model-value="props.borderWidth"
                @update:model-value="emits('update:borderWidth', $event)" />
        </WithToolTip>

        <WithToolTip v-if="props.hasMaps" message="map.hover_scale" class="border-width-control d-flex align-items-center">
            <i class="bi bi-arrows-fullscreen me-1" style="font-size: 13px;"></i>
            <RangeInput :min="1" :max="6" :step="0.1" :model-value="props.hoverScale"
                @update:model-value="emits('update:hoverScale', $event)" />
        </WithToolTip>
    </div>
</template>

<style scoped>
.map-header-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 3px;
    background: var(--bg-primary);
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
}

.tool {
    color: var(--text-primary);
    line-height: 100%;
    padding: 3px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.tool:hover {
    background-color: var(--hover-bg);
}

.map-select {
    background-color: var(--island-surface);
    border-radius: var(--radius-sm);
}

.border-width-control {
    color: var(--text-tertiary);
    cursor: pointer;
    padding: 3px;
    gap: 6px;
}

.border-width-control :deep(.custom-slider) {
    width: 90px;
}
</style>
