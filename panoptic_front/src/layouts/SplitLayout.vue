<script setup lang="ts">
import { ref, computed, onBeforeUnmount, watch } from 'vue'

// Two-pane split where the primary pane grows and the secondary pane keeps a
// (draggable) fixed size. Either pane can be hidden, in which case the other
// fills the whole area. Works as a column (default) or row split.
// Pure layout — slots + layout props only.
interface Props {
    direction?: 'row' | 'column'
    secondarySize?: number
    secondaryRatio?: number
    gap?: number
    resizable?: boolean
    minPrimary?: number
    minSecondary?: number
    hidePrimary?: boolean
    hideSecondary?: boolean
}

const props = withDefaults(defineProps<Props>(), {
    direction: 'column',
    secondarySize: 200,
    secondaryRatio: undefined,
    gap: 6,
    resizable: false,
    minPrimary: 80,
    minSecondary: 80,
    hidePrimary: false,
    hideSecondary: false
})

const root = ref<HTMLElement>()
const size = ref(props.secondarySize)
const ratio = ref(props.secondaryRatio ?? 0.5)
const isResizing = ref(false)
let startPos = 0
let startSize = 0
let startRatio = 0

const emit = defineEmits<{
    'update:secondarySize': [size: number]
    'update:secondaryRatio': [ratio: number]
}>()

// Watch for prop changes and update internal size/ratio
watch(() => props.secondarySize, (newSize) => {
    if (!isResizing.value) {
        size.value = newSize
    }
})

watch(() => props.secondaryRatio, (newRatio) => {
    if (!isResizing.value && newRatio !== undefined) {
        ratio.value = newRatio
    }
})

const isColumn = computed(() => props.direction === 'column')
const useRatio = computed(() => (props.secondaryRatio !== undefined || props.secondaryRatio === 0))
// The divider is shown as long as the primary pane is visible — even when the
// secondary pane is hidden — so the primary always gets a visible trailing
// edge (margin-like gap + hover highlight). Dragging only makes sense when
// both panes are actually present.
const showHandle = computed(() => !props.hidePrimary)
const canDrag = computed(() => props.resizable && !props.hidePrimary && !props.hideSecondary)

const secondaryStyle = computed(() => {
    if (isColumn.value && useRatio.value) {
        return {} // height set via inline style on the element itself
    }
    if (useRatio.value) {
        return {} // width set via inline style on the element itself
    }
    if (isColumn.value) {
        return { height: size.value + 'px' }
    }
    return { width: size.value + 'px' }
})

const handleStyle = computed(() =>
    isColumn.value ? { height: props.gap + 'px' } : { width: props.gap + 'px' }
)

function startResize(e: PointerEvent) {
    isResizing.value = true
    startPos = isColumn.value ? e.clientY : e.clientX
    if (useRatio.value) {
        startRatio = ratio.value
    } else {
        startSize = size.value
    }
    window.addEventListener('pointermove', onResize)
    window.addEventListener('pointerup', stopResize)
}

function onResize(e: PointerEvent) {
    const pos = isColumn.value ? e.clientY : e.clientX
    if (useRatio.value) {
        const containerSize = (isColumn.value ? root.value?.clientHeight : root.value?.clientWidth) ?? 0
        if (containerSize === 0) return
        const delta = (startPos - pos) / containerSize
        const next = startRatio + delta
        // Clamp: primary >= minPrimary, secondary >= minSecondary
        const minRatio = (props.minSecondary ?? 80) / containerSize
        const maxRatio = 1 - (props.minPrimary ?? 80) / containerSize
        ratio.value = Math.min(maxRatio, Math.max(minRatio, next))
    } else {
        const next = startSize + (startPos - pos)
        const total = (isColumn.value ? root.value?.clientHeight : root.value?.clientWidth) ?? 0
        const max = Math.max(props.minSecondary, total - props.gap - props.minPrimary)
        size.value = Math.min(max, Math.max(props.minSecondary, next))
    }
}

