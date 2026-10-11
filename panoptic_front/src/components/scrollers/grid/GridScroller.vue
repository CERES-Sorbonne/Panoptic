<script setup lang="ts">
import { computed, onMounted, onUnmounted, provide, reactive, ref, shallowRef, watch } from 'vue';
import TableHeader from './TableHeader.vue';
import { keyState } from '@/data/composables/keyState';
import { Group } from '@/core/GroupManager'
import type { GroupInspector } from '@/core/group/inspector'
import { Property, ModalId, PropertyMode } from '@/data/models';
import { GroupLine, PileRowLine, RowLine } from '@/components/scrollers/types';
import GridScrollerLine from './GridScrollerLine.vue';
import { usePanopticStore } from '@/data/stores/panopticStore';
import { useColumnStore } from '@/data/stores/columnStore';
import { TabManager } from '@/core/TabManager';
import InstanceData from '@/components/data/InstanceData.vue';
import VirtualScroller from '@/components/scrollers/virtual/VirtualScroller.vue';
import { ScrollLayout, lineKey } from '@/components/scrollers/virtual/scrollLayout';
import type { LineRef } from '@/components/scrollers/virtual/scrollLayout';
import type { ViewRange } from '@/components/scrollers/virtual/virtualView';
import { cellEditingKey, CellKey, useCellEditing } from '@/components/scrollers/cellEditing';
import { adjacentCellIn, revealOffset } from '@/components/scrollers/cellNavigation';
import { gridCellWalk, gridGroupLine, gridRow, gridSource } from './gridLines';

const panoptic = usePanopticStore()
const columnStore = useColumnStore()

// Type-based props: `manager` is the GroupInspector contract (a CollectionManager in the
// main/view panes, a standalone GroupManager elsewhere), which has no runtime constructor.
const props = withDefaults(defineProps<{
    tab: TabManager,
    manager: GroupInspector,
    height: number,
    width: number,
    selectedProperties: Property[],
    showImages?: boolean,
    hideIfModal?: boolean,
    // Per-view image size (Pillar F). Passed in by the pane; tab-level imageSize
    // no longer exists.
    imageSize?: number,
}>(), { imageSize: 100 })

defineExpose({
    computeLines: () => computeLines(true),
    clear
})

// TableHeader is a single 30px row (the old "Images: n" summary row was removed).
const hearderHeight = ref(30)
// Width eaten by the scroller's vertical scrollbar. The header sits outside the
// scrolling element, so without subtracting it the header is wider than the rows.
const scrollbarWidth = ref(0)
const currentGroup = reactive({} as Group)
const visibleProperties = computed(() => props.selectedProperties.filter(p => {
    return p.mode == PropertyMode.sha1 || props.manager.groupState.sha1Mode == false
}))

const tabState = computed(() => props.tab.state)

const totalPropWidth = computed(() => {
    const options =tabState.value.propertyOptions
    let propSum = visibleProperties.value.map(p => options[p.id]?.size ?? 0).reduce((a, b) => a + b, 0)
    if (props.showImages) {
        propSum += props.imageSize
    }
    return propSum
})

// Usable width: what the rows actually get inside the scrolling element.
const contentWidth = computed(() => props.width - scrollbarWidth.value)

const scrollerWidth = computed(() => Math.max(totalPropWidth.value, contentWidth.value))

const missingWidth = computed(() => contentWidth.value - totalPropWidth.value)

const scrollerHeight = computed(() => props.height - hearderHeight.value)

// The least height of an image/pile row (the image, or one line of text), and the size of the rows
// not measured yet. Rows grow to fit their cells (multi-line text, wrapped tags: see
// GridCellView); the VirtualScroller measures the rows on screen (`measure`) and the layout keeps
// those heights per leaf.
const rowSize = computed(() => props.showImages ? props.imageSize + 4 : 28)

// ── Layout ────────────────────────────────────────────────────────────────────
// The tree is handed to the VirtualScroller as it is (gridSource): a leaf's row count is its slot
// count, and a row object is only made for the rows on screen (gridItem). Opening or closing a
// group, or a row measuring itself, changes a few numbers per group; nothing is built per image.
const layout = new ScrollLayout(gridSource(() => props.manager.result, () => rowSize.value))
const vs = ref<InstanceType<typeof VirtualScroller>>()

// Empty space below the last row.
const TAIL = 300

// The line objects handed to the rows, by line key, handed back while they come out the same so an
// unchanged row is not re-rendered. Only lines that were on screen are here.
const items = new Map<string, GroupLine | RowLine | PileRowLine>()

