<script setup lang="ts">
import { Filter, FilterGroup, FilterOperator } from '@/data/models';
import { reactive, watch, computed } from 'vue';
import FilterGroupInput from './FilterGroupInput.vue';
import { globalStore } from '@/data/store';

const props = defineProps({
    modelValue: Object as () => FilterGroup
})

const emits = defineEmits(['update:modelValue'])


const selectedFilterSet = computed(() => {
    let list = recursiveListFilters(props.modelValue)
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

watch(() => props.modelValue, () => {
    emits('update:modelValue', props.modelValue)
}, { deep: true })

</script>

<template>
    <div class="btn-group">
        <button class="btn-sm no-border rounded bg-white p-0 m-0" type="button" data-bs-toggle="dropdown"
            data-bs-auto-close="outside" aria-expanded="false">
            <div class="bg-medium d-flex flex-row rounded m-0 p-0" style="cursor:pointer;">
                <template v-for="filter, index in selectedFilterSet">
                    <span v-if="index > 0" class="label">|</span>
                    <div class="label">
                        {{ globalStore.properties[filter.propertyId].name }}
                    </div>
                </template>
            </div>
        </button>
        <div class="dropdown-menu m-0 p-0" aria-labelledby="defaultDropdown">
            <div class="m-1 p-0" v-if="Object.keys(globalStore.properties).length > 0">
                <FilterGroupInput :filter="props.modelValue" />
            </div>
        </div>
    </div>
</template>
