<script setup lang="ts">
// import RecycleScroller from '@/components/Scroller/src/components/RecycleScroller.vue';
import { computed, nextTick, onMounted, onUnmounted, provide, reactive, ref, watch } from 'vue';
import TableHeader from './TableHeader.vue';
import { keyState } from '@/data/composables/keyState';
import { Group} from '@/core/GroupManager'
import type { GroupInspector } from '@/core/group/inspector'
import { Property, ModalId, PropertyMode } from '@/data/models';
import { GroupLine, RowLine, PileRowLine, ScrollerLine } from '@/components/scrollers/types';
import { useProjectStore } from '@/data/stores/projectStore';
import GridScrollerLine from './GridScrollerLine.vue';
import {RecycleScroller} from 'vue-virtual-scroller';
import { usePanopticStore } from '@/data/stores/panopticStore';
import { useColumnStore } from '@/data/stores/columnStore';
import { TabManager } from '@/core/TabManager';
import InstanceData from '@/components/data/InstanceData.vue';
import { usePagedLines } from '@/components/scrollers/usePagedLines';
import { cellEditingKey, CellKey, useCellEditing } from '@/components/scrollers/cellEditing';
import { adjacentCell, CellLines, revealOffset } from '@/components/scrollers/cellNavigation';
import { GridLineCache, rowInstanceId } from './gridLines';
import { RowHeights, rowHeightsKey } from './rowHeights';

const project = useProjectStore()
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
    // scrollTo,
    computeLines,
    clear
})

// TableHeader is a single 30px row (the old "Images: n" summary row was removed).
const hearderHeight = ref(30)
// Width eaten by the scroller's vertical scrollbar. The header sits outside the
// scrolling element, so without subtracting it the header is wider than the rows.
const scrollbarWidth = ref(0)
const scroller = ref(null)
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
// not measured yet. Rows grow to fit their cells (multi-line text, wrapped tags, up to a cap: see
// GridCellView) and are measured once on screen, by row and without forced layout (rowHeights.ts).
// Measuring used to go cell by cell, each correction moving the window, which mounted more rows
// that measured again — the table froze in waves on every open/close, column change and scroll.
const rowSize = computed(() => props.showImages ? props.imageSize + 4 : 28)

// The full line list stays here; the scroller only gets the lines around the viewport plus
// padding (see usePagedLines), so a huge list does not go past the browser's height limit.
// Shallow: line sizes are only ever set here (built, or measured — then `paged.updateSizes`), so
// nothing needs the rendered items (and the Group objects, slots and all, behind group lines) to
// be proxied.
// Mounted beyond the viewport: 300px (a row when they are taller), enough for a fast trackpad
// frame. The rows are short, so this is already 10 rows without images; what made scrolling heavy
// was the window being rebuilt about every row, re-rendering every mounted row (see usePagedLines).
const paged = usePagedLines<ScrollerLine>({ scroller, viewportHeight: () => scrollerHeight.value, minBuffer: 300 })
const rowLines = paged.windowLines
const scrollerBuffer = paged.buffer

// ── Row heights ───────────────────────────────────────────────────────────────
// The rows on screen report their height together, once per frame; the sizes are set in place and
// the scroller laid out again in one go, keeping the top line where it is (paged.updateSizes).
// Heights are also kept per image (a pile row by its first image), so the rows of a leaf that is
// re-rowed (a sort, a regroup) start at their last measured height rather than the estimate.
// What is kept is only ever an estimate: a row is measured again each time it is mounted.
const heights = new Map<number, number>()
const rowHeights = new RowHeights(changes => {
    const ids = columnStore.instanceIds()
    paged.updateSizes(() => {
        for (const [line, size] of changes) {
            line.size = size
            const id = rowInstanceId(line, ids)
            if (id !== undefined) heights.set(id, size)
        }
        return true
    })
})
provide(rowHeightsKey, rowHeights)
const measuredHeight = (instanceId: number) => heights.get(instanceId)

// The rows' layout changed (row height, columns, properties shown): what was measured off screen
// no longer holds, and those rows go back to the estimate. The rows on screen keep their size: they
// report their new height themselves if it changed, and are still right if it did not — resetting
// them would collapse the visible rows for nothing, and could rebuild the window.
function forgetHeights() {
    const mounted = rowHeights.mountedLines()
    const ids = columnStore.instanceIds()
    heights.clear()
    for (const line of mounted) {
        const id = rowInstanceId(line, ids)
        if (id !== undefined) heights.set(id, line.size)
    }
    if (!dataLines.length) return
    paged.updateSizes(() => lineCache.resize(rowSize.value, mounted))
}