function gridItem(line: LineRef): GroupLine | RowLine | PileRowLine | undefined {
    const host = props.manager.result
    const key = lineKey(line)
    const previous = items.get(key)
    let item: GroupLine | RowLine | PileRowLine | undefined
    if (line.index < 0) {
        const group = host.index[line.node]
        item = group && gridGroupLine(group, previous?.type === 'group' ? previous as GroupLine : undefined)
    } else {
        item = gridRow(host, columnStore.instanceIds(), line, previous?.type === 'group' ? undefined : previous as RowLine | PileRowLine)
    }
    if (item && item !== previous) {
        if (items.size > 2000) items.clear()
        items.set(key, item)
    }
    return item
}

// What the layout was last read from (see computeLines).
let builtResult: unknown
let builtRev = -1
let builtVersion = -1

/**
 * Reads the tree again: rebuilt when it is another tree or its structure changed (`rev`),
 * refreshed otherwise (open states, row counts). O(groups) either way. Every mounted row checks its
 * item (an unchanged one comes back the same and is not re-rendered).
 */
function computeLines(force = false) {
    const result = props.manager.result
    if (force || result !== builtResult || result.rev !== builtRev) layout.rebuild()
    else layout.refresh()
    builtResult = result
    builtRev = result.rev
    builtVersion = props.manager.version.value
    vs.value?.relayout({ rerender: true })
}

// Opening or closing a group from its row: applied to the layout right away, that group only, and
// the version stamped so the version watcher has nothing left to do.
function toggled(groupId: number) {
    const result = props.manager.result
    if (result !== builtResult || result.rev !== builtRev) return computeLines()
    layout.refreshNode(groupId)
    builtVersion = props.manager.version.value
    vs.value?.relayout()
}

function openGroup(groupId: number) {
    props.manager.openGroup(groupId, true)
    toggled(groupId)
}

function closeGroup(groupId: number) {
    props.manager.closeGroup(groupId, true)
    toggled(groupId)
}

function selectImage(groupId: number, imageIndex: number) {
    // Recycled lines can outlive the group they point at; an invalid iterator has no slots.
    const iterator = props.manager.getImageIterator(groupId, imageIndex)
    if (iterator.isValid) props.manager.toggleImageIterator(iterator, keyState.shift)
}

function selectGroup(groupId: number) {
    const iterator = props.manager.getGroupIterator(groupId)
    if (iterator.isValid) props.manager.toggleGroupIterator(iterator, keyState.shift)
}

function clear() {
    items.clear()
    builtResult = undefined
    layout.clear()
    vs.value?.relayout({ rerender: true })
}

// Another manager (the tab or the pane's collection changed, the same view kept): its version may
// well equal the old one's, so the version watcher below cannot be relied on to see it.
watch(() => props.manager, () => {
    items.clear()
    computeLines(true)
})

// Re-render on result change via the version tick (note §3, step 1).
watch(() => props.manager.version.value, () => {
    const result = props.manager.result
    if (result === builtResult && result.rev === builtRev && builtVersion === props.manager.version.value) return
    computeLines()
})

// The scrolling element itself must also cover the scrollbar gutter, otherwise
// measuring it would shrink the content on every pass.
const scrollerStyle = computed(() => ({
    height: scrollerHeight.value + 'px',
    width: (scrollerWidth.value + scrollbarWidth.value) + 'px',
}))

const hideFromModal = computed(() => props.hideIfModal && (panoptic.openModalId == ModalId.IMAGE || panoptic.openModalId == ModalId.TAG))

// ── Instance data for the rows around the viewport ────────────────────────────
// The prefetch range: the mounted rows and a viewport ahead in the scroll direction. Held by the
// scroller while flinging.
const range = shallowRef<ViewRange | null>(null)

const windowIds = computed(() => {
    const r = range.value
    if (!r) return []
    const host = props.manager.result
    const colIds = columnStore.instanceIds()
    const ids: number[] = []
    for (const line of layout.between(r.prefetch[0], r.prefetch[1], 1000)) {
        if (line.index < 0) continue
        const row = gridRow(host, colIds, line)
        if (!row) continue
        if (row.type === 'pile') for (const slot of (row as PileRowLine).data.slots) ids.push(colIds[slot])
        else ids.push((row as RowLine).data.id)
    }
    return ids
})

const windowPropIds = computed(() => visibleProperties.value.map(p => p.id))

// ── Property cells ────────────────────────────────────────────────────────────
// The rows draw their cells read-only (GridCellView) and mount an editor only for the cell being
// edited; which one that is lives here, per scroller.
const cells = useCellEditing({ navigate: navigateCell })
provide(cellEditingKey, cells)

