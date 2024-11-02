<script setup lang="ts">
import { Filter, FilterManager, FilterOperator, operatorHasInput } from '@/core/FilterManager';
import { defineProps, defineEmits, computed } from 'vue'
import OperatorChoice from './OperatorChoice.vue';
import PropertyDropdown from '../properties/PropertyDropdown.vue';
import FilterValueInput from './FilterValueInput.vue';
import { useDataStore } from '@/data/dataStore';
import { Property } from '@/data/models';

const data = useDataStore()

const props = defineProps<{
    manager: FilterManager
    filter: Filter
}>()
const emits = defineEmits([])

const property = computed(() => data.properties[props.filter.propertyId])
const hasValue = computed(() => operatorHasInput(props.filter.operator))

function updateFilterOperator(operator: FilterOperator) {
    props.manager.updateFilter(props.filter.id, { operator: operator })
}

function updateFilterValue(value: any) {
    props.manager.updateFilter(props.filter.id, { value: value })
}

function updateProperty(prop: Property) {
    props.manager.updateFilter(props.filter.id, { propertyId: prop.id })
    // props.manager.update(true)
}

</script>

<template>
    <td class="p-0 m-0 ps-2">
        <PropertyDropdown :model-value="property" @update:model-value="updateProperty" />
    </td>
    <td>
        <OperatorChoice :property-id="property.id" :model-value="props.filter.operator"
            @update:model-value="updateFilterOperator" />
    </td>
    <td>
        <FilterValueInput v-if="hasValue" :model-value="props.filter.value" @update:model-value="updateFilterValue"
            :property="property" :width="140" style="width: 150px;" class=""/>

    </td>
</template>

<style scoped></style>