// The scrolling element itself must also cover the scrollbar gutter, otherwise
// measuring it would shrink the content on every pass.
const scrollerStyle = computed(() => ({
    height: scrollerHeight.value + 'px',
    width: (scrollerWidth.value + scrollbarWidth.value) + 'px',
    // overflowX: 'hidden'
}))

const hideFromModal = computed(() => props.hideIfModal && (panoptic.openModalId == ModalId.IMAGE || panoptic.openModalId == ModalId.TAG))

// windowIds is derived from the current window slice — no separate index tracking needed.
const windowIds = computed(() => {
    const ids: number[] = []
    const colIds = columnStore.instanceIds()
    for (const line of rowLines.value) {
        if (line.type === 'image') {
            ids.push((line as RowLine).data.id)
        } else if (line.type === 'pile') {
            for (const slot of (line as PileRowLine).data.slots) ids.push(colIds[slot])
        }
    }
    return ids
})

const windowPropIds = computed(() => visibleProperties.value.map(p => p.id))

// Non-reactive master list.
let dataLines: ScrollerLine[] = []

// ── Property cells ────────────────────────────────────────────────────────────
// The rows draw their cells read-only (GridCellView) and mount an editor only for the cell being
// edited; which one that is lives here, per scroller.
const cells = useCellEditing({ navigate: navigateCell })
provide(cellEditingKey, cells)

// One cell per image or pile row, in display order. A pile row edits its first image (see RowLine).
function cellLines(): CellLines {
    const lines = dataLines
    const ids = columnStore.instanceIds()
    return {
        count: lines.length,
        cells: l => lines[l].type === 'image' || lines[l].type === 'pile' ? 1 : 0,
        at: l => {
            const line = lines[l]
            if (line.type === 'pile') {
                const handle = (line as PileRowLine).data
                return { instanceId: ids[handle.slots[0]], groupId: handle.groupId }
            }
            return { instanceId: (line as RowLine).data.id, groupId: line.groupId }
        },
    }
}

// Tab / Shift-Tab: the same column on the next / previous row, scrolled into view first.
async function navigateCell(from: CellKey, backwards: boolean): Promise<CellKey | undefined> {
    const to = adjacentCell(cellLines(), from, backwards)
    if (!to || to.cell.instanceId === undefined) return undefined
    const target = dataLines[to.line]
    const reveal = () => revealOffset(paged.lineOffset(to.line), target.size, paged.getScrollTop(), scrollerHeight.value)
    let offset = reveal()
    if (offset !== undefined) {
        // The editor being left commits on its blur: give it that now, while its row is still
        // there — the scroll can recycle it.
        ;(document.activeElement as HTMLElement)?.blur?.()
        // Off-screen rows have estimated sizes: the rows drawn on arrival measure themselves, and
        // can push the target out of view again. Once more with their real heights; twice is
        // enough (the target and its neighbours are measured by then).
        for (let pass = 0; pass < 2 && offset !== undefined; pass++) {
            paged.scrollToPosition(offset)
            // Open only once the scroll has landed and the target row is drawn (and measured).
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
            // The lines were rebuilt meanwhile: the target is not where it was.
            if (dataLines[to.line] !== target) break
            offset = reveal()
        }
    }
    return { ...to.cell, propertyId: from.propertyId }
}

// ── line construction ─────────────────────────────────────────────────────────

// Each leaf's rows, kept across rebuilds and handed back while they still match the leaf (see
// GridLineCache). A rebuild walks the groups and only re-rows the leaves whose images changed —
// opening or closing a group re-rows nothing.
const lineCache = new GridLineCache()

function computeLines() {
    if (!props.manager.result.root) return
    const host = props.manager.result
    const lines: ScrollerLine[] = []
    const ids = columnStore.instanceIds()
    const size = rowSize.value

    function visit(group: Group) {
        // Piled leaves have no children; a group with children is a real sub-tree.
        if (group.children.length > 0) {
            if (!group.view.closed) {
                for (const child of group.children) visit(child)
            }
            return
        }

        if (group.id !== 0) {
            lines.push({
                id: group.id,
                data: group,
                type: 'group',
                size: 35,
                nbClusters: 10,
                groupId: group.id,
            } as GroupLine)
        }

        if (group.view.closed) return
        const rows = lineCache.leafLines(host, group, ids, size, measuredHeight)
        for (let i = 0; i < rows.length; i++) lines.push(rows[i])
    }

    visit(host.root)
    lineCache.prune(host)
    lines.push({ id: '__filler__', type: 'fillter', size: 300, index: lines.length, data: null })

    // Keeps the scroll position.
    dataLines = lines
    paged.setLines(lines)
}