// Tab / Shift-Tab: the same column on the next / previous row, scrolled into view first.
async function navigateCell(from: CellKey, backwards: boolean): Promise<CellKey | undefined> {
    const to = adjacentCellIn(gridCellWalk(props.manager.result, layout, columnStore.instanceIds()), from, backwards)
    if (!to || to.cell.instanceId === undefined || !vs.value) return undefined
    const reveal = () => revealOffset(layout.offsetOf(to.line), layout.sizeOf(to.line), vs.value!.scrollTop(), scrollerHeight.value)
    let offset = reveal()
    if (offset !== undefined) {
        // The editor being left commits on its blur: give it that now, while its row is still
        // there — the scroll can recycle it.
        ;(document.activeElement as HTMLElement)?.blur?.()
        // Off-screen rows have estimated sizes: the rows drawn on arrival measure themselves, and
        // can push the target out of view again. Once more with their real heights; twice is
        // enough (the target and its neighbours are measured by then).
        for (let pass = 0; pass < 2 && offset !== undefined; pass++) {
            vs.value.scrollToOffset(offset)
            // Open only once the scroll has landed and the target row is drawn (and measured).
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
            // The tree changed meanwhile: the target is not where it was.
            if (!vs.value || !layout.isShown(to.line)) break
            offset = reveal()
        }
    }
    return { ...to.cell, propertyId: from.propertyId }
}

// ── Scrollbar width ───────────────────────────────────────────────────────────
let scrollbarObserver: ResizeObserver | undefined

function measureScrollbar() {
    const el = vs.value?.el()
    if (!el) return
    // Overlay scrollbars (default on macOS) measure 0, which is correct: they
    // take no layout space, so header and rows already line up.
    const w = el.offsetWidth - el.clientWidth
    if (w >= 0 && w !== scrollbarWidth.value) scrollbarWidth.value = w
}

onMounted(() => {
    // Build the first layout here, like the other scrollers do. A view must not wipe collection
    // state (the authored ClusterOverlay map) shared with the other pane just to draw itself.
    computeLines(true)
    const el = vs.value?.el()
    if (el) {
        // The content box narrows when the scrollbar appears, and widens when it goes.
        scrollbarObserver = new ResizeObserver(measureScrollbar)
        scrollbarObserver.observe(el)
    }
    measureScrollbar()
})

onUnmounted(() => {
    scrollbarObserver?.disconnect()
})

// What a row's height depends on besides its own values: the row height (image size, images
// shown), which properties are shown, and the width of each column (the last one takes up the
// width left over). When it changes, what was measured off screen no longer holds and those rows go
// back to the estimate. The rows on screen keep their size: they report their new height themselves
// if it changed, and are still right if it did not — resetting them would collapse the visible rows
// for nothing. An instance's values changing needs nothing: a row on screen reports its new height,
// one off screen is measured when it is next drawn.
const rowLayout = computed(() => {
    const options = tabState.value.propertyOptions
    return rowSize.value + ':' + visibleProperties.value.map(p => p.id + '=' + (options[p.id]?.size ?? 0)).join(',')
        + ':' + Math.max(0, missingWidth.value)
})
watch(rowLayout, () => {
    const mounted = vs.value?.mountedLines().filter(l => l.index >= 0) ?? []
    // The estimate may have changed too (rowSize).
    layout.refresh()
    layout.clearMeasured(mounted)
    vs.value?.relayout()
})

</script>

<template>
    <!-- ctrl-held: url cells read as links while ctrl is down (see GridCellView) -->
    <div class="grid-container overflow-hidden" :class="{ 'ctrl-held': keyState.ctrl }" :style="{ width: scrollerStyle.width }">
        <TableHeader :tab="props.tab" :image-size="props.imageSize" :manager="props.manager" :properties="visibleProperties" :missing-width="missingWidth"
            :show-image="props.showImages" :current-group="currentGroup" class="p-0 m-0" />

        <InstanceData :instance-ids="windowIds" :prop-ids="windowPropIds">
        <VirtualScroller ref="vs" :layout="layout" :height="scrollerHeight" :measure="true" :tail="TAIL" :overscan="300"
            :style="{ width: scrollerStyle.width }" class="p-0 m-0" @range="r => range = r">
            <template #default="{ line }">
                <GridScrollerLine v-if="!hideFromModal && gridItem(line)" :item="gridItem(line)!" :tab="props.tab"
                    :image-size="props.imageSize" :manager="props.manager" :properties="visibleProperties" :width="scrollerWidth"
                    :show-images="props.showImages" :row-height="rowSize"
                    :missing-width="missingWidth" @open:group="openGroup" @close:group="closeGroup"
                    @toggle:image="({ groupId, imageIndex }) => selectImage(groupId, imageIndex)" @toggle:group="selectGroup" />
            </template>
        </VirtualScroller>
        </InstanceData>
    </div>
</template>

<style>
.grid-container {
    white-space: nowrap;
}

/* The row holding the cell being edited is raised: its editor's focus shadow is let out of the
   cell (see RowLine), and each slot is its own stacking context, laid out in pool order, so the
   row below could paint over it. */
.grid-container .vs-slot:focus-within {
    z-index: 1;
}
</style>
