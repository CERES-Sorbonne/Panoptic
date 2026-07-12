<script setup lang="ts">
// A groupless image scroller. Derived from tree/TreeScroller.vue but it takes a plain
// Instance[] instead of a GroupManager and renders a flat, virtualized wall of images.
//
// Drag-and-drop: each visible line wraps its cells in a <draggable-component>. Every line
// (in this scroller AND any other ImageScroller given the same `dragGroup`) shares one
// SortableJS group, so an image can be dragged out of any visible line and dropped into
// any other — including a line in the other scroller. On a drop we don't mutate our own
// list; we emit what changed and let the owning parent update the source/target arrays,
// then recompute the lines. RecycleScroller virtualization is preserved (lists can be huge).
import { ref, nextTick, onMounted, onUnmounted, watch, computed, Ref, shallowRef, provide } from 'vue';
import ImageCell from './ImageCell.vue';
import { RecycleScroller } from 'vue-virtual-scroller';
import draggableComponent from 'vuedraggable';
import { Property, PropertyMode, ModalId, Instance } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { useColumnStore } from '@/data/columnStore';
import InstanceData from '@/components/data/InstanceData.vue';

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
    // ColumnStore selection namespace so two scrollers can select independently.
    selectNamespace?: string,
    hideIfModal?: boolean,
}>()

const emit = defineEmits<{
    // The moved Instance object is passed so the receiving parent can insert it directly.
    (e: 'instance-added', payload: { instance: Instance, index: number }): void
    (e: 'instance-removed', payload: { instance: Instance }): void
}>()

