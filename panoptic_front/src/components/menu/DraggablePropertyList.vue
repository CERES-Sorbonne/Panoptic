<script setup lang="ts">
import { TabManager } from '@/core/TabManager';
import { useDataStore } from '@/data/dataStore';
import { PropertyGroupNode } from '@/data/models';
import { defineProps, defineEmits, reactive, onMounted, ref, watch, nextTick, triggerRef } from 'vue'
import draggableComponent from 'vuedraggable';
import PropertyOptions from './PropertyOptions.vue';
import PropertyGroup from './PropertyGroup.vue';

const data = useDataStore()

const props = defineProps<{
    tab: TabManager
    menuOpen: boolean
}>()
const emits = defineEmits([])

function onChange(e) {
    data.triggerPropertyTreeChange()
}

</script>

<template>
    <draggable-component :list="data.propertyTree" @change="onChange" :item-key="e => e.groupId">
        <template #item="{ element }">
            <div v-if="element.groupId >= 0" class="mb-1">
                <PropertyGroup :tab="props.tab" :node="element" :menu-open="props.menuOpen"></PropertyGroup>
            </div>
        </template>

        <template #footer>
            <PropertyGroup class="mb-1" :tab="props.tab" :node="data.propertyTree[data.propertyTree.length-2]" :menu-open="props.menuOpen"></PropertyGroup>
            <PropertyGroup class="mb-1" :tab="props.tab" :node="data.propertyTree[data.propertyTree.length-1]" :menu-open="props.menuOpen"></PropertyGroup>
        </template>
    </draggable-component>
</template>

<style scoped></style>