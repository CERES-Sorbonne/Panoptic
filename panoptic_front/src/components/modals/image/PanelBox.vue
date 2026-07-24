<script setup lang="ts">
import { useResizeObserver } from '@vueuse/core';
import { ref } from 'vue';

// Chrome around a modal panel: a small title bar with a close button, and a body
// that measures itself. Panels here (scrollers, grids) need explicit pixel sizes,
// so the measured size is handed back through the default slot.
const props = defineProps<{
    title: string
    noPadding?: boolean
}>()

const emits = defineEmits(['close'])

const bodyElem = ref(null)
const width = ref(0)
const height = ref(0)

useResizeObserver(bodyElem, (entries) => {
    const rect = entries[0].contentRect
    width.value = Math.floor(rect.width)
    height.value = Math.floor(rect.height)
})
</script>

<template>
    <div class="panel-box d-flex flex-column h-100 overflow-hidden">
        <div class="panel-header d-flex">
            <div class="flex-grow-1 text-truncate">{{ props.title }}</div>
            <slot name="actions"></slot>
            <div class="panel-close bi bi-x" @click="emits('close')"></div>
        </div>
        <div class="panel-body overflow-hidden" :class="props.noPadding ? '' : 'p-1'" ref="bodyElem">
            <slot v-if="width > 0 && height > 0" :width="width" :height="height"></slot>
        </div>
    </div>
</template>

<style scoped>
.panel-box {
    background-color: var(--island-surface);
    min-height: 0;
}

/* Same reason as ImageDisplay: the slot content is laid out from the measured body
   size, so the body has to be allowed to shrink below that content. */
.panel-body {
    flex: 1 1 0;
    min-height: 0;
    min-width: 0;
}

/* Fixed height: the actions slot can hold taller widgets (selection stamp), and a header
   that grows/shrinks with them would resize the measured body on every selection change. */
.panel-header {
    background-color: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
    color: var(--text-secondary);
    font-size: 13px;
    height: 30px;
    flex-shrink: 0;
    align-items: center;
    padding: 0 2px 0 6px;
}

.panel-close {
    padding: 0 4px;
    cursor: pointer;
    color: var(--text-secondary);
}

.panel-close:hover {
    color: var(--text-primary);
    background-color: var(--bg-tertiary);
}
</style>
