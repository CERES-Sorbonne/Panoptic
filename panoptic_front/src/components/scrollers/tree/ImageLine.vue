<script setup lang="ts">
import { Property } from '@/data/models';
import { ImageLine } from '@/components/scrollers/types';
import Image from './Image.vue';
import { ImageIterator, SelectedImages } from '@/core/GroupManager';
import { ComputedRef, Ref, computed, inject } from 'vue';
import { useColumnStore } from '@/data/stores/columnStore';
import { LineHost, lineIterators, treeLinesBuiltKey } from './treeLines';

const props = defineProps<{
    imageSize: number,
    item: ImageLine,
    parentIds: number[],
    // The tree the line is a range of (the manager's GroupResult).
    result: LineHost,
    properties: Property[],
    preview?: Ref<SelectedImages>,
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'update:selected-image'])

const columnStore = useColumnStore()
const selectNamespace = inject<ComputedRef<string>>('selectNamespace', computed(() => 'global'))
const linesBuilt = inject(treeLinesBuiltKey, undefined)

// The images of this line, made here for the lines on screen only (the line itself is just a
// range, see treeLines.ts). Re-checked after every rebuild of the scroller's lines, and the
// previous array kept while it still holds — so the cards only re-render when their image did.
const images = computed<ImageIterator[]>(previous => {
    linesBuilt?.value
    return lineIterators(props.result, props.item, previous)
})

// Helper function to resolve an iterator's slot to an instance ID
function getImageId(imageIt: ImageIterator): number {
    return columnStore.instanceIds()[imageIt.slot]
}

// Inner (image) width for the cell at column `i` — precomputed by the scroller so cells
// add up to exactly the line width. Falls back to the line's base image size.
function cellWidth(i: number): number {
    return props.item.cardWidths?.[i] ?? props.imageSize
}

const selected = computed(() => {
    const ns = selectNamespace.value
    columnStore.selectionTick(ns)  // reactive dep on this namespace's selection (step 2)
    const res = {}
    images.value.forEach(it => {
        const id = getImageId(it)
        if (id !== undefined) {
            res[id] = columnStore.isSelectedId(id, ns)
        }
    })
    return res
})

const preview = computed(() => {
    const res = {}
    images.value.forEach(it => {
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
            <div class="image-line" :data-border-group="parentId"></div>
        </div>
        <Image :image="imageIt" :groupId="item.groupId" :size="props.imageSize"
            :width="cellWidth(i)"
            :properties="props.properties"
            :selected="selected[getImageId(imageIt)]"
            :selectedPreview="preview[getImageId(imageIt)]"
            @update:selected="v => emits('update:selected-image', { id: getImageId(imageIt), value: v })"
            v-for="imageIt, i in images" class="me-2 mb-2"
            :noBorder="false" />

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