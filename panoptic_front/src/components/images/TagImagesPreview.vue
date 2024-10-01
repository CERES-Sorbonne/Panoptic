<script setup lang="ts">
import { Instance, Tag } from '@/data/models';
import { defineProps, defineEmits, computed } from 'vue'
import ImagePreview from '../preview/ImagePreview.vue';
import EditableTag from '../tags/EditableTag.vue';
import { useDataStore } from '@/data/dataStore';

const data = useDataStore()

const props = defineProps<{
    tags: Tag[]
    tagToInstance: { [tId: number]: Instance[] }
}>()

const emits = defineEmits(['unselect'])

const instances = computed(() => {
    const instanceSet = new Set<number>()
    for(let tag of props.tags) {
        props.tagToInstance[tag.id].forEach(i => instanceSet.add(i.id))
    }
    return Array.from(instanceSet).map(i => data.instances[i])
})

</script>

<template>
    <div class="h-100 w-100 pt-1 d-flex flex-column overflow-hidden">
        <EditableTag v-for="tag in props.tags" :tag="tag" @unselect="e => emits('unselect', e)" />
        <div class="flex-shrink-0" style="height: 2px;"></div>
        <ImagePreview :instances="instances" />
    </div>
</template>

<style scoped></style>