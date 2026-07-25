<!--
  The graph view's chart.

  Rendered with ECharts (canvas), which owns the marks, the axes, the legend and the x zoom.
  Everything that has to know about Panoptic — the hover readout, the crosshair, and
  click/drag selection of images — is ours, driven by zrender pointer events and the
  pixel <-> data conversions the chart exposes. Nothing is injected into the chart's DOM.

  Interaction contract:
    · move        → crosshair snaps to the nearest bucket + tooltip with its images
    · click       → select that bucket's images        (shift: add, alt: remove)
    · drag        → select every bucket in the range   (shift: add, alt: remove)
    · wheel       → zoom the x axis (y rescales to what is visible)
    · legend      → show/hide a series; hovering one fades the others
-->
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'

import { useColumnStore } from '@/data/columnStore'
import { useInstanceStore } from '@/data/instanceStore'
import { GraphOptions } from '@/data/models'
import { ChartModel, thumbnailsAvailable } from './chartModel'
import { buildChartOption, chartLayout } from './chartOptions'

const columnStore = useColumnStore()
const instanceStore = useInstanceStore()

const props = defineProps<{
    model: ChartModel
    options: GraphOptions
    /** Selection namespace of the collection being charted. */
    namespace: string
    height: number
}>()

const emits = defineEmits<{
    (e: 'select', payload: { slots: number[]; mode: 'replace' | 'add' | 'remove' }): void
    (e: 'hover', bucketIndex: number | null): void
}>()

// ── Layout ───────────────────────────────────────────────────────────────────
// The same geometry the option is built with, so the overlays (crosshair, drag band) and the
// pointer hit-testing land on the plot rectangle exactly.
const layout = computed(() => chartLayout(props.model))

const showThumbnails = computed(() =>
    props.options.showThumbnails && thumbnailsAvailable(props.model, props.options))

// ── Selection state ──────────────────────────────────────────────────────────
// selectedCount() scans a Uint8Array mask; the per-cell pass below only runs when something
// is actually selected, so the common (nothing selected) case costs one scan.
const selectedTotal = computed(() => {
    columnStore.selectionTick(props.namespace)
    return columnStore.selectedCount(props.namespace)
})

const selectedCells = computed<boolean[][]>(() => {
    const empty = props.model.series.map(s => s.cells.map(() => false))
    if (selectedTotal.value === 0) return empty
    const ns = props.namespace
    return props.model.series.map(s => s.cells.map(cell => {
        if (!cell) return false
        for (const slot of cell.slots) if (columnStore.isSelected(slot, ns)) return true
        return false
    }))
})

// ── Legend state ─────────────────────────────────────────────────────────────
const hiddenSeries = ref<Record<string, boolean>>({})
function isVisible(name: string) { return !hiddenSeries.value[name] }
function onLegendChange(params: any) {
    const selected = params?.selected ?? {}
    const next: Record<string, boolean> = {}
    for (const name of Object.keys(selected)) if (!selected[name]) next[name] = true
    hiddenSeries.value = next
}

// ── Option ───────────────────────────────────────────────────────────────────
// Built by chartOptions.ts, which stays a pure function of the model + display options +
// the reactive bits below, so the same option can be rendered outside the app.
const option = computed(() => buildChartOption(props.model, props.options, {
    selected: selectedCells.value,
    anySelected: selectedTotal.value > 0,
    isVisible,
    imageUrl: id => {
        const url = instanceStore.instanceData[id]?.imageUrl
        return url ? `${url}?size=128` : undefined
    },
    thumbnails: showThumbnails.value,
}))

// ── Pointer geometry ─────────────────────────────────────────────────────────
const chartRef = ref<any>(null)
/**
 * The chart's coordinate/geometry API. vue-echarts re-exposes the methods we need
 * (getWidth/getHeight/convertToPixel/…) on the component itself, so we go through those rather
 * than the wrapped instance — the wrapper's shape is its own business, the methods are its API.
 * Returns null until it is mounted.
 */
function api(): any {
    const component = chartRef.value
    return component && typeof component.getWidth === 'function' ? component : null
}

/**
 * Pixel x of every bucket, cached: recomputing it per mousemove would mean one coordinate
 * conversion per bucket per event. Invalidated whenever the chart re-renders (zoom, resize,
 * new data), which is exactly when the mapping can change. Buckets outside the zoom window
 * convert to a non-finite value and are skipped by the hit-testing below.
 */
let pixels: number[] | null = null

