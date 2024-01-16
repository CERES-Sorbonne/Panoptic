<script setup lang="ts">
import { watch, computed, ref } from 'vue';
import FilterGroupInput from './FilterGroupInput.vue';
import { useProjectStore } from '@/data/projectStore'
import Dropdown from '../dropdowns/Dropdown.vue';
import { Filter, FilterGroup, FilterManager } from '@/core/FilterManager';
import PropertyIcon from '../properties/PropertyIcon.vue';
import { PropertyID } from '@/data/models';
const store = useProjectStore()
const props = defineProps({
    manager: FilterManager
})

const emits = defineEmits(['update:modelValue'])
const popupElem = ref(null)
const dropdownElem = ref(null)

const selectedFilterSet = computed(() => {
    let list = recursiveListFilters(props.manager.state.filter)
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

watch(() => props.manager.state.filter.filters, () => {
    if (props.manager.state.filter.filters.length == 0) {
        dropdownElem.value.hide()
    }
})

</script>

<template>
    <Dropdown ref="dropdownElem">
        <template #button>
            <div>
                <div v-if="selectedFilterSet.length" class="d-flex flex-row m-0 ms-1 p-1 bg hover-light bg-medium"
                    style="cursor:pointer;">
                    <div v-for="filter, index in selectedFilterSet">
                        <span v-if="index > 0" class="or-separator">|</span>
                        <PropertyIcon v-if="filter.propertyId == PropertyID.id" :type="store.data.properties[filter.propertyId].type" style="margin-right: 2px;"/>
                        <span>{{ store.data.properties[filter.propertyId].name }}</span>
                    </div>
                </div>
            </div>
        </template>
        <template #popup>
            <div class="m-0 p-0" ref="popupElem">
                <div class="m-1 p-0" v-if="Object.keys(store.data.properties).length > 0">
                    <FilterGroupInput :filter="props.manager.state.filter" :manager="props.manager" :parent="popupElem" />
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
