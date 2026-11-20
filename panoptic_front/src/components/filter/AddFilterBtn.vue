<script setup lang="ts">
import { FilterGroup, FilterManager } from '@/core/FilterManager';
import Dropdown from '../dropdowns/Dropdown.vue';
import PropertySelection from '../inputs/PropertySelection.vue';
import { PropertyID } from '@/data/models';
import { Dropdowns } from '@/components/dropdowns/registry';

const props = defineProps<{
    group: FilterGroup
    manager: FilterManager
}>()
const emits = defineEmits([])

function addFilter(propId: number) {
    props.manager.addNewFilter(propId, props.group.id)
    Dropdowns.filter.show()
}

</script>

<template>
    <Dropdown placement="auto" :auto-focus="false">
        <template #button>
            <slot></slot>
        </template>
        <template #popup="{ hide }">
            <PropertySelection @select="pId => { addFilter(pId); hide(); }" :ignore-ids="[PropertyID.folders]"/>
        </template>
    </Dropdown>
</template>

<style scoped></style>