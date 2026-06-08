<script setup lang="ts">
import { computed } from 'vue'
import { TabManager } from '@/core/TabManager'
import { useDataStore } from '@/data/dataStore'
import { PropertyGroupId } from '@/data/models'
import draggableComponent from 'vuedraggable'
import PropertyGroup from '@/components/menu/PropertyGroup.vue'

const data = useDataStore()

const props = defineProps<{
    tab: TabManager
}>()

const userGroups = computed(() => data.propertyTree.filter(g => g.groupId >= 0))
const defaultGroup = computed(() => data.propertyTree.find(g => g.groupId === PropertyGroupId.DEFAULT) ?? null)
const metadataGroup = computed(() => data.propertyTree.find(g => g.groupId === PropertyGroupId.METADATA) ?? null)

function onChange() {
    data.triggerPropertyTreeChange()
}
</script>

<template>
    <draggable-component :list="userGroups" @change="onChange" :item-key="e => e.groupId">
        <template #item="{ element }">
            <div class="mb-1">
                <PropertyGroup :tab="props.tab" :node="element" :menu-open="true" />
            </div>
        </template>
    </draggable-component>
    <PropertyGroup v-if="defaultGroup" class="mb-1" :tab="props.tab" :node="defaultGroup" :menu-open="true" />
    <PropertyGroup v-if="metadataGroup" class="mb-1" :tab="props.tab" :node="metadataGroup" :menu-open="true" />
</template>
