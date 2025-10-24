<script setup lang="ts">
import { watch, computed, ref, onMounted, nextTick } from 'vue';
import Dropdown from '../dropdowns/Dropdown.vue';
import { Filter, FilterGroup, FilterManager } from '@/core/FilterManager';
import PropertyIcon from '../properties/PropertyIcon.vue';
import { PropertyID } from '@/data/models';
import { useDataStore } from '@/data/dataStore';
import FilterGroupVue from '../filter/FilterGroup.vue';
import { Dropdowns } from '@/data/dropdowns';
const data = useDataStore()

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

onMounted(async() => {
    await nextTick()
    Dropdowns.filter = dropdownElem.value
})

</script>

<template>
    <Dropdown ref="dropdownElem" placement="top-start">
        <template #button>
            <div>
                <div v-if="selectedFilterSet.length || props.manager.state.query" class="d-flex flex-row m-0 ms-1 p-1 bg hover-light bg-medium"
                    style="cursor:pointer;">
                    <div v-if="props.manager.state.query">
                        <span class="text-primary">Text Query</span>
                        <span v-if="selectedFilterSet.length" class="or-separator">|</span>
                    </div>
                    <div v-for="filter, index in selectedFilterSet">
                        <span v-if="index > 0" class="or-separator">|</span>
                        <PropertyIcon v-if="filter.propertyId == PropertyID.id" :type="data.properties[filter.propertyId].type" style="margin-right: 2px;"/>
                        <span>{{ data.properties[filter.propertyId].name }}</span>
                    </div>
                </div>
            </div>
        </template>
        <template #popup>
            <div class="m-0 p-0" ref="popupElem">
                <div class="m-1 p-1" v-if="Object.keys(data.properties).length > 0">
                    <FilterGroupVue :filter="props.manager.state.filter" :manager="props.manager" :parent="popupElem" />
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
