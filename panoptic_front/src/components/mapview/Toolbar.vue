<script setup lang="ts">
import { computed } from 'vue'
import RangeInput from '../inputs/RangeInput.vue'
import PointMapSelection from './PointMapSelection.vue'
import SelectDropdown, { SelectOption } from '../dropdowns/SelectDropdown.vue'
import ActionButton2 from '../actions/ActionButton2.vue'
import { useI18n } from 'vue-i18n'
import { Instance } from '@/data/models'
import { useDataStore } from '@/data/dataStore'
import { useTabStore } from '@/data/tabStore'

const { t } = useI18n()

const data = useDataStore()

const props = defineProps<{
    mouseMode: string
    imageSize: number
    zoomDelay: number
    showPoint: boolean
    selectedMap: number | null
    colorOption: string
    hasMaps: boolean
    images: Instance[]
}>()

const emits = defineEmits([
    'update:mouseMode',
    'update:imageSize',
    'update:zoomDelay',
    'update:showPoint',
    'update:selectedMap',
    'update:colorOption',
    'clusters',
    'delete:map'
])

const colorOptions = computed<SelectOption[]>(() => {
    return [
        { value: 'property', label: t('map.color_prop'), icon: 'stack' },
        { value: 'cluster', label: t('map.color_cluster'), icon: 'stack' }
    ]
})

function changeTool(tool: string) {
    emits('update:mouseMode', tool)
}

function deleteMap() {
    useDataStore().deleteMap(props.selectedMap)
}

function updateMap(event) {
    console.log(event)
    emits('update:selectedMap', event.value.id)
}

const selectedImages = computed(() => Object.keys(useTabStore().getMainTab().collection.groupManager.selectedImages.value).map(Number).map(id => data.instances[id]))
</script>

<template>
    <div class="glass-box2 d-flex align-items-center">
        <div class="toolbar-item px-1 d-flex align-items-center gap-1">
            <div v-if="props.hasMaps" class="tool sb" @click="deleteMap">
                <i class="bi bi-trash" style="opacity: 0.8;"></i>
            </div>
            <div v-if="props.hasMaps" style="min-width: 150px;" class="map-select">
                <PointMapSelection :model-value="props.selectedMap"
                    @update:model-value="emits('update:selectedMap', $event)" />
            </div>
        </div>
        <div class="toolbar-item text-secondary">
            <ActionButton2 action="map" class="bb ps-1 pe-1" style="font-size: 14px;" :no-border="true" @call="updateMap" :images="selectedImages">
                <i class="bi bi-boxes" /> {{ $t('map.create') }}
            </ActionButton2>
        </div>

        <div class="divider"></div>

        <div class="toolbar-item d-flex align-items-center gap-1">
            <div style="min-width: 120px;">
                <SelectDropdown :teleport="true" :options="colorOptions" :model-value="props.colorOption"
                    @update:model-value="e => emits('update:colorOption', e)" :no-border="true" />
            </div>
        </div>

        <div v-if="props.colorOption === 'cluster'" class="toobar-item">
            <ActionButton2 :images="props.images" action="group" class="sb ps-1 pe-1" style="font-size: 14px;" :no-border="true" @groups="clusters => emits('clusters', clusters)">
                <img class="cluster-icon" src="/icons/network2_white.svg" />
            </ActionButton2>
        </div>

        <div class="divider"></div>

        <div class="tool" :class="{ selected: props.showPoint }" @click="emits('update:showPoint', !props.showPoint)"
            title="Show Points">
            <i class="bi bi-dot"></i>
        </div>
        <div class="tool" :class="{ selected: props.mouseMode == 'pan' }" @click="changeTool('pan')" title="Pan">
            <i class="bi bi-hand-index-thumb"></i>
        </div>
        <div class="tool" :class="{ selected: props.mouseMode == 'lasso-plus' }" @click="changeTool('lasso-plus')"
            title="Lasso Add">
            <i class="bi bi-plus-circle-dotted"></i>
        </div>
        <div class="tool" :class="{ selected: props.mouseMode == 'lasso-minus' }" @click="changeTool('lasso-minus')"
            title="Lasso Remove">
            <i class="bi bi-dash-circle-dotted"></i>
        </div>

        <div class="divider"></div>

        <div class="tool-icon ms-1"><i class="bi bi-aspect-ratio"></i></div>
        <RangeInput style="width: 60px;" :min="1" :max="10" :modelValue="props.imageSize"
            @update:modelValue="e => emits('update:imageSize', e)" />

        <div class="tool-icon ms-1"><i class="bi bi-border"></i></div>
        <RangeInput style="width: 60px;" :min="1" :max="10" :modelValue="props.zoomDelay"
            @update:modelValue="e => emits('update:zoomDelay', e)" />
    </div>
</template>

<style scoped>
.glass-box2 {
    padding: 4px 8px;
    background: rgb(246, 247, 249);
    /* backdrop-filter: blur(10px); */
    /* -webkit-backdrop-filter: blur(10px); */
    border-bottom: 1px solid var(--border-color);
    /* box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); */
    /* border-radius: 8px; */
    border-radius: 0px;
    column-gap: 4px;
}

.toolbar-item {
    display: flex;
    align-items: center;
}

.tool {
    color: rgb(0, 0, 0);
    line-height: 100%;
    padding: 6px;
    border-radius: 5px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.tool-icon {
    color: rgb(0, 0, 0);
    line-height: 100%;
    padding: 4px 0px;
    opacity: 0.7;
    display: flex;
    align-items: center;
}

.tool:hover {
    background-color: rgba(137, 176, 205, 0.4);
}

.selected,
.selected:hover {
    color: rgb(255, 255, 255);
    background-color: #384955;
}

.divider {
    height: 24px;
    border-left: 1px solid rgba(0, 0, 0, 0.1);
    margin: 0 4px;
}

.map-select {
    background-color: white;
    border-radius: 5px;
}
</style>