<script setup lang="ts">
import { Filter, FilterGroup, FilterOperator, Property, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed, onMounted, watch } from 'vue';
import FilterDropdown from '../dropdowns/FilterDropdown.vue';
import FilterPreview from '../preview/FilterPreview.vue';
import PropertySelection from './PropertySelection.vue';
import PropertyDropdown from '../properties/PropertyDropdown.vue';
import Dropdown from '../dropdowns/Dropdown.vue';
import { FilterManager } from '@/core/FilterManager';

const props = defineProps({
    // filter: { type: Object as () => FilterGroup, required: true },
    manager: FilterManager,
    parent: HTMLElement
})

const emits = defineEmits(['delete'])


const filter = computed(() => props.manager.state.filter as FilterGroup)
const filters = computed(() => filter.value.filters)
const subGroupStyle = computed(() => {
    let val = 255 - ((filter.value.depth + 1) * 5)
    return `background: rgb(${val},${val},${val});`
})

function updateFilter(filterId: number, propertyId: number) {
    props.manager.updateFilter(filterId, {propertyId})
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

// onMounted(() => {
//     if (props.filter.filters.length == 0 && props.filter.depth > 0) {
//         addNewFilter()
//     }
// })

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
                            <template #popup="{hide}">
                                <div class="ps-2 pt-1 pb-1 pe-2" @click="hide">
                                    <div class="base-btn" @click="filter.groupOperator = FilterOperator.and">
                                        {{ $t('modals.filters.and') }}
                                    </div>
                                    <hr class="m-0 p-0 mt-1 mb-1"/>
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
                    <PropertyDropdown :model-value="globalStore.properties[(children as Filter).propertyId]"
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
                            <FilterGroupInput :filter="(filter as FilterGroup)" :manager="props.manager" />
                        </div>
                    </td>
                </template>
                <td class="">
                    <span class="base-btn" @click="deleteFilter(children)">
                        <i class="bi bi-trash"></i>
                    </span>
                    <!-- <div class="m-0 p-0 ms-1 me-1">
                        <div class="text-secondary" data-bs-toggle="dropdown" data-bs-auto-close="true"
                            aria-expanded="false"><i class="bi bi-three-dots btn-icon"></i></div>
                        <ul class="dropdown-menu bg-white m-0 p-0">
                            <li><a class="dropdown-item" href="#" @click="deleteFilter(filter)"><i
                                        class="bi bi-trash me-1"></i>{{$t('modals.filters.remove')}}</a></li>
                        </ul>
                    </div> -->
                </td>
            </tr>
            <!-- <tr>
                <td colspan="2" class="text-start">
                    <span>
                        <button class="btn dropdown-toggle no-border text-secondary ms-0 ps-0" type="button"
                            data-bs-toggle="dropdown" data-bs-auto-close="true" aria-expanded="false">
                            <span><i class="bi bi-plus"></i>Add filter rule</span>
                        </button>
                        <ul class="dropdown-menu bg-white m-0 p-0">
                            <li><a class="dropdown-item" href="#" @click="addNewFilter">New Filter</a></li>
                            <li v-if="props.filter.depth < 2"><a class="dropdown-item" href="#"
                                    @click="addNewGroupFilter">New Group Filter</a>
                            </li>
                        </ul>
                    </span>
                </td>
            </tr> -->
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