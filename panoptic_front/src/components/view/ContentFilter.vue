<script setup lang="ts">

/** ContentFilter
 *  Main UI to filter/sort/group a list of image
 */
import FilterForm from '../forms/FilterForm.vue';
import GroupForm from '../forms/GroupForm.vue';
import SortForm from '../forms/SortForm.vue';
import RangeInput from '../inputs/RangeInput.vue'
import Toggle from '@vueform/toggle'
import wTT from '../tooltips/withToolTip.vue'
import { computed, onMounted, ref, watch } from 'vue';
import SelectionStamp from '../selection/SelectionStamp.vue';
import { TabManager } from '@/core/TabManager';

const props = defineProps({
    tab: TabManager,
    computeStatus: Object as () => { groups: boolean },
})

const emits = defineEmits(['compute-ml', 'search-images', 'remove:selected'])

const localQuery = ref('')

const selectedImageIds = computed(() => Object.keys(props.tab.collection.groupManager.selectedImages).map(Number))
const hasSelectedImages = computed(() => selectedImageIds.value.length)


function updateSha1Mode(event) {
    const value = event.target.checked
    props.tab.collection.groupManager.setSha1Mode(value, true)
}

function getLocalQuery() {
    localQuery.value = props.tab.state.filterState.query
}

function setQuery() {
    props.tab.collection.filterManager.setQuery(localQuery.value)
    props.tab.collection.filterManager.update(true)
}

function deleteQuery() {
    props.tab.collection.filterManager.setQuery('')
    props.tab.collection.filterManager.update(true)
}


onMounted(getLocalQuery)
watch(() => props.tab.collection.filterManager.state.query, getLocalQuery)

</script>

<template>
    <div class="d-flex flex-row p-2">
        <wTT :icon="true" message="main.menu.search_tooltip" iconPos="left">
            <div class="d-flex flex-row search-input me-5"  :class="localQuery ? 'border-primary' : ''">
                <div class="bi bi-search float-start bi-sm"></div>
                <input type="text" class="input-hidden" :placeholder="$t('main.menu.search')" v-model="localQuery" @change="setQuery"/>
                <div class="bi-sm base-hover" style="cursor: pointer; padding: 0px 2px;" @click="deleteQuery">x</div>
            </div>
        </wTT>

        <div class="me-5 d-flex">
            <wTT message="main.menu.grid_tooltip">
                <i :class="'bi bi-grid-3x3-gap-fill me-2 btn-icon' + (props.tab.state.display == 'tree' ? '' : ' text-secondary')"
                    @click="props.tab.state.display = 'tree'"></i>
            </wTT>
            <wTT message="main.menu.table_tooltip">
                <i id="toot" :class="'bi bi-table btn-icon' + (props.tab.state.display == 'grid' ? '' : ' text-secondary')"
                    @click="props.tab.state.display = 'grid'">
                </i>
            </wTT>
        </div>

        <wTT message="main.menu.image_size_tooltip" :click="false">
            <div class="bi bi-aspect-ratio me-1"></div>
        </wTT>
        <div>
            <RangeInput :min="30" :max="500" v-model="props.tab.state.imageSize" />
        </div>
        <div class="ms-5" style="font-size: 13px;">
            <wTT message="main.menu.image_mode_tooltip">
                <input type="checkbox" :checked="props.tab.collection.groupManager.state.sha1Mode" @change="updateSha1Mode"/>
                <span class="ms-1">Mode Image unique</span>
            </wTT>
        </div>
        <SelectionStamp id="selection-stamp" v-if="hasSelectedImages" class="ms-5" :selected-images-ids="selectedImageIds"
            @remove:selected="props.tab.collection.groupManager.clearSelection()" />
    </div>
    <div class="d-flex flex-wrap content-container ps-2">
        <FilterForm :manager="props.tab.collection.filterManager" />
        <GroupForm :is-loading="props.computeStatus.groups" :manager="props.tab.collection.groupManager" />
        <SortForm :manager="props.tab.collection.sortManager" />
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
    /* line-height: 10px; */
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
</style>