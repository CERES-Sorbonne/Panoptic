<script setup lang="ts">
import { ref, onBeforeUnmount, watch } from 'vue'

// Sidebar + main content separated by a gutter. The gutter doubles as a
// horizontal resize zone when `resizable` is set, and the sidebar can be
// collapsed away entirely. Pure layout — slots + layout props only.
interface Props {
    sidebarWidth?: number
    gap?: number
    resizable?: boolean
    minWidth?: number
    maxWidth?: number
    collapsed?: boolean
}

const props = withDefaults(defineProps<Props>(), {
    sidebarWidth: 250,
    gap: 6,
    resizable: false,
    minWidth: 180,
    maxWidth: 600,
    collapsed: false
})

const emit = defineEmits<{
    'update:sidebarWidth': [width: number]
}>()

const width = ref(clamp(props.sidebarWidth))
const isResizing = ref(false)
let startX = 0
let startWidth = 0

// Watch for prop changes and update internal width
watch(() => props.sidebarWidth, (newWidth) => {
    if (!isResizing.value) {
        width.value = clamp(newWidth)
    }
})

function clamp(value: number) {
    return Math.min(props.maxWidth, Math.max(props.minWidth, value))
}

function startResize(e: PointerEvent) {
    isResizing.value = true
    startX = e.clientX
    startWidth = width.value
    window.addEventListener('pointermove', onResize)
    window.addEventListener('pointerup', stopResize)
}

function onResize(e: PointerEvent) {
    width.value = clamp(startWidth + (e.clientX - startX))
}

function stopResize() {
    isResizing.value = false
    window.removeEventListener('pointermove', onResize)
    window.removeEventListener('pointerup', stopResize)
    emit('update:sidebarWidth', width.value)
}

onBeforeUnmount(stopResize)
</script>

<template>
    <div class="sidebar-layout" :class="{ resizing: isResizing }">
        <template v-if="!collapsed">
            <div class="sidebar-pane" :style="{ width: width + 'px' }">
                <slot name="sidebar"></slot>
            </div>
            <div
                class="gutter"
                :class="{ resizable, active: isResizing }"
                :style="{ width: gap + 'px' }"
                @pointerdown="resizable && startResize($event)"
            ></div>
        </template>
        <div class="main-pane">
            <slot name="main"></slot>
        </div>
    </div>
</template>

<style scoped>
.sidebar-layout {
    display: flex;
    flex: 1;
    min-width: 0;
    min-height: 0;
}

.sidebar-layout.resizing {
    user-select: none;
    cursor: col-resize;
}

.sidebar-pane {
    display: flex;
    flex-shrink: 0;
    min-height: 0;
    overflow: hidden;
}

.main-pane {
    display: flex;
    flex: 1;
    min-width: 0;
    min-height: 0;
}

.gutter {
    position: relative;
    flex-shrink: 0;
}

.gutter.resizable {
    cursor: col-resize;
}

/* Widen the pointer hit area beyond the visible gutter */
.gutter.resizable::before {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: -3px;
    right: -3px;
}

/* Highlight line shown on hover / while dragging */
.gutter.resizable::after {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: 50%;
    width: 2px;
    transform: translateX(-50%);
    border-radius: 1px;
    background-color: transparent;
    transition: background-color var(--transition-fast);
}

.gutter.resizable:hover::after,
.gutter.resizable.active::after {
    background-color: var(--primary);
}
</style>
