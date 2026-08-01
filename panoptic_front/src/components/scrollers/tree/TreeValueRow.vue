<script setup lang="ts">
// Non-editable property row of a tree cell: computed properties, _folders, and any type the
// scroller has no dedicated input for yet. Replaces the two identical copies of this markup
// that used to live in TreePropertyInput (readonly branch + v-else fallback).
import TreeCellFrame from './TreeCellFrame.vue'
import TagBadge from '@/components/tagtree/TagBadge.vue'
import { Property, PropertyType } from '@/data/models'
import { useDataStore } from '@/data/dataStore'

const data = useDataStore()

const props = defineProps<{
    property: Property
    value?: any
}>()
</script>

<template>
    <TreeCellFrame :type="props.property.type" :empty="props.value === undefined || props.value === ''">
        <TagBadge v-if="props.property.type == PropertyType._folders && props.value !== undefined"
            :name="data.folders[props.value]?.name" :color="-1" />
        <span v-else-if="props.value !== undefined && props.value !== ''" class="value">{{ props.value }}</span>
    </TreeCellFrame>
</template>

<style scoped>
.value {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}
</style>
