<script setup lang="ts">
import { Filter, FilterGroup, FilterOperator, Property } from '@/data/models';
import GlobalFilterInputDropdown from '../inputs/GlobalFilterInputDropdown.vue';
import { FilterManager, defaultOperator } from '@/utils/filter';
import PropertySelection from '../inputs/PropertySelection.vue';
import FilterDropdown from '../dropdowns/FilterDropdown.vue';

const props = defineProps({
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
    <div class="d-flex flex-row filter-form">
        <div class="pt-1 pb-1">Filtres:</div>
        <GlobalFilterInputDropdown :model-value="props.manager.filter" :manager="props.manager"/>
      
        <FilterDropdown :manager="props.manager" class="p-1">
            <span class="base-hover plus-btn text-secondary "><i class="bi bi-plus"></i></span>
        </FilterDropdown>
    </div>
</template>

<style scoped>

.filter-form {
    color: rgb(33, 37, 41);
    font-size: 14px;
}

.plus-btn {
    padding: 4px;
    border-radius: 3px;
}

</style>