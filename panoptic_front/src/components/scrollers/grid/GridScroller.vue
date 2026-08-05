<script setup lang="ts">
// import RecycleScroller from '@/components/Scroller/src/components/RecycleScroller.vue';
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import TableHeader from './TableHeader.vue';
import { keyState } from '@/data/keyState';
import { Group} from '@/core/GroupManager'
import type { GroupInspector } from '@/core/group/inspector'
import { Property, GroupLine, RowLine, PileRowLine, ScrollerLine, ModalId, PropertyMode } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import GridScrollerLine from './GridScrollerLine.vue';
import {RecycleScroller} from 'vue-virtual-scroller';
import { usePanopticStore } from '@/data/panopticStore';
import { useColumnStore } from '@/data/columnStore';
import { TabManager } from '@/core/TabManager';
import InstanceData from '@/components/data/InstanceData.vue';

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
// Only the visible window slice + at most two spacers — never the full dataset.
const rowLines = ref([])
const lineSizes: { [id: string]: number } = {}
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

// ── non-reactive master list + cumulative-size index ──────────────────────────
let dataLines: ScrollerLine[] = []
let cumSizes: number[] = []   // cumSizes[i] = total height of dataLines[0..i-1]

function buildCumSizes() {
    const n = dataLines.length
    cumSizes = new Array(n + 1)
    cumSizes[0] = 0
    for (let i = 0; i < n; i++) cumSizes[i + 1] = cumSizes[i] + dataLines[i].size
}

// Binary search: index of the item whose row contains pixel offset `px`.
function itemAtPixel(px: number): number {
    if (px <= 0 || !dataLines.length) return 0
    let lo = 0, hi = dataLines.length - 1
    while (lo < hi) {
        const mid = (lo + hi) >> 1
        if (cumSizes[mid + 1] <= px) lo = mid + 1
        else hi = mid
    }
    return lo
}

// Extra pixels rendered above and below the viewport.
const BUFFER_PX = 800

let _winStart = -1
let _winEnd   = -1
let currentScrollTop = 0

function rebuildWindow() {
    if (!dataLines.length) { rowLines.value = []; return }

    const start = Math.max(0, itemAtPixel(currentScrollTop - BUFFER_PX))
    const end   = Math.min(dataLines.length - 1, itemAtPixel(currentScrollTop + scrollerHeight.value + BUFFER_PX))

    if (start === _winStart && end === _winEnd) return
    _winStart = start
    _winEnd   = end

    const topH    = cumSizes[start]
    const totalH  = cumSizes[dataLines.length]
    const bottomH = totalH - cumSizes[end + 1]

    const items: ScrollerLine[] = []
    if (topH    > 0) items.push({ id: '__top__',    type: 'fillter', size: topH, data: null })
    for (let i = start; i <= end; i++) items.push(dataLines[i])
    if (bottomH > 0) items.push({ id: '__bottom__', type: 'fillter', size: bottomH, data: null })

    rowLines.value = items
}

function onScroll(event: Event) {
    currentScrollTop = (event.target as HTMLElement).scrollTop
    rebuildWindow()
}

// ── line construction ─────────────────────────────────────────────────────────

function computeLines() {
    if (!props.manager.result.root) return
    const lines: ScrollerLine[] = []
    const ids = columnStore.instanceIds()
    const defaultSize = props.showImages ? props.imageSize + 4 : 28

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

        if (group.view.closed || !group.slots.length) return

        const pile = props.manager.result.pileIndex.get(group.id)
        if (!pile) {
            for (let i = 0; i < group.slots.length; i++) {
                const instanceId = ids[group.slots[i]]
                lines.push({
                    id: group.id + '-img:' + instanceId,
                    data: { id: instanceId, imageUrl: '' },
                    type: 'image',
                    size: lineSizes[instanceId] ?? defaultSize,
                    index: i,
                    groupId: group.id,
                } as RowLine)
            }
        } else {
            const pileCount = pile.bounds.length - 1
            for (let i = 0; i < pileCount; i++) {
                const slots = pile.order.slice(pile.bounds[i], pile.bounds[i + 1])
                const firstId = ids[slots[0]]
                lines.push({
                    id: group.id + '-sha1:' + firstId,
                    data: { groupId: group.id, pileIndex: i, slots },
                    type: 'pile',
                    size: lineSizes[firstId] ?? defaultSize,
                } as PileRowLine)
            }
        }
    }

    visit(props.manager.result.root)
    lines.push({ id: '__filler__', type: 'fillter', size: 300, index: lines.length, data: null })

    dataLines = lines
    buildCumSizes()

    // Preserve current scroll position across rebuilds.
    currentScrollTop = scroller.value?.getScroll()?.start ?? 0
    _winStart = -1
    _winEnd   = -1
    rebuildWindow()
}

