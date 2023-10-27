<script setup lang="ts">
import { Filter, FilterGroup, FilterOperator, Property, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed, onMounted, watch } from 'vue';
import FilterInput from './FilterInput.vue';
import { defaultOperator } from '@/utils/filter';

const props = defineProps({
    filter: { type: Object as () => FilterGroup, required: true }
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
    props.filter.filters = props.filter.filters.filter(f => f != filter)
    if (props.filter.filters.length == 0) {
        emits('delete')
    }
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
                <td class="text-center align-top">
                    <div v-if="index == 0" style="width: 80px;" class="mt-2">Where</div>
                    <div v-else-if="index == 1">
                        <button class="border border-secondary rounded dropdown-toggle p-1 bg-white text-secondary hover-light" type="button" data-bs-toggle="dropdown"
                            data-bs-auto-close="true" aria-expanded="false" style="width: 70px;">
                            {{ props.filter.groupOperator }}
                        </button>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="#"
                                    @click="props.filter.groupOperator = FilterOperator.and">and</a></li>
                            <li><a class="dropdown-item" href="#"
                                    @click="props.filter.groupOperator = FilterOperator.or">or</a>
                            </li>
                        </ul>
                    </div>
                    <div v-else class="text-secondary mt-1">{{ props.filter.groupOperator }}</div>
                </td>
                <template v-if="(filter as Filter).propertyId !== undefined">
                    <FilterInput :filter="(filter as Filter)" />
                </template>
                <template v-else>
                    <td colspan="3" :style="subGroupStyle">
                        <div class="border rounded">
                            <FilterGroupInput :filter="(filter as FilterGroup)" @delete="deleteFilter(filter)" />
                        </div>
                    </td>
                </template>
                <td class="align-top">
                    <div>
                        <button class="btn no-border text-secondary" type="button" data-bs-toggle="dropdown"
                            data-bs-auto-close="true" aria-expanded="false"><i
                                class="bi bi-three-dots btn-icon"></i></button>
                        <ul class="dropdown-menu bg-white m-0 p-0">
                            <li><a class="dropdown-item" href="#" @click="deleteFilter(filter)"><i
                                        class="bi bi-trash me-1"></i>delete</a></li>
                        </ul>
                    </div>
                </td>
            </tr>
            <tr>
                <td colspan="2" class="text-start">
                    <span>
                        <button class="btn dropdown-toggle no-border text-secondary ms-0 ps-0" type="button" data-bs-toggle="dropdown"
                            data-bs-auto-close="true" aria-expanded="false">
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
            </tr>
        </table>

    </div>
</template>

<style scoped>
.filter-group {
    min-width: 300px;
}
</style>