<script setup lang="ts">

/** ContentFilter
 *  Main UI to filter/sort/group a list of image
 */
import FilterForm from '../forms/FilterForm.vue';
import GroupForm from '../forms/GroupForm.vue';
import SortForm from '../forms/SortForm.vue';
import RangeInput from '../inputs/RangeInput.vue'
import wTT from '../tooltips/withToolTip.vue'
import { computed, onMounted, ref, watch } from 'vue';
import SelectionStamp from '../selection/SelectionStamp.vue';
import { TabManager } from '@/core/TabManager';
import HistoryDropdown from '../dropdowns/HistoryDropdown.vue';
import ToggleReload from '../toggles/ToggleReload.vue';
import { useInputStore } from '@/data/inputStore';
import TextSearchInput from '../inputs/TextSearchInput.vue';
import { TextQuery } from '@/data/models';

const inputs = useInputStore()

const props = defineProps<{
    tab: TabManager,
    computeStatus: { groups: boolean }
}>()

const emits = defineEmits(['compute-ml', 'search-images', 'remove:selected'])

const localQuery = ref<TextQuery>({ type: 'text', text: '' })

const selectedImageIds = computed(() => Object.keys(props.tab.collection.groupManager.selectedImages.value).map(Number))
const hasSelectedImages = computed(() => selectedImageIds.value.length)


function updateSha1Mode(value: boolean) {
    props.tab.collection.groupManager.setSha1Mode(value, true)
}

function getLocalQuery() {
    localQuery.value = props.tab.state.filterState.query
}

function setQuery(query) {
    localQuery.value = query
    props.tab.collection.filterManager.setQuery(localQuery.value)
    props.tab.collection.filterManager.update(true)
    props.tab.saveState()
}

function deleteQuery() {
    props.tab.collection.filterManager.setQuery({ type: 'text', text: '' })
    props.tab.collection.filterManager.update(true)
}

onMounted(getLocalQuery)
watch(() => props.tab.collection.filterManager.state.query, getLocalQuery)

// keyState.ctrlF.on(() => textInput.value.focus())

</script>

<template>
    <div class="d-flex flex-row pt-2 ps-2 pb-1 align-items-center">
        <TextSearchInput class="me-3" style="flex-shrink: 0;" :query="localQuery" @update:query="setQuery" />

        <div class="me-3 d-flex align-items-center">
            <wTT message="main.menu.grid_tooltip">
                <div class="tool-sm" :class="{ selected: props.tab.state.display == 'tree' }" @click="props.tab.setViewMode('tree')">
                    <i class="bi bi-grid-3x3-gap-fill"></i>
                </div>
            </wTT>
            <wTT message="main.menu.table_tooltip">
                <div class="tool-sm" :class="{ selected: props.tab.state.display == 'grid' }" @click="props.tab.setViewMode('grid')">
                    <i class="bi bi-table"></i>
                </div>
            </wTT>
            <wTT message="main.menu.graph_tooltip">
                <div class="tool-sm" :class="{ selected: props.tab.state.display == 'graph' }" @click="props.tab.setViewMode('graph')">
                    <i class="bi bi-bar-chart"></i>
                </div>
            </wTT>
            <wTT message="main.menu.map_tooltip">
                <div class="tool-sm" :class="{ selected: props.tab.state.display == 'map' }" @click="props.tab.setViewMode('map')">
                    <i class="bi bi-map"></i>
                </div>
            </wTT>
        </div>

        <wTT message="main.menu.image_size_tooltip" :click="false">
            <div class="bi bi-aspect-ratio me-1"></div>
        </wTT>
        <div>
            <RangeInput :min="30" :max="500" v-model="props.tab.state.imageSize" />
        </div>

        <div class="ms-3 d-flex align-items-center">
            <wTT message="main.menu.instance_mode_tooltip">
                <div class="tool-sm" :class="{ selected: !props.tab.collection.groupManager.state.sha1Mode }" @click="updateSha1Mode(false)">
                    <i class="bi bi-image"></i>
                </div>
            </wTT>
            <wTT message="main.menu.image_mode_tooltip">
                <div class="tool-sm" :class="{ selected: props.tab.collection.groupManager.state.sha1Mode }" @click="updateSha1Mode(true)">
                    <i class="bi bi-images"></i>
                </div>
            </wTT>
        </div>

        <div class="ms-3">
            <HistoryDropdown />
        </div>
        <div>
            <SelectionStamp v-if="hasSelectedImages" class="ms-5" style="font-size: 14px;"
                :selected-images-ids="selectedImageIds"
                @remove:selected="props.tab.collection.groupManager.clearSelection()"
                @stamped="props.tab.collection.groupManager.clearSelection()" />
        </div>
        <div class="flex-grow-1"></div>
        <wTT message="main.menu.issue" class="bb ">
            <a href="https://github.com/CERES-Sorbonne/Panoptic/issues/new/choose" target="_blank"
                class="bi bi-cone-striped" style="color: grey"></a>
        </wTT>
    </div>
    <div class="d-flex flex-wrap content-container ps-2 align-items-center">
        <ToggleReload :tab="props.tab" class="me-1" />
        <FilterForm :manager="props.tab.collection.filterManager" />
        <GroupForm :is-loading="props.computeStatus.groups" :manager="props.tab.collection.groupManager" />
        <SortForm :manager="props.tab.collection.sortManager" />
        <div>
        </div>
    </div>
</template>

<style scoped>
.custom-toggle {
    --toggle-width: 60px !important;
    --toggle-bg-on: #a5a5a5;
    --toggle-border-on: #a5a5a5;
}

.center-block {
    margin: auto;
    display: block;
}

.unique-switch {
    height: 10px;
}

.unique-switch:focus {
    height: 10px;
    box-shadow: none;
}

.content-container {
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 5px;
    margin: 0;
}

.search-input {
    border: 2px solid rgb(197, 206, 213);
    padding: 1px;
    margin: 0px;
    border-radius: 3px;
    width: 180px;
}

.input-hidden {
    -webkit-appearance: none !important;
    -moz-appearance: none !important;
    appearance: none !important;
    border: none;
    margin: 0;
    padding: 0;
    margin-top: 1px;
    height: 16px;
    font-size: 10px;
    color: var(--text-color);
    width: 100%;
}

.input-hidden:focus {
    -webkit-appearance: none !important;
    -moz-appearance: none !important;
    appearance: none !important;
    outline-width: 0;
    border: 0;
    outline: none;
}

.bi-sm {
    font-size: 10px;
    color: rgb(120, 137, 150);
    margin-top: 2px;
    margin-right: 4px;
    margin-left: 3px;
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

.tool-sm {
    color: rgb(0, 0, 0);
    line-height: 100%;
    padding: 5px;
    border-radius: 5px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.tool:hover,
.tool-sm:hover {
    background-color: rgba(137, 176, 205, 0.4);
}

.selected,
.selected:hover {
    color: rgb(255, 255, 255);
    background-color: #384955;
}
</style>