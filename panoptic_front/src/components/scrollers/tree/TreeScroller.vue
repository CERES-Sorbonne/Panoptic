<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed, Ref, shallowRef, shallowReactive, provide, triggerRef, getCurrentInstance } from 'vue';
import ImageLineVue from './ImageLine.vue';
import PileLine from './PileLine.vue';
import GroupLineVue from './GroupLine.vue';
import { Group, SelectedImages } from '@/core/GroupManager'
import type { GroupInspector } from '@/core/group/inspector'
import { keyState } from '@/data/composables/keyState';
import { Property, Sha1Scores, PropertyMode, ModalId } from '@/data/models';
import { ScrollerLine, GroupLine, ScrollerPileLine, ImageLine } from '@/components/scrollers/types';
import { cardLineSize, lineFirstSlots, lineSlot, TreeLineCache, treeLinesBuiltKey } from './treeLines';
import { RecycleScroller } from 'vue-virtual-scroller';
import { usePanopticStore } from '@/data/stores/panopticStore';
import { useColumnStore } from '@/data/stores/columnStore'; // <-- Imported columnStore
import InstanceData from '@/components/data/InstanceData.vue';
import { usePagedLines } from '@/components/scrollers/usePagedLines';
import CellHoverTip from '@/components/scrollers/CellHoverTip.vue';
import { cellEditingKey, CellKey, useCellEditing } from '@/components/scrollers/cellEditing';
import { cellPointedKey, useCellHover } from '@/components/scrollers/cellHover';
import { adjacentCell, CellLines, revealOffset } from '@/components/scrollers/cellNavigation';
import { useDataStore } from '@/data/stores/dataStore';
import { useInstanceStore } from '@/data/stores/instanceStore';
import { cellFullText } from './cellDisplay';

const panoptic = usePanopticStore()
const columnStore = useColumnStore() // <-- Initialized store to map slots to IDs

const props = defineProps<{
    imageSize: number,
    height: number,
    width: number,
    manager: GroupInspector,
    properties: Property[],
    hideOptions?: boolean,
    hideGroup?: boolean,
    sha1Scores?: Sha1Scores,
    hideIfModal?: boolean
    preview?: SelectedImages
    // No longer read: Tab between cells walks this scroller's own lines (see navigateCell) instead
    // of inputStore's registry, which this key used to namespace. Kept so callers need no change.
    inputKey: string
}>()

const emit = defineEmits(['reco'])

// Selection namespace for descendant cells (defaults to 'global'). Sourced from
// the manager so there is a single source of truth per scroller.
provide('selectNamespace', computed(() => props.manager?.selectionNamespace ?? 'global'))

const groupIdx = {}
const imageLines = shallowRef([]) as Ref<ScrollerLine[]>

const hoverGroupBorder = ref(-1)

// The hovered group's indent borders are lit by one CSS rule written here, not by a prop handed to
// every line: as a prop, each hover in or out of a border re-rendered every line on screen (and
// every idle one the scroller keeps). The borders only carry their group id (data-border-group);
// the rule is scoped to this scroller, so the other pane's tree keeps its own borders.
const borderScope = 'tree-' + getCurrentInstance()!.uid
const hoverBorderCss = computed(() => hoverGroupBorder.value < 0 ? '' :
    `.vue-recycle-scroller[data-border-scope="${borderScope}"] [data-border-group="${hoverGroupBorder.value}"] { border-left-color: blue; }`)

const scroller = ref(null)

// The scroller only gets the lines around the viewport plus padding (see usePagedLines), so
// a huge tree does not go past the browser's height limit. imageLines stays the full list.
// Mounted beyond the viewport: one line on each side (the buffer follows the tallest line, ~330px
// for a card line with properties), at least 300px when the lines are short so a fast trackpad
// frame does not scroll into blank. It used to be 400px of scroller buffer inside an 800px window,
// and since the window was rebuilt nearly every scroll event, every line on screen re-rendered as
// often (see usePagedLines).
const paged = usePagedLines<ScrollerLine>({ scroller, viewportHeight: () => props.height, minBuffer: 300 })
const windowLines = paged.windowLines
const scrollerBuffer = paged.buffer
watch(imageLines, lines => paged.setLines(lines), { flush: 'sync' })

// Trim off the width prop: the vertical scrollbar (15) + 2px so cells don't touch it. This
// used to be 34, which happened to cover the indent the line math forgot to reserve; now that
// the indent is accounted for properly, the extra would just be wasted space on the right.
const WIDTH_OFFSET = 17

