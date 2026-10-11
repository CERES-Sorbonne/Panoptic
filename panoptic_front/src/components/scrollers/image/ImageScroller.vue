<script setup lang="ts">
// A groupless image scroller. Derived from tree/TreeScroller.vue but it takes a plain
// Instance[] instead of a GroupManager and renders a flat, virtualized wall of images.
//
// Drag-and-drop: each visible line wraps its cells in a <draggable-component>. Every line
// (in this scroller AND any other ImageScroller given the same `dragGroup`) shares one
// SortableJS group, so an image can be dragged out of any visible line and dropped into
// any other — including a line in the other scroller. On a drop we don't mutate our own
// list; we emit what changed and let the owning parent update the source/target arrays,
// then recompute the lines. The list stays virtualized (it can be huge).
import { ref, nextTick, onMounted, onUnmounted, watch, computed, shallowRef, provide } from 'vue';
import ImageCell from './ImageCell.vue';
import draggableComponent from 'vuedraggable';
import { Property, PropertyMode, ModalId, Instance } from '@/data/models';
import { usePanopticStore } from '@/data/stores/panopticStore';
import { useColumnStore } from '@/data/stores/columnStore';
import InstanceData from '@/components/data/InstanceData.vue';
import { keyState } from '@/data/composables/keyState';
import VirtualScroller from '@/components/scrollers/virtual/VirtualScroller.vue';
import { ScrollLayout, lineKey } from '@/components/scrollers/virtual/scrollLayout';
import type { LayoutSource, LineRef } from '@/components/scrollers/virtual/scrollLayout';
import type { ViewRange } from '@/components/scrollers/virtual/virtualView';

const panoptic = usePanopticStore()
const columnStore = useColumnStore()

const props = defineProps<{
    instances: Instance[],
    imageSize: number,
    height: number,
    width: number,
    properties: Property[],
    inputKey: string,
    // Shared vuedraggable group name. Two ImageScrollers with the same value can exchange
    // images. Left undefined => drag disabled (nothing to move between).
    dragGroup?: string,
    // Opt out of drag-and-drop entirely. `dragGroup` alone already disables *dropping*, but
    // every line still instantiates a SortableJS component; consumers that will never move
    // images (similarity results, any read-only list) set this to skip that machinery and
    // render plain rows instead.
    noDrag?: boolean,
    // ColumnStore selection namespace so two scrollers can select independently.
    selectNamespace?: string,
    hideIfModal?: boolean,
    // Optional per-instance score badge, keyed by instance id.
    scores?: Record<number, number>,
    // Instance ids to highlight as the target of a pending action (paint preview).
    preview?: Record<number, boolean>,
    // Deduplicated lists: maps a displayed instance id to every instance id it stands for
    // (e.g. all instances sharing a sha1). Drives the count badge, and makes selecting a
    // cell select the whole pile. Absent => each cell is exactly one instance.
    piles?: Record<number, number[]>,
    // A cell's image was clicked. Declared as a prop (not an emit) so the scroller can tell
    // whether the parent handles `@open`; without a handler it opens the image modal itself.
    onOpen?: (instance: Instance) => void,
}>()

const emit = defineEmits<{
    // The moved Instance object is passed so the receiving parent can insert it directly.
    (e: 'instance-added', payload: { instance: Instance, index: number }): void
    (e: 'instance-removed', payload: { instance: Instance }): void
}>()

// A click on a cell's image: the parent's `@open` handler when given, otherwise the image modal.
// A flat list has no tree position, so the modal gets a bare slot (no prev/next arrows).
function openInstance(instance: Instance) {
    if (props.onOpen) return props.onOpen(instance)
    const slot = columnStore.slotMap.get(instance.id)
    if (slot === undefined) return
    panoptic.showModal(ModalId.IMAGE, { slot })
}

// Drag is live only when a group to exchange with was named AND the consumer didn't opt out.
const dragEnabled = computed(() => !!props.dragGroup && !props.noDrag)

// The line model handed to a row: the instances of one line. Made only for the lines on screen
// (lineItem); the list itself is a single node of the scroller's layout, with one body line per
// `perLine` instances.
interface ImgLine {
    id: string
    type: 'images'
    data: Instance[]
    startIndex: number
    depth: number
    imageSize: number
    emptyCount: number
    cardWidths: number[]
    size: number
}

provide('inputKey', props.inputKey)
const selectNs = computed(() => props.selectNamespace ?? 'global')
provide('selectNamespace', selectNs)

