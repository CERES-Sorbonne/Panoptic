<script setup lang="ts">
import { Tab } from '@/data/models';
import FilterForm from '../forms/FilterForm.vue';
import GroupForm from '../forms/GroupForm.vue';
import SortForm from '../forms/SortForm.vue';
import RangeInput from '../inputs/RangeInput.vue'
import {apiStartPCA} from '../../data/api'


const props = defineProps({
    tab: Object as () => Tab,
    computeStatus: Object as () => {groups: boolean}
})

const emits = defineEmits(['compute-ml', 'search-images'])

</script>

<template>
    <div class="d-flex flex-row p-2">
        <div class="d-flex flex-row search-input me-5">
            <div class="bi bi-search float-start bi-sm"></div>
            <input type="text" class="input-hidden" placeholder="Chercher par texte" @keyup.enter="$emit('search-images',($event.target as HTMLInputElement).value)"/>
        </div>
        <div class="bi bi-aspect-ratio me-1"></div>
        <div>
            <RangeInput :min="50" :max="500" v-model="props.tab.data.imageSize" />
        </div>
        <!-- <div class="ms-5">
            <button class="me-2" @click="apiStartPCA">PCA</button>
        </div> -->
        <!-- <span class="ms-2">({{ props.imageSize }}px)</span> -->
    </div>
    <div class="d-flex flex-wrap content-container">
        <FilterForm :filter="props.tab.data.filter" />
        <GroupForm :groupIds="props.tab.data.groups" :is-loading="props.computeStatus.groups"/>
        <SortForm :sortList="props.tab.data.sortList" />
        <!-- <div class="ms-2">
            <button @click="$emit('compute-ml')">Compute All Groups</button>
        </div> -->
    </div>
</template>

<style scoped>

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