// The `width` prop is the box this scroller occupies. RecycleScroller scrolls vertically, so
// its scrollbar (plus a small margin) eats WIDTH_OFFSET px off the usable content width —
// subtract it up front so the line math matches what's actually available. No ResizeObserver:
// the prop is the single source of truth, and every per-cell size is precomputed here (never
// inside the line comps).
const contentWidth = computed(() => Math.max(0, props.width - WIDTH_OFFSET))

const visiblePropertiesNb = computed(() => props.properties.length)
const visiblePropertiesCluster = computed(() => props.properties.filter(p => p.mode == PropertyMode.sha1))
const visiblePropertiesClusterNb = computed(() => visiblePropertiesCluster.value.length)

// Row height depends on the actual rendered image size of that row (which varies per
// leaf, see treeLines.buildLeafLines), not the global imageSize prop.
function imageLineSizeFor(imgSize: number) {
    return cardLineSize(imgSize, visiblePropertiesNb.value)
}

function pileLineSizeFor(imgSize: number) {
    return cardLineSize(imgSize, visiblePropertiesClusterNb.value)
}

// ── Property cells ──────────────────────────────────────────────────────────
// The cards draw their property rows read-only (TreeCellView) and mount an editor only for the
// row being edited; which one that is lives here, per scroller. Hover on the rows is handled here
// too, once for all of them: hover-store reporting, the value tooltip, and which row gets the
// filter/copy buttons.
const data = useDataStore()
const instanceStore = useInstanceStore()

const cells = useCellEditing({ navigate: navigateCell })
provide(cellEditingKey, cells)

const cellHover = useCellHover({
    fullText: key => {
        const property = data.properties[key.propertyId]
        if (!property) return undefined
        return cellFullText(property, instanceStore.instanceData[key.instanceId]?.properties[key.propertyId], data.tags)
    }
})
provide(cellPointedKey, cellHover.pointed)

// The cells of `propertyId` in display order: every image of an image line, and every pile of a
// pile line when the property is one the piles show (see visiblePropertiesCluster).
function cellLines(propertyId: number): CellLines {
    const lines = imageLines.value
    const ids = columnStore.instanceIds()
    const host = props.manager.result
    const onPiles = visiblePropertiesCluster.value.some(p => p.id === propertyId)
    return {
        count: lines.length,
        cells: l => {
            const line = lines[l]
            if (line.type === 'images' || (line.type === 'piles' && onPiles)) return (line as ImageLine).count
            return 0
        },
        // A pile's cell is its first image's, as the card draws it (Image.vue reads `slot`).
        at: (l, i) => ({ instanceId: ids[lineSlot(host, lines[l] as ImageLine, i)], groupId: lines[l].groupId }),
    }
}

// Tab / Shift-Tab: the same property on the next / previous image, scrolled into view first.
async function navigateCell(from: CellKey, backwards: boolean): Promise<CellKey | undefined> {
    const to = adjacentCell(cellLines(from.propertyId), from, backwards, groupIdx[from.groupId] ?? 0)
    if (!to || to.cell.instanceId === undefined) return undefined
    const offset = revealOffset(paged.lineOffset(to.line), imageLines.value[to.line].size, paged.getScrollTop(), props.height)
    if (offset !== undefined) {
        // The editor being left commits on its blur: give it that now, while its card is still
        // there — the scroll can recycle it, and the popups close on scroll anyway.
        ;(document.activeElement as HTMLElement)?.blur?.()
        paged.scrollToPosition(offset)
        // Open only once the scroll has landed and the target card is drawn: an editor opened
        // before would be closed by the scroll it is waiting on.
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    }
    return { ...to.cell, propertyId: from.propertyId }
}

const hideFromModal = computed(() => props.hideIfModal && (panoptic.openModalId == ModalId.IMAGE || panoptic.openModalId == ModalId.TAG))

provide('hideImg', hideFromModal)

// ── Window-level batch registration ──────────────────────────────────────────
// All instance IDs of the rendered window are registered in one shot so the
// backend is hit with a single batched request instead of one per image cell.

