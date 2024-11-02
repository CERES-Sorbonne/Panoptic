<script setup lang="ts">
import { computed } from 'vue';
import FilterDropdown from '../dropdowns/FilterDropdown.vue';
import FilterPreview from '../preview/FilterPreview.vue';
import PropertyDropdown from '../properties/PropertyDropdown.vue';
import Dropdown from '../dropdowns/Dropdown.vue';
import { Filter, FilterGroup, FilterManager, FilterOperator } from '@/core/FilterManager';
import { useDataStore } from '@/data/dataStore';
import GridPropInput from '../scrollers/grid/GridPropInput.vue';
import FilterGroupOperator from './FilterGroupOperator.vue';
import FilterGroupVue from './FilterGroup.vue'
import OperatorChoice from './OperatorChoice.vue';
import FilterValueInput from './FilterValueInput.vue';

const data = useDataStore()

const props = defineProps<{
    filter: FilterGroup,
    manager: FilterManager,
    parent?: HTMLElement
}>()

const emits = defineEmits(['delete'])


const filter = computed(() => props.filter as FilterGroup)
const filters = computed(() => filter.value.filters)
const subGroupStyle = computed(() => {
    let val = 255 - ((filter.value.depth + 1) * 5)
    return `background: rgb(${val},${val},${val});`
})

function updateProperty(filterId: number, propertyId: number) {
    props.manager.updateFilter(filterId, { propertyId })
    // props.manager.update(true)
}

function deleteFilter(filter: Filter | FilterGroup) {
    props.manager.deleteFilter(filter.id)
    // props.manager.update(true)
}

function addFilterGroup(filterId: number) {
    props.manager.addNewFilterGroup(filterId)
    // props.manager.update(true)
}

function updateOperator(filterId: number, operator: FilterOperator.and | FilterOperator.or) {
    props.manager.updateFilterGroup(filterId, operator)
    // props.manager.update(true)
}

function updateFilterOperator(filterId: number, operator: FilterOperator) {
    props.manager.updateFilter(filterId, {operator: operator})
}

function updateFilterValue(filterId: number, value: any) {
    props.manager.updateFilter(filterId, {value: value})
}

</script>

<template>
    <div class="filter-group">
        <table class="table table-sm">
            <tr v-for="children, index in filters">
                <td class="align-top p-0 m-0">
                    <div v-if="index == 0" class="m-0 p-0">{{ $t('modals.filters.where') }}</div>
                    <template v-else-if="index == 1">

                        <FilterGroupOperator :model-value="filter.groupOperator"
                            @update:model-value="op => updateOperator(filter.id, op)" />

                    </template>
                    <span v-else class="text-secondary">{{ $t('modals.filters.' + filter.groupOperator) }}</span>
                </td>
                <td v-if="(children as Filter).propertyId !== undefined" class="p-0 m-0 ps-2">
                    <PropertyDropdown :model-value="data.properties[(children as Filter).propertyId]"
                        @update:model-value="p => updateProperty(children.id, p.id)" />
                </td>
                <td v-if="(children as Filter).propertyId !== undefined">
                    <OperatorChoice :property-id="children.propertyId" :model-value="children.operator" @update:model-value="op => updateFilterOperator(children.id, op)"/>
                </td>
                <td v-if="(children as Filter).propertyId !== undefined" style="width: 150px;">
                    <FilterValueInput :model-value="children.value" @update:model-value="v => updateFilterValue(children.id, v)" :property="data.properties[children.propertyId]" :width="100" />
                </td>

                <!-- <td v-if="(children as Filter).propertyId !== undefined" class="p-0 m-0 ps-2">
                    <FilterDropdown class="flex-grow-1" :manager="manager" :mode="2" :parent-id="filter.id"
                        :filter-id="children.id" :parent="props.parent">
                        <FilterPreview :filter="(children as Filter)" />
                    </FilterDropdown>
                </td> -->
                <td v-else colspan="3" :style="subGroupStyle">
                    <div class="border rounded">
                        <FilterGroupVue :filter="(children as FilterGroup)" :manager="props.manager" />
                    </div>
                </td>
                <td class="">
                    <span class="base-btn" @click="deleteFilter(children)">
                        <i class="bi bi-trash"></i>
                    </span>
                </td>
            </tr>
        </table>

        <div class="d-flex text-secondary ms-2">
            <FilterDropdown :manager="props.manager" :parent-id="filter.id">
                <div class="add-options hover-light"><i class="bi bi-plus"></i>{{ $t('modals.filters.new_filter') }}
                </div>
            </FilterDropdown>
            <div class="add-options hover-light" @click="addFilterGroup(filter.id)">
                <i class="bi bi-plus"></i>{{ $t('modals.filters.new_group') }}
            </div>
        </div>

    </div>
</template>

<style scoped>
.filter-group {
    min-width: 300px;
}

.operator-offset {
    padding-left: 2px;
}

.add-options {
    margin-right: 10px;
    cursor: pointer;
    padding-right: 4px;
    border-radius: 3px;
}
</style>