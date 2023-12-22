<script setup lang="ts">
import { useStore } from '@/data/store'
import { computed } from 'vue';
import FilterDropdown from '../dropdowns/FilterDropdown.vue';
import FilterPreview from '../preview/FilterPreview.vue';
import PropertyDropdown from '../properties/PropertyDropdown.vue';
import Dropdown from '../dropdowns/Dropdown.vue';
import { Filter, FilterGroup, FilterManager, FilterOperator } from '@/core/FilterManager';
const store = useStore()
const props = defineProps({
    filter: Object as () => FilterGroup,
    manager: FilterManager,
    parent: HTMLElement
})

const emits = defineEmits(['delete'])


const filter = computed(() => props.filter as FilterGroup)
const filters = computed(() => filter.value.filters)
const subGroupStyle = computed(() => {
    let val = 255 - ((filter.value.depth + 1) * 5)
    return `background: rgb(${val},${val},${val});`
})

function updateFilter(filterId: number, propertyId: number) {
    props.manager.updateFilter(filterId, { propertyId })
    props.manager.update(true)
}

function deleteFilter(filter: Filter | FilterGroup) {
    props.manager.deleteFilter(filter.id)
    props.manager.update(true)
}

function addFilterGroup(filterId: number) {
    props.manager.addNewFilterGroup(filterId)
    props.manager.update(true)
}

</script>

<template>
    <div class="filter-group">
        <table class="table table-sm">
            <tr v-for="children, index in filters">
                <td class="align-top ps-2">
                    <div v-if="index == 0" class="m-0 p-0">{{ $t('modals.filters.where') }}</div>
                    <template v-else-if="index == 1">

                        <Dropdown>
                            <template #button>
                                <div class="p-0 hover-light ps-1" style="width: 50px; cursor: pointer; border-radius: 3px;">
                                    <span class="">{{ $t('modals.filters.' + filter.groupOperator) }}</span>
                                </div>
                            </template>
                            <template #popup="{ hide }">
                                <div class="ps-2 pt-1 pb-1 pe-2" @click="hide">
                                    <div class="base-btn" @click="filter.groupOperator = FilterOperator.and">
                                        {{ $t('modals.filters.and') }}
                                    </div>
                                    <hr class="m-0 p-0 mt-1 mb-1" />
                                    <div class="base-btn" @click="filter.groupOperator = FilterOperator.or">
                                        {{ $t('modals.filters.or') }}
                                    </div>
                                </div>
                            </template>
                        </Dropdown>

                    </template>
                    <span v-else class="text-secondary">{{ (filter as FilterGroup).groupOperator }}</span>
                </td>
                <td v-if="(children as Filter).propertyId !== undefined" class="p-0 m-0 ps-2">
                    <PropertyDropdown :model-value="store.data.properties[(children as Filter).propertyId]"
                        @update:model-value="p => updateFilter(children.id, p.id)" />
                </td>
                <td v-if="(children as Filter).propertyId !== undefined" class="p-0 m-0 ps-2">
                    <FilterDropdown class="flex-grow-1" :manager="manager" :mode="2" :parent-id="filter.id"
                        :filter-id="children.id" :parent="props.parent">
                        <FilterPreview :filter="(children as Filter)" />
                    </FilterDropdown>
                </td>
                <template v-else>
                    <td colspan="3" :style="subGroupStyle">
                        <div class="border rounded">
                            <FilterGroupInput :filter="(children as FilterGroup)" :manager="props.manager" />
                        </div>
                    </td>
                </template>
                <td class="">
                    <span class="base-btn" @click="deleteFilter(children)">
                        <i class="bi bi-trash"></i>
                    </span>
                </td>
            </tr>
        </table>

        <div class="d-flex text-secondary ms-2">
            <FilterDropdown :manager="props.manager" :parent-id="filter.id">
                <div class="add-options hover-light"><i class="bi bi-plus"></i>{{ $t('modals.filters.new_filter') }}</div>
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