const windowIds = computed(() => {
    const ids: number[] = []
    const lines = imageLines.value
    if (!lines.length) return ids

    // Clamp the window to the valid range
    const range = paged.windowRange.value
    let start = Math.max(0, Math.min(range.start, lines.length - 1))
    let end = Math.max(0, Math.min(range.end, lines.length - 1))

    // Expand backwards until 5 image/pile lines before the visible window
    let preCount = 0
    while (start > 0 && preCount < 5) {
        start--
        if (lines[start].type === 'images' || lines[start].type === 'piles') preCount++
    }

    // Expand forwards until 5 image/pile lines after the visible window
    let postCount = 0
    while (end < lines.length - 1 && postCount < 5) {
        end++
        if (lines[end].type === 'images' || lines[end].type === 'piles') postCount++
    }

    // Read off the leaves directly (a pile counts by its first image, the one its card draws):
    // no iterators for this, the lines only hold ranges.
    const host = props.manager.result
    const colIds = columnStore.instanceIds()
    const slots: number[] = []
    for (let i = start; i <= end; i++) {
        const line = lines[i]
        if (line.type === 'images' || line.type === 'piles') lineFirstSlots(host, line as ImageLine, slots)
    }
    for (const slot of slots) {
        // RESOLVE ID: map the slot to the backend instanceId
        const instanceId = colIds[slot]
        if (instanceId !== undefined && !isNaN(instanceId)) ids.push(instanceId)
    }
    return ids
})
const windowPropIds = computed(() => props.properties?.map(p => p.id) ?? [])

defineExpose({
    scrollTo,
    computeLines,
    clear
})

function clear() {
    lineCache.clear()
    imageLines.value = []
}

// Each leaf's block of image/pile lines, kept across rebuilds (see TreeLineCache for the key and
// why it needs no change signal from the tree). A rebuild walks the groups only and reuses every
// block whose leaf, sizes and properties did not change — opening or closing a group no longer
// re-lines the images of every other group.
const lineCache = new TreeLineCache()

// Bumped with every new line list; the line components re-check their iterators on it (see
// treeLinesBuiltKey).
const linesBuilt = shallowRef(0)
provide(treeLinesBuiltKey, linesBuilt)

function groupLine(group: Group): GroupLine {
    // Never reused — GroupManager rebuilds the tree with new Group objects, so reusing old line
    // objects keeps stale .data references and Vue won't update. One per group: cheap.
    return {
        id: group.id,
        type: 'group',
        data: group,
        depth: group.depth,
        size: props.hideGroup ? 0 : 30,
        nbClusters: 10
    }
}

// What the current lines were built from. A version bump the lines already reflect needs no
// second rebuild: opening/closing a group bumps the version AND rebuilds right away through the
// group:open/close handlers, so the debounced version watcher would otherwise redo the same work
// 50ms later. The manager is part of the stamp since a swapped-in manager can sit at the same
// version number as the one it replaced.
let builtVersion = -1
let builtManager: GroupInspector | undefined

// Parent-id arrays handed to the lines (see groupLineParents/getImageLineParents). The template
// asks for them on every render of the scroller slot, i.e. every time the window shifts. A fresh
// array each time is a changed prop for every line on screen, so all of them re-rendered on
// scroll; handing back the same array while the tree is unchanged lets Vue skip them. Keyed by group id ('g' = the group line's own ancestors, 'l' = an image line's, which
// adds the group itself) and emptied by computeLines, which is when the drawn tree changes.
const parentsCache = new Map<string, number[]>()

let _computingLines = false
function computeLines() {
    if (_computingLines) return
    _computingLines = true
    try {
        if (!props.manager.result.root) return
        builtVersion = props.manager.version.value
        builtManager = props.manager
        // Parent chains are read off the tree being drawn now: drop the ones of the old tree.
        parentsCache.clear()
        const host = props.manager.result
        let it = props.manager.getGroupIterator()
        if (!it?.group) {
            lineCache.clear()
            imageLines.value = []
            return
        }
        const params = {
            contentWidth: contentWidth.value,
            imageSize: props.imageSize,
            propertyCount: visiblePropertiesNb.value,
            pilePropertyCount: visiblePropertiesClusterNb.value,
        }
        const lines: ScrollerLine[] = []
        const visited = new Set<number>()
        while (it) {
            const group = it.group
            if (visited.has(group.id)) break
            visited.add(group.id)
            groupIdx[group.id] = lines.length
            lines.push(groupLine(group))
            // A group with children is a real sub-tree (piled leaves have no children); a closed
            // leaf keeps its cached block for when it reopens.
            if (group.children.length === 0 && !group.view.closed) {
                const block = lineCache.leafLines(host, group, params)
                for (let i = 0; i < block.length; i++) lines.push(block[i])
            }
            it = it.nextGroup()
        }
        lineCache.prune(host)
        linesBuilt.value++
        imageLines.value = lines
    } finally {
        _computingLines = false
    }
}

