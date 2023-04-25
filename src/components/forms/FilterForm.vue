<script setup lang="ts">
import { Filter, FilterGroup, FilterOperator, Property } from '@/data/models';
import FilterInputDropdown from '../inputs/FilterInputDropdown.vue';
import GlobalFilterInputDropdown from '../inputs/GlobalFilterInputDropdown.vue';
import { globalStore } from '@/data/store';
import { defaultOperator } from '@/utils/filter';

const props = defineProps({
    filter: Object as () => FilterGroup
})

function addNewFilter() {
    let property = (Object.values(globalStore.properties)[0] as Property)

    let filter: Filter = {
        propertyId: property.id,
        operator: defaultOperator(property.type),
        value: undefined,
    }
    props.filter.filters.push(filter)
}

function addNewGroupFilter() {
    let filter: FilterGroup = {
        filters: [],
        groupOperator: FilterOperator.or,
        depth: props.filter.depth + 1,
        isGroup: true
    }
    props.filter.filters.push(filter)
}

</script>

<template>
    <div class="d-flex flex-row">
        <div class="">
            <GlobalFilterInputDropdown :model-value="props.filter" @update:model-value="e => Object.assign(props.filter, e)"/>
        </div>
        <div class="btn btn-sm border me-1" style="cursor: inherit;" @click="props.filter.groupOperator = props.filter.groupOperator == FilterOperator.and ? FilterOperator.or : FilterOperator.and">{{
            props.filter.groupOperator == FilterOperator.and ? 'All' : 'Any' }}</div>
        <div v-for="filter, index in props.filter.filters">
            <FilterInputDropdown v-model="props.filter.filters[index]" @delete="props.filter.filters.splice(index, 1)" />
        </div>
        <div class="btn btn-sm no-border me-1 p-1 hover-light" data-bs-toggle="dropdown" data-bs-auto-close="true">
            <i class="bi bi-plus"></i>
        </div>
        <ul class="dropdown-menu p-1 btn-icon">
            <li class="mb-1 hover-light rounded ps-1 pe-1" @click="addNewFilter">Add new filter</li>
            <li class="mb-1 hover-light rounded ps-1 pe-1" @click="addNewGroupFilter">Add new group</li>
        </ul>
    </div>
</template>