function bucketPixels(): number[] | null {
    if (pixels) return pixels
    const instance = api()
    if (!instance) return null
    const rect = plotRect()
    const { buckets, xKind } = props.model
    const out = new Array<number>(buckets.length)
    for (let bi = 0; bi < buckets.length; bi++) {
        const coord = xKind === 'category' ? buckets[bi].label : buckets[bi].x
        const px = instance.convertToPixel({ xAxisIndex: 0 }, coord as any)
        // Outside the zoom window the conversion may clamp to the plot edge instead of
        // returning NaN, which would make an off-screen bucket the nearest one to a click at
        // the edge. Anything landing outside the plot is not addressable, whatever it returned.
        const usable = typeof px === 'number' && Number.isFinite(px)
            && (!rect || (px >= rect.x0 - 1 && px <= rect.x1 + 1))
        out[bi] = usable ? px : NaN
    }
    pixels = out
    return pixels
}

function plotRect() {
    const instance = api()
    if (!instance) return null
    return {
        x0: layout.value.left,
        x1: instance.getWidth() - layout.value.right,
        y0: layout.value.top,
        y1: instance.getHeight() - layout.value.bottom,
    }
}

function insidePlot(x: number, y: number) {
    const rect = plotRect()
    return !!rect && x >= rect.x0 && x <= rect.x1 && y >= rect.y0 && y <= rect.y1
}

function nearestBucket(pixelX: number): number | null {
    const px = bucketPixels()
    if (!px) return null
    let best = -1
    let bestDist = Infinity
    for (let bi = 0; bi < px.length; bi++) {
        if (!Number.isFinite(px[bi])) continue
        const dist = Math.abs(px[bi] - pixelX)
        if (dist < bestDist) { bestDist = dist; best = bi }
    }
    return best < 0 ? null : best
}

function bucketsBetween(fromPx: number, toPx: number): number[] {
    const px = bucketPixels()
    if (!px) return []
    const min = Math.min(fromPx, toPx)
    const max = Math.max(fromPx, toPx)
    const out: number[] = []
    for (let bi = 0; bi < px.length; bi++) {
        if (Number.isFinite(px[bi]) && px[bi] >= min && px[bi] <= max) out.push(bi)
    }
    return out
}

// ── Hover ────────────────────────────────────────────────────────────────────
const hoverIndex = ref<number | null>(null)
const pointer = ref({ x: 0, y: 0 })

const crosshairX = computed(() => {
    if (hoverIndex.value === null) return null
    const px = bucketPixels()
    const x = px?.[hoverIndex.value]
    return x !== undefined && Number.isFinite(x) ? x : null
})

const tooltipStyle = computed(() => {
    const instance = api()
    const width = instance?.getWidth() ?? 0
    const flip = pointer.value.x + 268 > width
    const top = Math.min(Math.max(pointer.value.y - 40, 4), Math.max(4, (instance?.getHeight() ?? 0) - 210))
    return {
        left: flip ? undefined : pointer.value.x + 16 + 'px',
        right: flip ? width - pointer.value.x + 16 + 'px' : undefined,
        top: top + 'px',
    }
})

const hoverBucket = computed(() => hoverIndex.value === null ? null : props.model.buckets[hoverIndex.value])

const hoverRows = computed(() => {
    if (hoverIndex.value === null) return []
    const bi = hoverIndex.value
    return props.model.series
        .filter(s => isVisible(s.name))
        .map(s => ({ name: s.name, color: s.color, count: s.cells[bi]?.count ?? 0 }))
        .filter(row => row.count > 0)
})

function setHover(index: number | null) {
    if (hoverIndex.value === index) return
    hoverIndex.value = index
    emits('hover', index)
}

// ── Drag selection ───────────────────────────────────────────────────────────
const dragFrom = ref<number | null>(null)
const dragTo = ref<number | null>(null)
const overPlot = ref(false)

const dragBand = computed(() => {
    if (dragFrom.value === null || dragTo.value === null) return null
    const rect = plotRect()
    if (!rect) return null
    const from = Math.max(Math.min(dragFrom.value, dragTo.value), rect.x0)
    const to = Math.min(Math.max(dragFrom.value, dragTo.value), rect.x1)
    if (to - from < 2) return null
    return { left: from + 'px', width: to - from + 'px', top: rect.y0 + 'px', height: rect.y1 - rect.y0 + 'px' }
})