const GAP = 8 // must match the "me-2" margin applied to cells
const BORDER = 2 // ImageCell's 1px border on each side, added on top of its width style
const WIDTH_OFFSET = 32 // trim off the width prop (vertical scrollbar + a little breathing room)

const contentWidth = computed(() => Math.max(0, props.width - WIDTH_OFFSET))

const visiblePropertiesNb = computed(() => props.properties.length)

// Row height depends on the actual rendered image size of that row.
function imageLineSizeFor(imgSize: number) {
    let nb = visiblePropertiesNb.value
    let offset = 0
    if (nb > 0) offset += 28
    if (nb > 1) offset += (nb - 1) * 27
    return imgSize + offset + 10
}

const hideFromModal = computed(() => props.hideIfModal && (panoptic.openModalId == ModalId.IMAGE || panoptic.openModalId == ModalId.TAG))
provide('hideImg', hideFromModal)

// Per-cell widths that exactly fill a line (identical logic to TreeScroller): flooring the
// cell size leaves up to (itemsPerLine - 1) leftover px, handed out 1px at a time to the
// leading columns so grid columns stay aligned line-to-line.
function fillWidths(lineWidth: number, itemsPerLine: number): { lineImgSize: number, cardWidths: number[] } {
    const cardArea = lineWidth - GAP * (itemsPerLine - 1)
    const baseOuter = Math.floor(cardArea / itemsPerLine)
    const extraCount = cardArea - baseOuter * itemsPerLine
    const lineImgSize = Math.max(1, baseOuter - BORDER)
    const cardWidths: number[] = []
    for (let c = 0; c < itemsPerLine; c++) cardWidths.push(lineImgSize + (c < extraCount ? 1 : 0))
    return { lineImgSize, cardWidths }
}

// ── Layout ────────────────────────────────────────────────────────────────────
// What every line shares; set by computeLines.
let geo = { perLine: 1, lineImgSize: 1, cardWidths: [] as number[], size: 1 }
// The instances the layout was last read with (the parent mutates its array in place on a move).
let lineCount = 0

const source: LayoutSource = {
    root: () => 0,
    childCount: () => 0,
    child: () => 0,
    isOpen: () => true,
    headerSize: () => 0,
    bodyLines: () => lineCount,
    lineEstimate: () => geo.size,
    lineType: () => 'images',
}
const layout = new ScrollLayout(source)
const vs = ref<InstanceType<typeof VirtualScroller>>()

// Below the images, when drops are allowed and they do not fill the pane: an empty but droppable
// filler covering the leftover height. Without it an empty pane has no draggable target and a
// near-empty one only accepts drops on its few cells.
const filler = shallowRef(0)
const fillerList: Instance[] = []

// Two lines are interchangeable when rendering them produces the same DOM. When that holds
// we keep the PREVIOUS line object so its cell references stay stable (no flash/re-render).
function sameLine(a: ImgLine | undefined, b: ImgLine): boolean {
    if (!a || a.size !== b.size || a.startIndex !== b.startIndex || a.imageSize !== b.imageSize) return false
    if (a.cardWidths.length !== b.cardWidths.length || a.cardWidths.some((w, i) => w !== b.cardWidths[i])) return false
    const ad = a.data, bd = b.data
    if (ad.length !== bd.length) return false
    for (let i = 0; i < ad.length; i++) if (ad[i].id !== bd[i].id) return false
    return true
}

const items = new Map<string, ImgLine>()

function lineItem(line: LineRef): ImgLine | undefined {
    const insts = props.instances ?? []
    const start = line.index * geo.perLine
    if (line.index < 0 || start >= insts.length) return undefined
    const data = insts.slice(start, start + geo.perLine)
    const item: ImgLine = {
        id: 'img-' + start,
        type: 'images',
        data,
        startIndex: start,
        depth: 0,
        imageSize: geo.lineImgSize,
        emptyCount: geo.perLine - data.length,
        cardWidths: geo.cardWidths,
        size: geo.size,
    }
    const key = lineKey(line)
    const previous = items.get(key)
    if (sameLine(previous, item)) return previous
    if (items.size > 2000) items.clear()
    items.set(key, item)
    return item
}

