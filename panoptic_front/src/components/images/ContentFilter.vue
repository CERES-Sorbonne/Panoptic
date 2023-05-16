<script setup lang="ts">
import { Tab, TabState } from '@/data/models';
import FilterForm from '../forms/FilterForm.vue';
import GroupForm from '../forms/GroupForm.vue';
import SortForm from '../forms/SortForm.vue';
import RangeInput from '../inputs/RangeInput.vue'
import { computed } from 'vue';


const props = defineProps({
    tab: Object as () => Tab,
})

</script>

<template>
    <div class="d-flex flex-row">
        <div class="d-flex flex-row search-input me-5">
            <div class="bi bi-search float-start bi-sm"></div>
            <input type="text" class="input-hidden" placeholder="rechercher dans tous les champs..." />
        </div>
        <div class="bi bi-aspect-ratio me-1"></div>
        <div>
            <RangeInput :min="50" :max="200" v-model="props.tab.data.imageSize" />
        </div>
        <div class="ms-5">
            <input type="text" class="text-input" v-model="props.tab.name"/>
        </div>
        <!-- <span class="ms-2">({{ props.imageSize }}px)</span> -->
    </div>
    <div class="d-flex flex-wrap mb-3 mt-3">
        <FilterForm :filter="props.tab.data.filter" />
        <GroupForm :groupIds="props.tab.data.groups" />
        <SortForm :sortList="props.tab.data.sortList" />
    </div>
</template>

<style scoped>
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