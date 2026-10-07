<script setup lang="ts">
// Non-editable property row of a tree cell: computed properties, _folders, and any type the
// scroller has no dedicated input for yet. Replaces the two identical copies of this markup
// that used to live in TreePropertyInput (readonly branch + v-else fallback).
import TreeCellFrame from './TreeCellFrame.vue'
import TagBadge from '@/components/tagtree/TagBadge.vue'
import { Property, PropertyType } from '@/data/models'
import { useDataStore } from '@/data/stores/dataStore'
import { isNumeric, isTag } from '@/utils/utils'
import { computed } from 'vue'

const data = useDataStore()

const props = defineProps<{
    property: Property
    value?: any
}>()

// Readonly tag properties still hold tag ids: they get the same badges as the editable row,
// only without the picker. Without this they fall through to the plain branch and print the
// raw array.
const tags = computed(() => isTag(props.property.type) ? (props.value ?? []) as number[] : [])
// badges carry no text separator, so the hover tooltip spells the list out; other values use
// the frame's default (the text shown)
const tagNames = computed(() => isTag(props.property.type)
    ? tags.value.map(id => data.tags[id]?.value).filter(Boolean).join(', ')
    : undefined)
const isEmpty = computed(() => {
    if (isTag(props.property.type)) return !tags.value.length
    return props.value === undefined || props.value === ''
})
</script>

<template>
    <!-- title="" on the badges: the row's own tooltip covers them, a native one would double it -->
    <TreeCellFrame :type="props.property.type" :empty="isEmpty" :tooltip="tagNames">
        <TagBadge v-if="props.property.type == PropertyType._folders && props.value !== undefined"
            :name="data.folders[props.value]?.name" :color="-1" title="" />
        <div v-else-if="isTag(props.property.type)" class="badges">
            <TagBadge v-for="id in tags" :key="id" :id="id" class="me-1" title="" />
        </div>
        <span v-else-if="props.value !== undefined && props.value !== ''" class="value"
            :class="{ num: isNumeric(props.property.type) }">{{ props.value }}</span>
    </TreeCellFrame>
</template>

<style scoped>
/* one clipped line of badges, same as the editable tag row */
.badges {
    display: flex;
    align-items: center;
    overflow: hidden;
    white-space: nowrap;
}

.value {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}
</style>
