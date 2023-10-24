<script setup lang="ts">
import { Tab } from '@/data/models';
import FilterForm from '../forms/FilterForm.vue';
import GroupForm from '../forms/GroupForm.vue';
import SortForm from '../forms/SortForm.vue';
import RangeInput from '../inputs/RangeInput.vue'
import { apiStartPCA } from '../../data/api'
import Toggle from '@vueform/toggle'
import { computed, ref } from 'vue';
import { globalStore } from '@/data/store';
import SelectionStamp from '../selection/SelectionStamp.vue';

const props = defineProps({
    tab: Object as () => Tab,
    computeStatus: Object as () => { groups: boolean },
    selectedImages: Object as () => {[imgId: string]: boolean}
})

const emits = defineEmits(['compute-ml', 'search-images', 'remove:selected'])

const selectedImageIds = computed(() => Object.keys(props.selectedImages).map(Number))
const hasSelectedImages = computed(() => selectedImageIds.value.length > 0)

</script>

<template>
    <div class="d-flex flex-row p-2">
        <div class="d-flex flex-row search-input me-5">
            <div class="bi bi-search float-start bi-sm"></div>
            <input type="text" class="input-hidden" placeholder="Chercher par texte"
                @keyup.enter="$emit('search-images', ($event.target as HTMLInputElement).value)" />
        </div>

        <div class="me-5">
            <i class="bi bi-grid-3x3-gap-fill me-2 btn-icon" @click="props.tab.data.display = 'tree'"></i>
            <i class="bi bi-table btn-icon"  @click="props.tab.data.display = 'grid'"></i>
        </div>

        <div class="bi bi-aspect-ratio me-1"></div>
        <div>
            <RangeInput :min="30" :max="500" v-model="props.tab.data.imageSize" />
        </div>
        <div class="ms-5">
            <Toggle v-model="props.tab.data.sha1Mode" on-label="Unique" off-label="All" class="custom-toggle" />
        </div>
        <SelectionStamp v-if="hasSelectedImages" class="ms-5" :selected-images-ids="selectedImageIds" @remove:selected="emits('remove:selected')"/>

        <!-- <div class="ms-5">
            <button class="me-2" @click="apiStartPCA">PCA</button>
        </div> -->
        <!-- <span class="ms-2">({{ props.imageSize }}px)</span> -->
    </div>
    <div class="d-flex flex-wrap content-container">
        <FilterForm :filter="props.tab.data.filter" />
        <GroupForm :groupIds="props.tab.data.groups" :is-loading="props.computeStatus.groups" />
        <SortForm :sortList="props.tab.data.sortList" />
        <!-- <div class="ms-2">
            <button @click="$emit('compute-ml')">Compute All Groups</button>
        </div> -->
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