// ── Instance data for the lines around the viewport ──────────────────────────
const range = shallowRef<ViewRange | null>(null)
const windowIds = computed(() => {
    const r = range.value
    if (!r) return []
    const insts = props.instances ?? []
    const ids: number[] = []
    const from = r.prefetch[0].index * geo.perLine
    const to = Math.min(insts.length, (r.prefetch[1].index + 1) * geo.perLine)
    for (let i = Math.max(0, from); i < to; i++) ids.push(insts[i].id)
    return ids
})
const windowPropIds = computed(() => props.properties?.map(p => p.id) ?? [])

defineExpose({ computeLines, clear, scrollToTop })

function scrollToTop() {
    vs.value?.scrollToOffset(0)
}

function clear() {
    items.clear()
    layout.clear()
    vs.value?.relayout({ rerender: true })
}

// `scale`: when only the line height changed, keep the same fraction of the top line in view.
function computeLines(anchor: 'pixels' | 'scale' = 'pixels') {
    // Pause while a drag is in flight so the dragged line is not handed another range out from
    // under SortableJS.
    if (dragging.value) return
    const insts = props.instances ?? []
    const lineWidth = contentWidth.value
    const perLine = Math.max(1, Math.floor(lineWidth / (props.imageSize + BORDER + GAP)))
    const { lineImgSize, cardWidths } = fillWidths(lineWidth, perLine)
    geo = { perLine, lineImgSize, cardWidths, size: imageLineSizeFor(lineImgSize) }
    lineCount = Math.ceil(insts.length / perLine)
    // One node: rebuilding is O(1).
    layout.rebuild()
    filler.value = dragEnabled.value ? Math.max(0, props.height - layout.height) : 0
    // Whatever SortableJS dropped in it: the parent has it in its list now.
    fillerList.length = 0
    vs.value?.relayout({ anchor, rerender: true })
}

// ── Selection (namespaced, via columnStore — same mechanism as the tree cell) ─────────
// A cell standing for a pile selects/reports its whole pile, so a deduplicated list behaves
// like the tree scroller's sha1 piles.
function idsFor(id: number): number[] {
    return props.piles?.[id] ?? [id]
}
function isSelectedId(id: number): boolean {
    columnStore.selectionTick(selectNs.value) // reactive dep on this namespace's selection
    return idsFor(id).every(i => columnStore.isSelectedId(i, selectNs.value))
}
// Last toggled cell: with shift held, the next toggle applies to the whole range
// between it and the clicked cell (in list order).
let anchorId: number | null = null
function toggleSelect(id: number, v: boolean) {
    let ids = idsFor(id)
    if (keyState.shift && anchorId !== null) {
        const insts = props.instances ?? []
        const a = insts.findIndex(i => i.id === anchorId)
        const b = insts.findIndex(i => i.id === id)
        if (a !== -1 && b !== -1) {
            ids = insts.slice(Math.min(a, b), Math.max(a, b) + 1).flatMap(i => idsFor(i.id))
        }
    }
    anchorId = id
    if (v) columnStore.selectIds(ids, selectNs.value)
    else columnStore.deselectIds(ids, selectNs.value)
}

// ── Drag-and-drop ─────────────────────────────────────────────────────────────────────
const dragging = ref(false)

const dragGroupOpt = computed(() =>
    dragEnabled.value ? { name: props.dragGroup, pull: true, put: true } : undefined)

function onDragEnd() {
    dragging.value = false
    nextTick(() => computeLines())
}

// vuedraggable @change (mirrors PropertyGroup.vue): translate a line-local drop into a flat
// operation on the master list. We only emit; the parent owns the arrays and mutates them,
// which re-flows `instances` and rebuilds the lines cleanly (discarding Sortable's splice).
function onLineChange(e: any, item: { startIndex: number }) {
    if (e.added) {
        emit('instance-added', { instance: e.added.element, index: item.startIndex + e.added.newIndex })
    }
    if (e.removed) {
        emit('instance-removed', { instance: e.removed.element })
    }
    if (e.moved) {
        // Reorder within one line = remove + re-insert at the new flat position.
        emit('instance-removed', { instance: e.moved.element })
        emit('instance-added', { instance: e.moved.element, index: item.startIndex + e.moved.newIndex })
    }
    nextTick(() => computeLines())
}

let _triggerHandle: ReturnType<typeof setTimeout> | undefined
function triggerUpdate() {
    if (dragging.value) return
    clearTimeout(_triggerHandle)
    _triggerHandle = setTimeout(() => computeLines(), 50)
}