function modeFrom(event: MouseEvent | undefined): 'replace' | 'add' | 'remove' {
    if (event?.altKey) return 'remove'
    if (event?.shiftKey || event?.ctrlKey || event?.metaKey) return 'add'
    return 'replace'
}

function onDown(e: any) {
    if (!insidePlot(e.offsetX, e.offsetY)) return
    dragFrom.value = e.offsetX
    dragTo.value = e.offsetX
    window.addEventListener('pointerup', onWindowUp)
}

function onMove(e: any) {
    const inside = insidePlot(e.offsetX, e.offsetY)
    overPlot.value = inside
    if (dragFrom.value !== null) dragTo.value = e.offsetX
    if (!inside) { setHover(null); return }
    pointer.value = { x: e.offsetX, y: e.offsetY }
    setHover(nearestBucket(e.offsetX))
}

function onUp(e: any) {
    finishDrag(e.offsetX, e.event as MouseEvent)
}

function onWindowUp(event: PointerEvent) {
    // Released outside the canvas: finish with the last position we saw.
    if (dragFrom.value !== null) finishDrag(dragTo.value ?? dragFrom.value, event as unknown as MouseEvent)
}

function finishDrag(endPx: number | null, event: MouseEvent | undefined) {
    window.removeEventListener('pointerup', onWindowUp)
    const start = dragFrom.value
    dragFrom.value = null
    dragTo.value = null
    if (start === null || endPx === null) return

    // Under a few pixels of travel it was a click, not a drag: one bucket, not a range.
    let indices: number[]
    if (Math.abs(endPx - start) < 4) {
        const bucket = nearestBucket(start)
        indices = bucket === null ? [] : [bucket]
    } else {
        indices = bucketsBetween(start, endPx)
    }
    if (!indices.length) return

    const slots: number[] = []
    for (const s of props.model.series) {
        if (!isVisible(s.name)) continue
        for (const bi of indices) {
            const cell = s.cells[bi]
            if (!cell) continue
            for (const slot of cell.slots) slots.push(slot)
        }
    }
    emits('select', { slots, mode: modeFrom(event) })
}

function onGlobalOut() {
    overPlot.value = false
    setHover(null)
}

// ── Cache invalidation ───────────────────────────────────────────────────────
function invalidatePixels() { pixels = null }

watch(() => [props.model, props.options.chartType, props.options.stacked, props.height], () => {
    invalidatePixels()
    // A hovered index describes the previous buckets; keeping it would point the crosshair and
    // the tooltip at whatever now sits at that position.
    setHover(null)
})

onUnmounted(() => window.removeEventListener('pointerup', onWindowUp))
</script>

<template>
    <div class="chart-host" :class="{ picking: overPlot }" :style="{ height: props.height + 'px' }">
        <VChart ref="chartRef" class="chart-canvas" :option="option" :update-options="{ replaceMerge: ['series'] }" autoresize
            @legendselectchanged="onLegendChange" @datazoom="invalidatePixels" @rendered="invalidatePixels"
            @zr:mousedown="onDown" @zr:mousemove="onMove" @zr:mouseup="onUp" @zr:globalout="onGlobalOut" />

        <!-- Crosshair: the reader aims at a bucket, never at a 2px mark. -->
        <div v-if="crosshairX !== null && !dragBand" class="crosshair"
            :style="{ left: crosshairX + 'px', top: layout.top + 'px', height: (props.height - layout.top - layout.bottom) + 'px' }">
        </div>

        <div v-if="dragBand" class="drag-band" :style="dragBand"></div>

        <div v-if="hoverBucket && !dragBand" class="tooltip-layer" :style="tooltipStyle">
            <slot name="tooltip" :bucket="hoverBucket" :rows="hoverRows" :index="hoverIndex"></slot>
        </div>
    </div>
</template>

<style scoped>
.chart-host {
    position: relative;
    width: 100%;
}

.chart-canvas {
    width: 100%;
    height: 100%;
}

.picking :deep(canvas) {
    cursor: crosshair;
}

.crosshair {
    position: absolute;
    width: 1px;
    background: var(--border-solid);
    pointer-events: none;
}

.drag-band {
    position: absolute;
    background: rgba(22, 120, 194, 0.12);
    border-left: 1px solid rgba(22, 120, 194, 0.55);
    border-right: 1px solid rgba(22, 120, 194, 0.55);
    pointer-events: none;
}

.tooltip-layer {
    position: absolute;
    z-index: 20;
    pointer-events: none;
}
</style>
