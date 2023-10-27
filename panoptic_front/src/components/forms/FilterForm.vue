<script setup lang="ts">
import { Filter, FilterGroup, FilterOperator, Property } from '@/data/models';
import GlobalFilterInputDropdown from '../inputs/GlobalFilterInputDropdown.vue';
import { FilterManager, defaultOperator } from '@/utils/filter';
import PropertySelection from '../inputs/PropertySelection.vue';
import FilterDropdown from '../dropdowns/FilterDropdown.vue';

const props = defineProps({
    filter: Object as () => FilterGroup,
    manager: FilterManager
})

// function addNewFilter(property: Property) {
//     // let property = (Object.values(globalStore.properties)[0] as Property)

//     let filter: Filter = {
//         propertyId: property.id,
//         operator: defaultOperator(property.type),
//         value: undefined,
//     }
//     props.filter.filters.push(filter)
// }

// function addNewGroupFilter() {
//     let filter: FilterGroup = {
//         filters: [],
//         groupOperator: FilterOperator.or,
//         depth: props.filter.depth + 1,
//         isGroup: true
//     }
//     props.filter.filters.push(filter)
// }

</script>

<template>
    <div class="d-flex flex-row">
        <div class="label me-0 pe-1">Filtres</div>
        <!-- <div class="">
            <GlobalFilterInputDropdown :model-value="props.filter" @update:model-value="e => Object.assign(props.filter, e)"/>
        </div> -->
        <!-- <div class="btn btn-sm border rounded bg-white hover-light me-1" @click="props.filter.groupOperator = props.filter.groupOperator == FilterOperator.and ? FilterOperator.or : FilterOperator.and">{{
            props.filter.groupOperator == FilterOperator.and ? 'All' : 'Any' }}</div> -->
        <!-- <div v-for="filter, index in props.filter.filters">
            <FilterInputDropdown v-model="props.filter.filters[index]" @delete="props.filter.filters.splice(index, 1)" />
        </div> -->
        <!-- <i class="bi bi-plus"></i> -->
        <GlobalFilterInputDropdown :model-value="props.filter" @update:model-value="e => Object.assign(props.filter, e)"/>
      
        <FilterDropdown :manager="props.manager">
            <span class="hover-light btn btn-sm ps-1 pe-1">+</span>
        </FilterDropdown>
        <!-- <div class="btn btn-sm no-border me-1 p-1 hover-light text-secondary" data-bs-toggle="dropdown"
            data-bs-auto-close="true">
            <i class="bi bi-plus"></i>
        </div>
        <div class="dropdown-menu p-0"> -->
            <!-- <PropertySelection @select="" /> -->
            <!-- <hr class="dropdown-divider">
            <div class="hover-light p-1 ps-2 mb-1 btn-icon" @click="addNewGroupFilter">Filter group</div> -->
        <!-- </div> -->
    </div>
</template>