// Only a namespace this scroller created is disposed on unmount. A namespace that already
// existed (e.g. the main view's selection) belongs to someone else and must survive.
let ownsNs = false
onMounted(() => {
    if (selectNs.value !== 'global') ownsNs = columnStore.ensureNamespace(selectNs.value)
    computeLines()
})

onUnmounted(() => {
    if (ownsNs) columnStore.disposeNamespace(selectNs.value)
})

// Follow the input list itself: a new array, or the same one mutated in place (the parent moves
// images between lists by splicing them).
watch(() => props.instances, () => nextTick(() => computeLines()), { deep: false })
watch(() => props.instances?.length, triggerUpdate)
watch(() => props.imageSize, () => nextTick(() => computeLines('scale')))
// Height drives the trailing filler's size (and whether it exists at all).
watch(() => props.height, () => nextTick(() => computeLines()))
// Only the line height: the same fraction of the top line stays in view.
watch(visiblePropertiesNb, () => computeLines('scale'))

let resizeWidthHandler: ReturnType<typeof setTimeout> | undefined
watch(contentWidth, () => {
    clearTimeout(resizeWidthHandler)
    resizeWidthHandler = setTimeout(() => computeLines('scale'), 200)
})
</script>

<template>
    <InstanceData :instance-ids="windowIds" :prop-ids="windowPropIds">
    <VirtualScroller ref="vs" :layout="layout" :height="props.height" :overscan="400" :tail="filler" @range="r => range = r">
        <template #default="{ line }">
            <template v-if="lineItem(line)">
                <!-- Drag disabled: a plain row, so no SortableJS instance per visible line. -->
                <div v-if="!dragEnabled" class="d-flex flex-row image-drop"
                    :style="{ minHeight: lineItem(line)!.size + 'px' }">
                    <ImageCell v-for="element, i in lineItem(line)!.data" :key="element.id" :instance="element"
                        :size="lineItem(line)!.imageSize" :width="lineItem(line)!.cardWidths[i]" :properties="props.properties"
                        :selected="isSelectedId(element.id)" :selected-preview="props.preview?.[element.id]"
                        :score="props.scores?.[element.id]" :count="props.piles?.[element.id]?.length"
                        :idx="lineItem(line)!.startIndex + i" @open="openInstance"
                        @update:selected="v => toggleSelect(element.id, v)" class="me-2 mb-2" />
                </div>

                <!-- A line's draggable spans the full width (cells are fixed-width, left-aligned),
                     so the whole row is a drop zone — not just the occupied cells. -->
                <draggable-component v-else :list="lineItem(line)!.data" :group="dragGroupOpt"
                    item-key="id" class="d-flex flex-row image-drop" :style="{ minHeight: lineItem(line)!.size + 'px' }"
                    :force-fallback="true" :fallback-on-body="true" :scroll="true"
                    handle=".image-drag-handle" :disabled="!props.dragGroup"
                    @start="dragging = true" @end="onDragEnd" @change="e => onLineChange(e, lineItem(line)!)">
                    <template #item="{ element, index: i }">
                        <ImageCell :instance="element" :size="lineItem(line)!.imageSize" :width="lineItem(line)!.cardWidths[i]"
                            :properties="props.properties" :selected="isSelectedId(element.id)"
                            :selected-preview="props.preview?.[element.id]" :score="props.scores?.[element.id]"
                            :count="props.piles?.[element.id]?.length"
                            :idx="lineItem(line)!.startIndex + i" @open="openInstance"
                            @update:selected="v => toggleSelect(element.id, v)" class="me-2 mb-2" />
                    </template>
                </draggable-component>
            </template>
        </template>

        <!-- Empty, droppable region filling the pane's leftover height so a sparse/empty
             list still accepts drops anywhere below the images. -->
        <template #tail="{ height }">
            <draggable-component :list="fillerList" :group="dragGroupOpt"
                item-key="id" class="image-drop" :style="{ height: height + 'px' }"
                :force-fallback="true" :fallback-on-body="true" :scroll="true" :disabled="!props.dragGroup"
                @start="dragging = true" @end="onDragEnd" @change="e => onLineChange(e, { startIndex: props.instances?.length ?? 0 })">
                <template #item="{ element }"><div :key="element.id"></div></template>
            </draggable-component>
        </template>
    </VirtualScroller>
    </InstanceData>
</template>

<style scoped>
/* Full-width drop zone so images can be dropped anywhere on a row (or in the filler),
   not only onto an existing cell. */
.image-drop {
    width: 100%;
}
</style>
