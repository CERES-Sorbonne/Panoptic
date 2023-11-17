<script setup lang="ts">
import { Filter, FilterGroup, FilterOperator } from '@/data/models';
import { reactive, watch, computed, ref } from 'vue';
import FilterGroupInput from './FilterGroupInput.vue';
import { globalStore } from '@/data/store';
import { FilterManager } from '@/utils/filter';
import * as bootstrap from 'bootstrap'
import Dropdown from '../dropdowns/Dropdown.vue';

const props = defineProps({
    // modelValue: Object as () => FilterGroup,
    manager: FilterManager
})

const emits = defineEmits(['update:modelValue'])
const popupElem = ref(null)
const dropdownElem = ref(null)

const selectedFilterSet = computed(() => {
    let list = recursiveListFilters(props.manager.filter)
    let unique = {} as any
    list.forEach(filter => unique[filter.propertyId] = filter)
    return Object.values(unique) as Array<Filter>
})

function recursiveListFilters(root: FilterGroup): Array<Filter> {
    let res = []
    for (let filter of root.filters) {
        if (filter.isGroup) {
            res.push(...recursiveListFilters(filter))
        }
        else {
            res.push(filter as Filter)
        }
    }
    return res
}

watch(() => props.manager.filter.filters, () => {
    if (props.manager.filter.filters.length == 0) {
        dropdownElem.value.hide()
    }
})

// watch(() => props.modelValue, () => {
//     emits('update:modelValue', props.modelValue)
// }, { deep: true })

</script>

<template>
    <Dropdown ref="dropdownElem">
        <template #button>
            <div>
                <div v-if="selectedFilterSet.length" class="d-flex flex-row m-0 ms-1 p-1 bg hover-light bg-medium"
                    style="cursor:pointer;">
                    <div v-for="filter, index in selectedFilterSet">
                        <span v-if="index > 0" class="or-separator">|</span>
                        <span>{{ globalStore.properties[filter.propertyId].name }}</span>
                    </div>
                </div>
            </div>
        </template>
        <template #popup>
            <div class="m-0 p-0" ref="popupElem">
                <div class="m-1 p-0" v-if="Object.keys(globalStore.properties).length > 0">
                    <FilterGroupInput :filter="props.manager.filter" :manager="props.manager" :parent="popupElem" />
                </div>
            </div>
        </template>

    </Dropdown>
</template>

<style scoped>
.or-separator {
    padding: 0 4px;
}

.bg {
    border-radius: 3px;
}
</style>
