<script setup lang="ts">
import { FilterGroup, FilterManager } from '@/core/FilterManager';
import { defineProps, defineEmits } from 'vue'
import Dropdown from '../dropdowns/Dropdown.vue';
import PropertySelection from '../inputs/PropertySelection.vue';
import { PropertyID } from '@/data/models';
import { Dropdowns } from '@/data/dropdowns';

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
    <Dropdown placement="auto">
        <template #button>
            <slot></slot>
        </template>
        <template #popup="{ hide }">
            <div style="max-height: 500px; overflow: auto;">
                <PropertySelection @select="pId => { addFilter(pId); hide(); }" :ignore-ids="[PropertyID.folders]"/>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped></style>