function openGroup(groupId: number) {
    props.manager.openGroup(groupId, true)
    // computeLines()
}

function closeGroup(groupId: number) {
    props.manager.closeGroup(groupId, true)
    // computeLines()
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
    lineCache.clear()
    heights.clear()
    dataLines = []
    paged.setLines([])
}

function changeHandler(){
    computeLines()
}
// Re-render on result change via the version tick (note §3, step 1).
watch(() => props.manager.version.value, changeHandler)

let scrollbarObserver: ResizeObserver | undefined

function measureScrollbar() {
    const el = scroller.value?.$el as HTMLElement | undefined
    if (!el) return
    // Overlay scrollbars (default on macOS) measure 0, which is correct: they
    // take no layout space, so header and rows already line up.
    const w = el.offsetWidth - el.clientWidth
    if (w >= 0 && w !== scrollbarWidth.value) scrollbarWidth.value = w
}

onMounted(() => {
    // Build the first window here, like the other scrollers do (TreeScroller, ImageScroller).
    // This used to be `manager.clearCustomGroups(true)`: the emit was what triggered the first
    // compute, and dropping the clusters was how the grid avoided rendering nodes its old row
    // model could not express. Both reasons are gone — `computeLines` walks the tree by
    // children/slots and does not look at GroupType, so cluster nodes render as ordinary group
    // rows. A view must not wipe collection state (the authored ClusterOverlay map) shared with
    // the other pane just to draw itself.
    computeLines()
    const el = scroller.value?.$el as HTMLElement | undefined
    if (el) {
        scrollbarObserver = new ResizeObserver(measureScrollbar)
        scrollbarObserver.observe(el)
    }
    measureScrollbar()
})

onUnmounted(() => {
    scrollbarObserver?.disconnect()
    rowHeights.disconnect()
})

// The scrollbar appears/disappears as content grows or shrinks.
watch(rowLines, () => nextTick(measureScrollbar))

// What a row's height depends on besides its own values: the row height (image size, images
// shown), which properties are shown, and the width of each column (the last one takes up the
// width left over). An instance's values changing needs nothing: a row on screen reports its new
// height, one off screen is measured when it is next drawn.
const rowLayout = computed(() => {
    const options = tabState.value.propertyOptions
    return rowSize.value + ':' + visibleProperties.value.map(p => p.id + '=' + (options[p.id]?.size ?? 0)).join(',')
        + ':' + Math.max(0, missingWidth.value)
})
watch(rowLayout, forgetHeights)

</script>

<template>
    <!-- ctrl-held: url cells read as links while ctrl is down (see GridCellView) -->
    <div class="grid-container overflow-hidden" :class="{ 'ctrl-held': keyState.ctrl }" :style="{ width: scrollerStyle.width }">
        <TableHeader :tab="props.tab" :image-size="props.imageSize" :manager="props.manager" :properties="visibleProperties" :missing-width="missingWidth"
            :show-image="props.showImages" :current-group="currentGroup" class="p-0 m-0" />

        <InstanceData :instance-ids="windowIds" :prop-ids="windowPropIds">
        <!-- skip-hover: nothing reads the scroller's own `hover` class, and setting it re-rendered
             the scroller's whole pool each time the pointer crossed into another row. -->
        <RecycleScroller :items="rowLines" key-field="id" ref="scroller" :style="scrollerStyle"
            :buffer="scrollerBuffer" :skip-hover="true"
            :emitUpdate="false" :page-mode="false" :prerender="0" class="p-0 m-0">

            <template v-slot="{ item, index, active }">
                <template v-if="active && !hideFromModal">
                    <GridScrollerLine :item="item" :tab="props.tab" :image-size="props.imageSize" :manager="props.manager" :properties="visibleProperties" :width="scrollerWidth"
                        :show-images="props.showImages" :row-height="rowSize"
                        :missing-width="missingWidth" @open:group="openGroup" @close:group="closeGroup"
                        @toggle:image="({ groupId, imageIndex }) => selectImage(groupId, imageIndex)" @toggle:group="selectGroup" />
                </template>
            </template>
        </RecycleScroller>
        </InstanceData>
    </div>
</template>

<style>
.grid-container {
    white-space: nowrap;
}

/* The row holding the cell being edited is raised: its editor's focus shadow is let out of the
   cell (see RowLine), and scroller items are each their own stacking context, laid out in
   recycling order, so the row below could paint over it. */
.grid-container .vue-recycle-scroller__item-view:focus-within {
    z-index: 1;
}
</style>