// The line model this scroller builds. Image lines hold cells; a trailing 'filler' line
// (empty, but droppable) covers the pane's remaining height so a sparse/empty list still
// offers a large drop target.
interface ImgLine {
    id: string
    type: 'images' | 'filler'
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

const imageLines = shallowRef([]) as Ref<ImgLine[]>
const scroller = ref(null)

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

// ── Window-level batch registration ──────────────────────────────────────────
const windowStart = ref(0)
const windowEnd   = ref(0)

function onScrollerUpdate(startIndex: number, endIndex: number) {
    windowStart.value = startIndex
    windowEnd.value   = endIndex
}

const windowIds = computed(() => {
    const ids: number[] = []
    const lines = imageLines.value
    if (!lines.length) return ids
    // Clamp reported indices and expand ±5 lines to prefetch just off-screen rows.
    const start = Math.max(0, Math.min(windowStart.value, lines.length - 1) - 5)
    const end   = Math.min(lines.length - 1, Math.max(0, windowEnd.value) + 5)
    for (let i = start; i <= end; i++) {
        for (const inst of lines[i].data) ids.push(inst.id)
    }
    return ids
})
const windowPropIds = computed(() => props.properties?.map(p => p.id) ?? [])

defineExpose({ computeLines, clear })

function clear() {
    imageLines.value = []
}

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

// Two lines are interchangeable when rendering them produces the same DOM. When that holds
// we keep the PREVIOUS line object so its cell references stay stable (no flash/re-render).
function sameLine(a: ImgLine, b: ImgLine): boolean {
    if (!a || a.type !== b.type || a.size !== b.size || a.startIndex !== b.startIndex) return false
    const ad = a.data, bd = b.data
    if (ad.length !== bd.length) return false
    for (let i = 0; i < ad.length; i++) if (ad[i].id !== bd[i].id) return false
    return true
}

function reconcileLines(prev: ImgLine[], next: ImgLine[]): ImgLine[] {
    if (!prev.length) return next
    const byId = new Map<string, ImgLine>()
    for (const l of prev) byId.set(l.id, l)
    for (let i = 0; i < next.length; i++) {
        const old = byId.get(next[i].id)
        if (old && sameLine(old, next[i])) next[i] = old
    }
    return next
}

let _computingLines = false
function computeLines() {
    // Pause rebuilds while a drag is in flight so RecycleScroller doesn't recycle the
    // dragged line out from under SortableJS.
    if (_computingLines || dragging.value) return
    _computingLines = true
    try {
        const insts = props.instances ?? []
        const lineWidth = contentWidth.value
        const itemsPerLine = Math.max(1, Math.floor(lineWidth / (props.imageSize + BORDER + GAP)))
        const { lineImgSize, cardWidths } = fillWidths(lineWidth, itemsPerLine)
        const size = imageLineSizeFor(lineImgSize)

        const lines: ImgLine[] = []
        for (let i = 0; i < insts.length; i += itemsPerLine) {
            const slice = insts.slice(i, i + itemsPerLine)
            lines.push({
                id: 'img-' + i,
                type: 'images',
                data: slice,
                startIndex: i,
                depth: 0,
                imageSize: lineImgSize,
                emptyCount: itemsPerLine - slice.length,
                cardWidths,
                size,
            })
        }

        // When drops are allowed and the images don't fill the pane, append an empty but
        // droppable filler covering the leftover height. Without it an empty pane has no
        // draggable target and a near-empty one only accepts drops on its few cells.
        const usedHeight = lines.length * size
        if (props.dragGroup && usedHeight < props.height) {
            lines.push({
                id: 'filler',
                type: 'filler',
                data: [],
                startIndex: insts.length,
                depth: 0,
                imageSize: lineImgSize,
                emptyCount: 0,
                cardWidths,
                size: props.height - usedHeight,
            })
        }
        imageLines.value = reconcileLines(imageLines.value, lines)
    } finally {
        _computingLines = false
    }
}

// ── Selection (namespaced, via columnStore — same mechanism as the tree cell) ─────────
function isSelectedId(id: number): boolean {
    columnStore.selectionTick(selectNs.value) // reactive dep on this namespace's selection
    return columnStore.isSelectedId(id, selectNs.value)
}
function toggleSelect(id: number, v: boolean) {
    if (v) columnStore.selectIds([id], selectNs.value)
    else columnStore.deselectIds([id], selectNs.value)
}

// ── Drag-and-drop ─────────────────────────────────────────────────────────────────────
const dragging = ref(false)

const dragGroupOpt = computed(() =>
    props.dragGroup ? { name: props.dragGroup, pull: true, put: true } : undefined)

function onDragEnd() {
    dragging.value = false
    nextTick(computeLines)
}

// vuedraggable @change (mirrors PropertyGroup.vue): translate a line-local drop into a flat
// operation on the master list. We only emit; the parent owns the arrays and mutates them,
// which re-flows `instances` and rebuilds the lines cleanly (discarding Sortable's splice).
function onLineChange(e: any, item: ImgLine) {
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
    nextTick(computeLines)
}

let _triggerHandle: ReturnType<typeof setTimeout> | undefined
function triggerUpdate() {
    if (dragging.value) return
    clearTimeout(_triggerHandle)
    _triggerHandle = setTimeout(computeLines, 50)
}

onMounted(() => {
    if (selectNs.value !== 'global') columnStore.ensureNamespace(selectNs.value)
    computeLines()
})

onUnmounted(() => {
    if (selectNs.value !== 'global') columnStore.disposeNamespace(selectNs.value)
})

// Follow the input list itself (reference or contents) — the parent mutates it on a move.
watch(() => props.instances, () => nextTick(computeLines), { deep: false })
watch(() => props.instances?.length, triggerUpdate)
watch(() => props.imageSize, () => nextTick(computeLines))
// Height drives the trailing filler's size (and whether it exists at all).
watch(() => props.height, () => nextTick(computeLines))

const margin_scroll_offset = 0
watch(visiblePropertiesNb, () => {
    const lines = imageLines.value
    if (!lines.length) return

    // Snapshot scroll position and preserve the item at the viewport top across the
    // line-height change (same technique as TreeScroller).
    const scrollPos = scroller.value.getScroll().start + margin_scroll_offset
    let topItemIdx = lines.length - 1
    let cumSize = 0
    for (let i = 0; i < lines.length; i++) {
        if (cumSize + lines[i].size > scrollPos) { topItemIdx = i; break }
        cumSize += lines[i].size
    }
    const delta = scrollPos - cumSize
    // The filler keeps its own height; only image lines resize with the property count.
    const newSizeOf = (l: ImgLine) => l.type === 'filler' ? l.size : imageLineSizeFor(l.imageSize)

    let newScrollPos = 0
    for (let i = 0; i < topItemIdx; i++) newScrollPos += newSizeOf(lines[i])
    const oldTopSize = lines[topItemIdx].size
    const newTopSize = newSizeOf(lines[topItemIdx])
    newScrollPos += oldTopSize > 0 ? delta * (newTopSize / oldTopSize) : delta

    scroller.value.$el.scrollTop = newScrollPos - margin_scroll_offset
    let imgHeight = 0
    for (const l of lines) {
        if (l.type === 'images') { l.size = imageLineSizeFor(l.imageSize); imgHeight += l.size }
    }
    // Re-fit the filler to the pane's new leftover height.
    const filler = lines.find(l => l.type === 'filler')
    if (filler) filler.size = Math.max(0, props.height - imgHeight)
    imageLines.value = [...lines]
})

let resizeWidthHandler: ReturnType<typeof setTimeout> | undefined
watch(contentWidth, () => {
    clearTimeout(resizeWidthHandler)
    resizeWidthHandler = setTimeout(computeLines, 200)
})
</script>

<template>
    <InstanceData :instance-ids="windowIds" :prop-ids="windowPropIds">
    <RecycleScroller :items="imageLines" key-field="id" ref="scroller" :style="'height: ' + props.height + 'px;'"
        :buffer="400" :min-item-size="0" :emitUpdate="true" @update="onScrollerUpdate" :page-mode="false" :prerender="0">
        <template v-slot="{ item }">
            <!-- A line's draggable spans the full width (cells are fixed-width, left-aligned),
                 so the whole row is a drop zone — not just the occupied cells. -->
            <draggable-component v-if="item.type == 'images'" :list="item.data" :group="dragGroupOpt"
                item-key="id" class="d-flex flex-row image-drop" :style="{ minHeight: item.size + 'px' }"
                :force-fallback="true" :fallback-on-body="true" :scroll="true"
                handle=".image-drag-handle" :disabled="!props.dragGroup"
                @start="dragging = true" @end="onDragEnd" @change="e => onLineChange(e, item)">
                <template #item="{ element, index: i }">
                    <ImageCell :instance="element" :size="item.imageSize" :width="item.cardWidths[i]"
                        :properties="props.properties" :selected="isSelectedId(element.id)"
                        :idx="item.startIndex + i"
                        @update:selected="v => toggleSelect(element.id, v)" class="me-2 mb-2" />
                </template>
            </draggable-component>

            <!-- Empty, droppable region filling the pane's leftover height so a sparse/empty
                 list still accepts drops anywhere below the images. -->
            <draggable-component v-else-if="item.type == 'filler'" :list="item.data" :group="dragGroupOpt"
                item-key="id" class="image-drop" :style="{ height: item.size + 'px' }"
                :force-fallback="true" :fallback-on-body="true" :scroll="true" :disabled="!props.dragGroup"
                @start="dragging = true" @end="onDragEnd" @change="e => onLineChange(e, item)">
                <template #item="{ element }"><div :key="element.id"></div></template>
            </draggable-component>
        </template>
    </RecycleScroller>
    </InstanceData>
</template>

<style scoped>
/* Full-width drop zone so images can be dropped anywhere on a row (or in the filler),
   not only onto an existing cell. */
.image-drop {
    width: 100%;
}
</style>
