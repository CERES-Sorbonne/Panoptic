<script setup lang="ts">
import { Instance } from '@/data/models'
import PointMapSelection from './PointMapSelection.vue'
import ActionButton2 from '../actions/ActionButton2.vue'
import { useMediaStore } from '@/data/mediaStore'

const media = useMediaStore()

const props = defineProps<{
    selectedMap: number | null
    hasMaps: boolean
    // Images the 'map' action runs on (the collection's current content). A getter, so the
    // list is materialised on click instead of on every tree tick.
    images: () => Instance[]
}>()

const emits = defineEmits([
    'update:selectedMap',
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
</style>