function stopResize() {
    isResizing.value = false
    window.removeEventListener('pointermove', onResize)
    window.removeEventListener('pointerup', stopResize)
    if (useRatio.value) {
        emit('update:secondaryRatio', ratio.value)
    } else {
        emit('update:secondarySize', size.value)
    }
}

onBeforeUnmount(stopResize)
</script>

<template>
    <div ref="root" class="split" :class="['split-' + direction, { resizing: isResizing }]" :style="{ gap: showHandle ? '0' : gap + 'px' }">
        <div v-if="!hidePrimary" class="split-primary">
            <slot name="primary"></slot>
        </div>

        <div
            v-if="showHandle"
            class="split-handle"
            :class="{ resizable, draggable: canDrag, active: isResizing }"
            :style="handleStyle"
            @pointerdown="canDrag && startResize($event)"
        >
            <div v-if="$slots.handle" class="split-handle-widget">
                <slot name="handle"></slot>
            </div>
        </div>

        <div
            v-if="!hideSecondary"
            class="split-secondary"
            :class="{ grow: hidePrimary }"
            :style="hidePrimary ? undefined : { ...secondaryStyle, ...(useRatio ? (isColumn ? { height: ratio * 100 + '%' } : { width: ratio * 100 + '%' }) : {}) }"
        >
            <slot name="secondary"></slot>
        </div>
    </div>
</template>

<style scoped>
.split {
    display: flex;
    flex: 1;
    width: 100%;
    min-width: 0;
    min-height: 0;
}

.split.split-column {
    flex-direction: column;
}

.split.split-row {
    flex-direction: row;
}

.split.resizing {
    user-select: none;
}

.split-primary {
    display: flex;
    flex: 1;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
}

.split-secondary {
    display: flex;
    flex-shrink: 0;
    overflow: hidden;
}

.split-secondary.split-row-ratio {
    flex-shrink: 0;
}

.split-secondary.split-column-ratio {
    flex-basis: auto;
}

.split-secondary.grow {
    flex: 1;
    min-width: 0;
    min-height: 0;
}

/* In a row split the panes share the cross (height) axis. Relying on
   align-items:stretch alone leaves percentage-height descendants without a
   definite height to resolve against, so pin the panes to the full height. */
.split.split-row > .split-primary,
.split.split-row > .split-secondary {
    height: 100%;
}

.split-handle {
    position: relative;
    flex-shrink: 0;
    /* Stay exactly `gap` wide — never let the floating widget's min-content
       (default min-width:auto on flex items) stretch the gutter. */
    min-width: 0;
    min-height: 0;
}

/* Optional widget (e.g. a link toggle) floating centered on the divider.
   Overflows the thin handle so the gutter itself can stay tiny. */
.split-handle-widget {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 2;
}

.split.split-column > .split-handle.draggable {
    cursor: row-resize;
}

.split.split-row > .split-handle.draggable {
    cursor: col-resize;
}

/* Widen the pointer/hover hit area beyond the visible gutter */
.split.split-column > .split-handle.draggable::before {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    top: -3px;
    bottom: -3px;
}

.split.split-row > .split-handle.draggable::before {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: -3px;
    right: -3px;
}

/* Highlight line shown on hover / while dragging */
.split.split-column > .split-handle.draggable::after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    top: 50%;
    height: 2px;
    transform: translateY(-50%);
    border-radius: 1px;
    background-color: var(--border-color);
    transition: background-color var(--transition-fast);
}

.split.split-row > .split-handle.draggable::after {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: 50%;
    width: 2px;
    transform: translateX(-50%);
    border-radius: 1px;
    background-color: var(--border-color);
    transition: background-color var(--transition-fast);
}

.split.split-column > .split-handle.draggable:hover::after,
.split.split-column > .split-handle.draggable.active::after,
.split.split-row > .split-handle.draggable:hover::after,
.split.split-row > .split-handle.draggable.active::after {
    background-color: var(--primary);
}
</style>
