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
import FilterRow from './FilterRow.vue';
import AddFilterBtn from './AddFilterBtn.vue';

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

</script>

<template>
    <div class="filter-group">
        <table class="table table-sm">
            <tr v-for="children, index in filters" style="height: 33px;">
                <td class="">
                    <div v-if="index == 0" class="m-0 p-0">{{ $t('modals.filters.where') }}</div>
                    <template v-else-if="index == 1">

                        <FilterGroupOperator :model-value="filter.groupOperator"
                            @update:model-value="op => updateOperator(filter.id, op)" />

                    </template>
                    <span v-else class="text-secondary">{{ $t('modals.filters.' + filter.groupOperator) }}</span>
                </td>
                <FilterRow v-if="(children as Filter).propertyId !== undefined" :filter="children"
                    :manager="props.manager" />
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
            <AddFilterBtn :group="props.filter" :manager="props.manager">
                <div class="add-options hover-light"><i class="bi bi-plus"></i>{{ $t('modals.filters.new_filter') }}
                </div>
            </AddFilterBtn>
            <!-- <FilterDropdown :manager="props.manager" :parent-id="filter.id">
                
            </FilterDropdown> -->
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