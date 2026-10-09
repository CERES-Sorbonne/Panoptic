<script setup lang="ts">
import { Property, Sha1Scores } from '@/data/models';
import { ScrollerPileLine } from '@/components/scrollers/types';
import ImageVue from './Image.vue';
import { ImageIterator, SelectedImages } from '@/core/GroupManager';
import { useColumnStore } from '@/data/stores/columnStore';
import { ComputedRef, computed, inject } from 'vue';
import { LineHost, lineIterators, treeLinesBuiltKey } from './treeLines';

const col = useColumnStore()
const selectNamespace = inject<ComputedRef<string>>('selectNamespace', computed(() => 'global'))
const linesBuilt = inject(treeLinesBuiltKey, undefined)

const props = defineProps<{
    imageSize: number
    item: ScrollerPileLine
    parentIds: number[]
    // The tree the line is a range of (the manager's GroupResult).
    result: LineHost
    properties: Property[]
    sha1Scores: Sha1Scores
    preview?: SelectedImages
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'update', 'update:selected-image'])

// One iterator per pile on this line (its `slots` = the whole pile), made for the lines on screen
// only — see ImageLine.vue.
const images = computed<ImageIterator[]>(previous => {
    linesBuilt?.value
    return lineIterators(props.result, props.item, previous)
})

// Inner (image) width for the cell at column `i` — precomputed by the scroller so cells
// add up to exactly the line width. Falls back to the line's base image size.
function cellWidth(i: number): number {
    return props.item.cardWidths?.[i] ?? props.imageSize
}

const selected = computed(() => {
    const ns = selectNamespace.value
    col.selectionTick(ns)  // reactive dep on this namespace's selection (step 2)
    const res = {}
    const ids = col.instanceIds()
    images.value.forEach(it => {
        const id = ids[it.slot]
        res[id] = col.isSelected(it.slot, ns)
    })
    return res
})

const previews = computed(() => {
    const res = {}
    if (!props.preview) return res
    const ids = col.instanceIds()
    images.value.forEach(it => {
        const id = ids[it.slot]
        res[id] = props.preview[id]
    })
    return res
})

</script>

<template>
    <div class="d-flex flex-row">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2"
            @click="emits('scroll', parentId)" @mouseenter="emits('hover', parentId)" @mouseleave="emits('unhover')">
            <div class="image-line" :data-border-group="parentId"></div>
        </div>
        <ImageVue :image="imageIt" :groupId="item.groupId" :size="props.imageSize"
            :width="cellWidth(i)"
            :properties="props.properties" :selected="selected[col.instanceIds()[imageIt.slot]]" :selectedPreview="previews[col.instanceIds()[imageIt.slot]]"
            @update:selected="v => emits('update:selected-image', { id: col.instanceIds()[imageIt.slot], value: v })"
            v-for="imageIt, i in images" class="me-2 mb-2" />

        <!-- Reserve the space of the images missing from this (partial) line so it keeps
             the same size as a full line instead of stretching to fill the gap. -->
        <div
            v-for="n in props.item.emptyCount"
            :key="'empty-' + n"
            class="image-empty me-2 mb-2"
            :style="{ width: cellWidth(props.item.count + n - 1) + 2 + 'px', height: props.imageSize + 2 + 'px' }"
        ></div>
    </div>
</template>

<style scoped>
.image-line {
    height: 100%;
    border-left: 1px solid var(--border-color);
    padding-left: 10px;
}

.image-empty {
    visibility: hidden;
    pointer-events: none;
}

.d-flex.flex-row > :last-child {
    margin-right: 0 !important;
}
</style>