function scrollTo(groupId) {
    paged.scrollToIndex(groupIdx[groupId])
}

function updateHoverBorder(value) {
    hoverGroupBorder.value = value
}

function getParents(group: Group) {
    const ids: number[] = []
    const seen = new Set<number>()
    let current = group?.parent
    while (current != undefined && !seen.has(current.id)) {
        seen.add(current.id)
        ids.unshift(current.id)
        current = current.parent
    }
    return ids
}

function groupLineParents(group: Group) {
    const key = 'g' + group?.id
    let ids = parentsCache.get(key)
    if (!ids) parentsCache.set(key, ids = getParents(group))
    return ids
}

function getImageLineParents(item) {
    const key = 'l' + item.groupId
    let ids = parentsCache.get(key)
    if (!ids) parentsCache.set(key, ids = [...getParents(props.manager.result.index[item.groupId]), item.groupId])
    return ids
}

// The line toggled (or its children) bumped the version before emitting: rebuild now so the
// open/close is immediate, and let the stamp in computeLines turn the watcher's pass into a no-op.
function closeGroup(groupIds) {
    computeLines()
}

function openGroup(groupId) {
    computeLines()
}

function updateImageSelection(data: { id: number, value: boolean }, item: ImageLine) {
    const iterator = props.manager.findImageIterator(item.groupId, data.id)
    if (iterator) props.manager.toggleImageIterator(iterator, keyState.shift)
}

function toggleGroupSelect(groupId: number) {
    // isValid, not truthiness: getGroupIterator always returns an object, so a stale line
    // pointing at a group a rebuild removed would pass `if (iterator)` and then throw.
    const iterator = props.manager.getGroupIterator(groupId)
    if (iterator.isValid) props.manager.toggleGroupIterator(iterator, keyState.shift)
}

let _triggerHandle: ReturnType<typeof setTimeout> | undefined
function triggerUpdate() {
    clearTimeout(_triggerHandle)
    // Checked when the timer fires, not now: a rebuild that lands in between (group toggle,
    // manager swap) may already cover this bump.
    _triggerHandle = setTimeout(() => {
        if (builtManager === props.manager && builtVersion === props.manager.version.value) return
        computeLines()
    }, 50)
}


onMounted(computeLines)

// The manager prop can be swapped for a brand-new instance (e.g. re-rooting the
// tree at a different group) without its `version` changing, since a fresh manager
// starts at the same baseline version as the one it replaced. Watch the reference
// itself so the scroller content always follows which group is being shown.
watch(() => props.manager, () => {
    nextTick(computeLines)
})

watch(() => props.imageSize, () => {
    nextTick(computeLines)
})

const margin_scroll_offset = 0
// Drawn in one go, not the viewport first and the buffer lines a frame later: the buffer is one
// line each side now, so that would only move ~40% of the (read-only) rows to the next frame for
// the same total. And shrinking the window for that frame would hand the scroller two new lists,
// each re-rendering every line on screen (see usePagedLines).
watch(visiblePropertiesNb, () => {
    const lines = imageLines.value
    if (!lines.length) return

    // Snapshot current scroll position before any layout change
    const scrollPos = paged.getScrollTop() + margin_scroll_offset

    // Find the index of the item sitting at the top of the viewport
    let topItemIdx = lines.length - 1
    let cumSize = 0
    for (let i = 0; i < lines.length; i++) {
        if (cumSize + lines[i].size > scrollPos) { topItemIdx = i; break }
        cumSize += lines[i].size
    }

    // How far the viewport top was scrolled INTO the top item. Must be preserved,
    // otherwise the item's top edge gets snapped to the viewport top and the view
    // jumps by that offset (showing the previous row when sizes shrink).
    const delta = scrollPos - cumSize

    const newSizeOf = (l) => l.type === 'images' ? imageLineSizeFor(l.imageSize)
        : l.type === 'piles' ? pileLineSizeFor(l.imageSize)
            : l.size

    // Pre-compute exact pixel offset of that item in the NEW layout so we can
    // restore it in the same nextTick flush — before the browser paints.
    let newScrollPos = 0
    for (let i = 0; i < topItemIdx; i++) {
        newScrollPos += newSizeOf(lines[i])
    }

    // Re-apply the intra-item offset, scaled by this item's own size change so the
    // same content stays under the viewport top.
    const oldTopSize = lines[topItemIdx].size
    const newTopSize = newSizeOf(lines[topItemIdx])
    newScrollPos += oldTopSize > 0 ? delta * (newTopSize / oldTopSize) : delta

    // Mutate sizes on the line objects, and keep them: the line components are not
    // re-created (no blank flash). Every image/pile line drawn is one of the cache's, and the
    // cache resizes all of its blocks — closed groups' too, so they are right when reopened.
    // The new list re-measures the window synchronously.
    lineCache.resize(visiblePropertiesNb.value, visiblePropertiesClusterNb.value)

    imageLines.value = [...lines]
    paged.scrollToPosition(newScrollPos - margin_scroll_offset)
})

