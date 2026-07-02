<script setup lang="ts">
import { ScrollerLine, Property, ImageLine } from '@/data/models';
import Image from './Image.vue';
import { GroupIndex, SelectedImages } from '@/core/GroupManager';
import { ComputedRef, Ref, computed, inject, onMounted } from 'vue';
import { useColumnStore } from '@/data/columnStore'; // <-- Import columnStore

const props = defineProps<{
    imageSize: number,
    inputIndex: number,
    item: ImageLine,
    parentIds: number[],
    hoverBorder: number,
    index: GroupIndex,
    properties: Property[],
    preview?: Ref<SelectedImages>,
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'update:selected-image'])

const columnStore = useColumnStore() // <-- Initialize columnStore
const selectNamespace = inject<ComputedRef<string>>('selectNamespace', computed(() => 'global'))

// Helper function to resolve an iterator's slot to an instance ID
function getImageId(imageIt: any): number {
    return columnStore.instanceIds()[imageIt.slot]
}

const selected = computed(() => {
    const ns = selectNamespace.value
    columnStore.selectionTick(ns)  // reactive dep on this namespace's selection (step 2)
    const res = {}
    props.item.data.forEach(it => {
        const id = getImageId(it)
        if (id !== undefined) {
            res[id] = columnStore.isSelectedId(id, ns)
        }
    })
    return res
})

const preview = computed(() => {
    const res = {}
    props.item.data.forEach(it => {
        const id = getImageId(it)
        if (id !== undefined) {
            res[id] = props.preview?.value[id]
        }
    })
    return res
})
</script>

<template>
    <div class="d-flex flex-row">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2"
            @click="emits('scroll', parentId)" @mouseenter="emits('hover', parentId)" @mouseleave="emits('unhover')">
            <div class="image-line" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <Image :image="imageIt" :index="props.inputIndex + i" :groupId="item.groupId" :size="props.imageSize"
            :properties="props.properties" 
            :selected="selected[getImageId(imageIt)]" 
            :selectedPreview="preview[getImageId(imageIt)]"
            @update:selected="v => emits('update:selected-image', { id: getImageId(imageIt), value: v })"
            v-for="imageIt, i in props.item.data" class="me-2 mb-2" />

    </div>
</template>

<style scoped>
.image-line {
    height: 100%;
    border-left: 1px solid var(--border-color);
    padding-left: 10px;
}

.active {
    border-left: 1px solid blue;
}
</style>