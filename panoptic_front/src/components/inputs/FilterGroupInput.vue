<script setup lang="ts">
import { Filter, FilterGroup, FilterOperator, Property, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed, onMounted, watch } from 'vue';
import { FilterManager, defaultOperator } from '@/utils/filter';
import FilterDropdown from '../dropdowns/FilterDropdown.vue';
import FilterPreview from '../preview/FilterPreview.vue';

const props = defineProps({
    filter: { type: Object as () => FilterGroup, required: true },
    manager: FilterManager
})

const emits = defineEmits(['delete'])

const filters = computed(() => props.filter.filters)
const subGroupStyle = computed(() => {
    let val = 255 - ((props.filter.depth + 1) * 5)
    return `background: rgb(${val},${val},${val});`
})

function addNewFilter() {
    let property = (Object.values(globalStore.properties)[0] as Property)

    let filter: Filter = {
        propertyId: property.id,
        operator: defaultOperator(property.type),
        value: undefined,
        id: 0
    }
    props.filter.filters.push(filter)
}

function addNewGroupFilter() {
    let filter: FilterGroup = {
        filters: [],
        groupOperator: FilterOperator.or,
        depth: props.filter.depth + 1,
        isGroup: true,
        id: 0
    }
    props.filter.filters.push(filter)
}

function deleteFilter(filter: Filter | FilterGroup) {
    props.manager.deleteFilter(filter.id)
}

onMounted(() => {
    if (props.filter.filters.length == 0 && props.filter.depth > 0) {
        addNewFilter()
    }
})

</script>

<template>
    <div class="filter-group">
        <table class="table table-sm">
            <tr v-for="filter, index in filters">
                <td class="align-top ps-2">
                    <div v-if="index == 0" class="m-0 p-0">Where</div>
                    <template v-else-if="index == 1">
                        <div class="dropdown-toggle p-0 hover-light ps-1" data-bs-toggle="dropdown"
                            data-bs-auto-close="true" aria-expanded="false"
                            style="width: 50px; cursor: pointer; border-radius: 3px;">
                            <span class="">{{ props.filter.groupOperator }}</span>
                        </div>
                        <ul class="dropdown-menu bg-white">
                            <li><a class="dropdown-item" href="#"
                                    @click="props.filter.groupOperator = FilterOperator.and">and</a></li>
                            <li><a class="dropdown-item" href="#"
                                    @click="props.filter.groupOperator = FilterOperator.or">or</a>
                            </li>
                        </ul>
                    </template>
                    <span v-else class="text-secondary">{{ props.filter.groupOperator }}</span>
                </td>
                <td v-if="(filter as Filter).propertyId !== undefined" class="ps-2">
                    <FilterDropdown :manager="manager" :mode="2" :parent-id="props.filter.id" :filter-id="filter.id">
                        <FilterPreview :filter="(filter as Filter)" />
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
                    <span class="base-btn" @click="deleteFilter(filter)">
                        <i class="bi bi-trash"></i>
                    </span>
                    <!-- <div class="m-0 p-0 ms-1 me-1">
                        <div class="text-secondary" data-bs-toggle="dropdown" data-bs-auto-close="true"
                            aria-expanded="false"><i class="bi bi-three-dots btn-icon"></i></div>
                        <ul class="dropdown-menu bg-white m-0 p-0">
                            <li><a class="dropdown-item" href="#" @click="deleteFilter(filter)"><i
                                        class="bi bi-trash me-1"></i>delete</a></li>
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
            <FilterDropdown :manager="props.manager" :parent-id="props.filter.id">
                <div class="add-options hover-light"><i class="bi bi-plus"></i>New Filter</div>
            </FilterDropdown>
            <div class="add-options hover-light" @click="props.manager.addNewFilterGroup(props.filter.id)"><i
                    class="bi bi-plus"></i>New Group</div>
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
}</style>