// Width drives per-line/per-cell sizing — recompute when it changes. The width prop is the
// single source of truth (no observer), so this fires once per real layout change.
let resizeWidthHandler: ReturnType<typeof setTimeout> | undefined
watch(contentWidth, () => {
    clearTimeout(resizeWidthHandler)
    resizeWidthHandler = setTimeout(computeLines, 200)
})

// Re-render on result change via the version tick (note §3, step 1) instead of
// the onResultChange listener. Vue stops this watch automatically on unmount.
watch(() => props.manager.version.value, triggerUpdate)

</script>

<template>
    <InstanceData :instance-ids="windowIds" :prop-ids="windowPropIds">
        <!-- skip-hover: nothing reads the scroller's own `hover` class, and setting it re-rendered
             the scroller's whole pool each time the pointer crossed into another line. -->
        <RecycleScroller :items="windowLines" key-field="id" ref="scroller" :style="'height: ' + props.height + 'px;'"
            :buffer="scrollerBuffer" :min-item-size="0" :page-mode="false" :skip-hover="true"
            :prerender="0" :data-border-scope="borderScope" v-on="cellHover.listeners">
            <template v-slot="{ item, index, active }">
                <!-- Only the views in use: an idle one (kept by the scroller for a later line) would
                     otherwise keep its last line mounted, off screen, and re-render it on every
                     change it reads — properties, the tree version, the image size. -->
                <template v-if="active">
                    <!-- <DynamicScrollerItem :item="item" :active="active" :data-index="index" :size-dependencies="[item.size]"> -->
                    <div v-if="item.type == 'group' && !props.hideGroup">
                        <GroupLineVue :item="(item as GroupLine)" :parent-ids="groupLineParents(item.data)"
                            :manager="props.manager" :hide-options="props.hideOptions" :data="props.manager.result"
                            @scroll="scrollTo" @hover="updateHoverBorder" @unhover="hoverGroupBorder = -1"
                            @group:close="closeGroup" @group:open="openGroup" @select="toggleGroupSelect"
                            @reco="emit('reco', $event)" />
                    </div>
                    <div v-else-if="item.type == 'images'">
                        <ImageLineVue :image-size="(item as ImageLine).imageSize" :item="(item as ImageLine)"
                            :result="props.manager.result"
                            :parent-ids="getImageLineParents(item)" :properties="props.properties"
                            @update:selected-image="e => updateImageSelection(e, (item as ImageLine))" @scroll="scrollTo"
                            @hover="updateHoverBorder" @unhover="hoverGroupBorder = -1" />
                    </div>
                    <div v-else-if="item.type == 'piles'">
                        <PileLine :image-size="(item as ScrollerPileLine).imageSize" :item="(item as ScrollerPileLine)"
                            :result="props.manager.result"
                            :parent-ids="getImageLineParents(item)" :properties="visiblePropertiesCluster"
                            :sha1-scores="props.sha1Scores" :preview="props.preview"
                            @update:selected-image="e => updateImageSelection(e, (item as ImageLine))" @scroll="scrollTo"
                            @hover="updateHoverBorder" @unhover="hoverGroupBorder = -1" />
                    </div>
                    <div v-else-if="item.type == 'filler'">
                        <div :style="{ height: item.size + 'px' }" class=""></div>
                    </div>
                </template>
                <!-- </DynamicScrollerItem> -->
            </template>
        </RecycleScroller>
    </InstanceData>
    <CellHoverTip :tip="cellHover.tip.value" @hide="cellHover.hideTip" />
    <component :is="'style'" v-if="hoverBorderCss">{{ hoverBorderCss }}</component>
</template>

<style scoped>
.text-div {
    position: absolute;
    z-index: 900;
    background-color: wheat;
    top: 100px;
}
</style>