function resizeHeight(item: ScrollerLine, h: number) {
    if (item.size == h) return
    item.size = h   // reactive via Proxy — RecycleScroller updates automatically
    if (item.type == 'image') {
        lineSizes[(item as RowLine).data.id] = h
    } else if (item.type == 'pile') {
        const firstId = columnStore.instanceIds()[(item as PileRowLine).data.slots[0]]
        if (firstId !== undefined) lineSizes[firstId] = h
    }
    // Cumulative sizes changed; update lookup for the next scroll event.
    buildCumSizes()
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
    // console.log(groupId, imageIndex)
    const iterator = props.manager.getImageIterator(groupId, imageIndex)
    props.manager.toggleImageIterator(iterator, keyState.shift)
    // props..toggleImageIterator(iterator, keyState.shift)
}

function selectGroup(groupId: number) {
    const iterator = props.manager.getGroupIterator(groupId)
    props.manager.toggleGroupIterator(iterator, keyState.shift)
}

function clear() {
    dataLines = []
    cumSizes  = []
    _winStart = -1
    _winEnd   = -1
    rowLines.value = []
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
    props.manager.clearCustomGroups(true)
    const el = scroller.value?.$el as HTMLElement | undefined
    el?.addEventListener('scroll', onScroll, { passive: true })
    if (el) {
        scrollbarObserver = new ResizeObserver(measureScrollbar)
        scrollbarObserver.observe(el)
    }
    measureScrollbar()
})

onUnmounted(() => {
    scroller.value?.$el?.removeEventListener('scroll', onScroll)
    scrollbarObserver?.disconnect()
})

// The scrollbar appears/disappears as content grows or shrinks.
watch(rowLines, () => nextTick(measureScrollbar))

watch(() => props.imageSize, (now) => {
    if (!dataLines.length) return
    const scrollPos = scroller.value?.getScroll()?.start ?? 0

    // Find the item at the top of the viewport so we can restore position.
    let topIdx = 0
    let acc = 0
    for (let i = 0; i < dataLines.length; i++) {
        if (acc + dataLines[i].size > scrollPos) { topIdx = i; break }
        acc += dataLines[i].size
    }

    // Resize all non-visible items (visible ones will be resized via resizeHeight events).
    const visibleIds = new Set(rowLines.value.map((l: any) => l.id))
    dataLines.forEach(l => {
        if (!visibleIds.has(l.id) && (l.type === 'image' || l.type === 'pile')) l.size = now + 4
    })

    buildCumSizes()

    let newScrollPos = 0
    for (let i = 0; i < topIdx; i++) newScrollPos += dataLines[i].size
    scroller.value?.scrollToPosition(newScrollPos)

    currentScrollTop = newScrollPos
    _winStart = -1
    _winEnd   = -1
    rebuildWindow()
})

</script>

<template>
    <div class="grid-container overflow-hidden" :style="{ width: scrollerStyle.width }">
        <TableHeader :tab="props.tab" :image-size="props.imageSize" :manager="props.manager" :properties="visibleProperties" :missing-width="missingWidth"
            :show-image="props.showImages" :current-group="currentGroup" class="p-0 m-0" />

        <InstanceData :instance-ids="windowIds" :prop-ids="windowPropIds">
        <RecycleScroller :items="rowLines" key-field="id" ref="scroller" :style="scrollerStyle"
            :emitUpdate="false" :page-mode="false" :prerender="0" class="p-0 m-0">

            <template v-slot="{ item, index, active }">
                <template v-if="active && !hideFromModal">
                    <GridScrollerLine :item="item" :tab="props.tab" :image-size="props.imageSize" :manager="props.manager" :properties="visibleProperties" :width="scrollerWidth"
                        :show-images="props.showImages"
                        :missing-width="missingWidth" @open:group="openGroup" @close:group="closeGroup"
                        @toggle:image="({ groupId, imageIndex }) => selectImage(groupId, imageIndex)" @toggle:group="selectGroup"
                        @resizeHeight="h => resizeHeight(item, h)" />
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
</style>
