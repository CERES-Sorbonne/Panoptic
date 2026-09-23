<script setup lang="ts">
// Thin coordinator that puts two ImageScrollers side by side and moves images between
// them via drag-and-drop. It owns the move: on a cross-scroller drag the source fires
// `instance-removed` and the target fires `instance-added`, and we splice the two arrays
// accordingly. Both scrollers share one `dragGroup` (so SortableJS treats every visible
// line across both as one drag group) but distinct selection namespaces / input keys.
//
// The `left` / `right` arrays are mutated in place (the same approach vuedraggable's
// `:list` uses), so the owner sees the move reflected in its own reactive arrays.
import { computed } from 'vue'
import ImageScroller from './ImageScroller.vue'
import { Instance, Property } from '@/data/models'

const props = withDefaults(defineProps<{
    left: Instance[]
    right: Instance[]
    properties: Property[]
    imageSize: number
    width: number
    height: number
    dragGroup?: string
    gap?: number
}>(), {
    dragGroup: 'image-move',
    gap: 6,
})

// Split the given width between the two panes (no ResizeObserver — width is the source of
// truth, like the other scrollers).
const paneWidth = computed(() => Math.max(0, Math.floor((props.width - props.gap) / 2)))

function add(target: Instance[], payload: { instance: Instance, index: number }) {
    const idx = Math.max(0, Math.min(payload.index, target.length))
    target.splice(idx, 0, payload.instance)
}

function remove(source: Instance[], payload: { instance: Instance }) {
    const i = source.findIndex(x => x.id === payload.instance.id)
    if (i >= 0) source.splice(i, 1)
}
</script>

<template>
    <div class="d-flex flex-row" :style="{ gap: props.gap + 'px', width: props.width + 'px' }">
        <ImageScroller input-key="dual-image-left" select-namespace="dual-image-left"
            :instances="props.left" :properties="props.properties" :image-size="props.imageSize"
            :width="paneWidth" :height="props.height" :drag-group="props.dragGroup"
            @instance-added="p => add(props.left, p)" @instance-removed="p => remove(props.left, p)" />

        <ImageScroller input-key="dual-image-right" select-namespace="dual-image-right"
            :instances="props.right" :properties="props.properties" :image-size="props.imageSize"
            :width="paneWidth" :height="props.height" :drag-group="props.dragGroup"
            @instance-added="p => add(props.right, p)" @instance-removed="p => remove(props.right, p)" />
    </div>
</template>
