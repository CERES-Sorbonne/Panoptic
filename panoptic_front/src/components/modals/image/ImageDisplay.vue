<script setup lang="ts">
import Zoomable from '@/components/Zoomable.vue';
import CenteredImage from '@/components/images/CenteredImage.vue';
import { InstanceEntry } from '@/data/stores/instanceStore';
import { useResizeObserver } from '@vueuse/core';
import { computed, inject, ref, watch } from 'vue';
import wTT from '@/components/tooltips/withToolTip.vue';

// The image alone, filling whatever space the open panels leave it.
const props = defineProps<{
    instance: InstanceEntry
    canNavigate: boolean
}>()

const nextImage: () => void = inject('nextImage')
const prevImage: () => void = inject('prevImage')

const elem = ref(null)
const width = ref(0)
const height = ref(0)

// Zoom is a factor over the fitted size (1 = the whole image fits the area). The image box is
// really resized rather than CSS-scaled, so CenteredImage asks the server for a sharper file
// as the zoom grows. `offset` is the top-left corner of that box inside the area.
const ZOOM_STEP = 1.4
// Browsers stop drawing elements past some millions of pixels (Firefox blanks them around
// 17.9M), so the zoomed box stays under this size. It is the only limit on the zoom.
const MAX_BOX_SIZE = 10_000_000
const zoom = ref(1)
const offset = ref({ x: 0, y: 0 })
const dragging = ref(false)
let dragStart = { x: 0, y: 0, ox: 0, oy: 0 }

const maxZoom = computed(() => {
    const side = Math.max(width.value, height.value)
    return side ? Math.max(1, MAX_BOX_SIZE / side) : 1
})
const boxWidth = computed(() => Math.round(width.value * zoom.value))
const boxHeight = computed(() => Math.round(height.value * zoom.value))
const isZoomed = computed(() => zoom.value > 1)

useResizeObserver(elem, (entries) => {
    const rect = entries[0].contentRect
    width.value = Math.floor(rect.width)
    height.value = Math.floor(rect.height)
    setOffset(offset.value.x, offset.value.y)
})

// The box always covers the area: no panning past its edges.
function setOffset(x: number, y: number) {
    offset.value = {
        x: Math.min(0, Math.max(width.value - boxWidth.value, x)),
        y: Math.min(0, Math.max(height.value - boxHeight.value, y))
    }
}

// Zoom keeping the point (cx, cy) of the area on the same image pixel.
function zoomTo(value: number, cx = width.value / 2, cy = height.value / 2) {
    const next = Math.min(maxZoom.value, Math.max(1, value))
    const ratio = next / zoom.value
    zoom.value = next
    setOffset(cx - (cx - offset.value.x) * ratio, cy - (cy - offset.value.y) * ratio)
}

function resetZoom() {
    zoom.value = 1
    offset.value = { x: 0, y: 0 }
}

function onWheel(e: WheelEvent) {
    const rect = elem.value.getBoundingClientRect()
    // A trackpad pinch comes as a ctrl+wheel with small deltas.
    const speed = e.ctrlKey ? 0.01 : 0.0015
    zoomTo(zoom.value * Math.exp(-e.deltaY * speed), e.clientX - rect.left, e.clientY - rect.top)
}

function onPointerDown(e: PointerEvent) {
    if (e.button != 0 || !isZoomed.value) return
    dragging.value = true
    dragStart = { x: e.clientX, y: e.clientY, ox: offset.value.x, oy: offset.value.y }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
    if (!dragging.value) return
    setOffset(dragStart.ox + e.clientX - dragStart.x, dragStart.oy + e.clientY - dragStart.y)
}

function onPointerUp() {
    dragging.value = false
}

watch(() => props.instance.id, resetZoom)
</script>

<template>
    <div class="image-area position-relative" ref="elem">
        <div class="pan-layer" :class="{ zoomed: isZoomed, dragging }" v-if="width > 0 && height > 0"
            :style="{ transform: `translate(${offset.x}px, ${offset.y}px)` }" @wheel.prevent="onWheel"
            @pointerdown="onPointerDown" @pointermove="onPointerMove" @pointerup="onPointerUp"
            @pointercancel="onPointerUp" @dragstart.prevent>
            <Zoomable :image="props.instance">
                <CenteredImage :instance-id="props.instance.id" :width="boxWidth" :height="boxHeight" no-click />
            </Zoomable>
        </div>
        <template v-if="props.canNavigate">
            <div class="arrow left" @click="prevImage"><i class="bi bi-arrow-left"></i></div>
            <div class="arrow right" @click="nextImage"><i class="bi bi-arrow-right"></i></div>
        </template>
        <div class="zoom-controls d-flex align-items-center">
            <wTT message="modals.image.zoom_out_tooltip">
                <div class="zoom-btn" :class="{ disabled: zoom <= 1 }" @click="zoomTo(zoom / ZOOM_STEP)">
                    <i class="bi bi-dash-lg"></i>
                </div>
            </wTT>
            <wTT message="modals.image.zoom_reset_tooltip">
                <div class="zoom-btn zoom-value num" @click="resetZoom">{{ Math.round(zoom * 100) }}%</div>
            </wTT>
            <wTT message="modals.image.zoom_in_tooltip">
                <div class="zoom-btn" :class="{ disabled: zoom >= maxZoom }" @click="zoomTo(zoom * ZOOM_STEP)">
                    <i class="bi bi-plus-lg"></i>
                </div>
            </wTT>
        </div>
    </div>
</template>

<style scoped>
.image-area {
    background-color: var(--bg-secondary);
    overflow: hidden;
    /* The image is sized from this box's measured size, so the box must be free to shrink
       when a panel opens — with the default min-height:auto it would stay at its content
       size and the resize observer would never fire again. */
    flex: 1 1 0;
    min-height: 0;
    min-width: 0;
}

.pan-layer {
    position: absolute;
    top: 0;
    left: 0;
    user-select: none;
}

.pan-layer.zoomed {
    cursor: grab;
}

.pan-layer.dragging {
    cursor: grabbing;
}

.zoom-controls {
    position: absolute;
    bottom: 10px;
    right: 10px;
    gap: 2px;
    padding: 2px;
    border-radius: 4px;
    border: 1px solid var(--border-color);
    background-color: var(--bg-primary);
    opacity: 0.8;
}

.zoom-controls:hover {
    opacity: 1;
}

.zoom-btn {
    padding: 0 6px;
    line-height: 22px;
    border-radius: 3px;
    cursor: pointer;
    color: var(--text-secondary);
    user-select: none;
}

.zoom-btn:hover {
    background-color: var(--bg-tertiary);
    color: var(--text-primary);
}

.zoom-btn.disabled {
    opacity: 0.4;
    pointer-events: none;
}

.zoom-value {
    min-width: 48px;
    text-align: center;
    font-size: 12px;
}

.arrow {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    font-size: 22px;
    line-height: 22px;
    padding: 6px 8px;
    cursor: pointer;
    border-radius: 50%;
    color: var(--text-secondary);
    background-color: rgba(255, 255, 255, 0.7);
    opacity: 0.5;
}

.arrow:hover {
    opacity: 1;
    color: var(--text-primary);
}

.left {
    left: 10px;
}

.right {
    right: 10px;
}
</style>
