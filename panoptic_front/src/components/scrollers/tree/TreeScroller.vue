<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed, Ref, shallowRef, shallowReactive, provide, triggerRef } from 'vue';
import ImageLineVue from './ImageLine.vue';
import PileLine from './PileLine.vue';
import GroupLineVue from './GroupLine.vue';
import { Group, GroupIterator, ImageIterator, SelectedImages } from '@/core/GroupManager'
import type { GroupInspector } from '@/core/group/inspector'
import { keyState } from '@/data/keyState';
import { Property, Sha1Scores, ScrollerLine, PropertyMode, GroupLine, ScrollerPileLine, ImageLine, ModalId } from '@/data/models';
import { RecycleScroller } from 'vue-virtual-scroller';
import { usePanopticStore } from '@/data/panopticStore';
import { useColumnStore } from '@/data/columnStore'; // <-- Imported columnStore
import InstanceData from '@/components/data/InstanceData.vue';

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
    inputKey: string
}>()

const emit = defineEmits(['reco'])

provide('inputKey', props.inputKey)
// Selection namespace for descendant cells (defaults to 'global'). Sourced from
// the manager so there is a single source of truth per scroller.
provide('selectNamespace', computed(() => props.manager?.selectionNamespace ?? 'global'))

const groupIdx = {}
const imageLines = shallowRef([]) as Ref<ScrollerLine[]>

const hoverGroupBorder = ref(-1)

const scroller = ref(null)
const MARGIN_STEP = 20
const GAP = 8 // must match the "me-2" margin applied to Image/PileLine cells
const BORDER = 2 // Image.vue's .full-container 1px border on each side, added on top of its width style
const WIDTH_OFFSET = 32 // trim off the width prop (vertical scrollbar + a little breathing room)

// The `width` prop is the box this scroller occupies. RecycleScroller scrolls vertically, so
// its scrollbar (plus a small margin) eats WIDTH_OFFSET px off the usable content width —
// subtract it up front so the line math matches what's actually available. No ResizeObserver:
// the prop is the single source of truth, and every per-cell size is precomputed here (never
// inside the line comps).
const contentWidth = computed(() => Math.max(0, props.width - WIDTH_OFFSET))

const visiblePropertiesNb = computed(() => props.properties.length)
const visiblePropertiesCluster = computed(() => props.properties.filter(p => p.mode == PropertyMode.sha1))
const visiblePropertiesClusterNb = computed(() => visiblePropertiesCluster.value.length)

const maxPerLine = computed(() => Math.ceil(contentWidth.value / props.imageSize * 1.5))

// Row height depends on the actual rendered image size of that row (which varies per
// line, see computeImageLines/computeImagePileLines), not the global imageSize prop.
function imageLineSizeFor(imgSize: number) {
    let nb = visiblePropertiesNb.value
    let offset = 0
    if (nb > 0) {
        offset += 28
    }
    if (nb > 1) {
        offset += (nb - 1) * 27
    }
    return imgSize + offset + 10
}

function pileLineSizeFor(imgSize: number) {
    let nb = visiblePropertiesClusterNb.value
    let offset = 0
    if (nb > 0) {
        offset += 28
    }
    if (nb > 1) {
        offset += (nb - 1) * 27
    }
    return imgSize + offset + 10
}

function simiImageLineSizeFor(imgSize: number) {
    return imgSize + 40
}

const hideFromModal = computed(() => props.hideIfModal && (panoptic.openModalId == ModalId.IMAGE || panoptic.openModalId == ModalId.TAG))

provide('hideImg', hideFromModal)

// ── Window-level batch registration ──────────────────────────────────────────
// RecycleScroller reports which items are active via @update(startIndex, endIndex).
// We derive all instance IDs in that window and register them in one shot so the
// backend is hit with a single batched request instead of one per image cell.

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

    // Clamp reported indices to valid range
    let start = Math.max(0, Math.min(windowStart.value, lines.length - 1))
    let end   = Math.max(0, Math.min(windowEnd.value,   lines.length - 1))

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

    for (let i = start; i <= end; i++) {
        const line = lines[i]
        if (line.type === 'images' || line.type === 'piles') {
            for (const it of (line as ImageLine).data) {
                // <-- RESOLVE ID: Map the iterator's slot to the backend instanceId
                const instanceId = columnStore.instanceIds()[it.slot]
                if (instanceId !== undefined && !isNaN(instanceId)) {
                    ids.push(instanceId)
                }
            }
        }
    }
    return ids
})
const windowPropIds = computed(() => props.properties?.map(p => p.id)??[])

defineExpose({
    scrollTo,
    computeLines,
    clear
})

function clear() {
    imageLines.value = []
}

function GroupToLines(it: GroupIterator) {
    const lines: Array<GroupLine | ScrollerPileLine> = []
    const group = it.group
    lines.push({
        id: group.id,
        type: 'group',
        data: group,
        depth: group.depth,
        size: props.hideGroup ? 0 : 30,
        nbClusters: 10
    })

    // A group with children is a real sub-tree; piled leaves have no children.
    if (group.children.length > 0) return lines
    if (group.view.closed) return lines

    const availableWidth = contentWidth.value - (group.depth * MARGIN_STEP)
    const piled = props.manager.result.pileIndex.has(group.id)
    if (!piled) {
        computeImageLines(it, lines, props.imageSize, availableWidth, group)
    } else {
        computeImagePileLines(it, lines as ScrollerPileLine[], props.imageSize, availableWidth, group)
    }

    return lines
}

// Two lines are interchangeable when rendering them produces the same DOM. When that
// holds we keep the PREVIOUS line object so its `:item` reference stays stable and the
// child component (and its images) is not re-rendered — this is what stops the flash.
function sameLine(a: ScrollerLine, b: ScrollerLine): boolean {
    if (!a || a.type !== b.type || a.size !== b.size || (a as any).depth !== (b as any).depth) return false
    if (b.type === 'group') {
        // Never reuse group lines — GroupManager rebuilds the tree with new Group objects,
        // so reusing old line objects keeps stale .data references and Vue won't update.
        return false
    }
    if (b.type === 'images' || b.type === 'piles') {
        const ad = (a as ImageLine).data, bd = (b as ImageLine).data
        if (ad.length !== bd.length) return false
        for (let i = 0; i < ad.length; i++) {
            if (ad[i].slot !== bd[i].slot) return false
        }
        return true
    }
    return false
}

// Reuse unchanged line objects (matched by id) so RecycleScroller and the line components
// keep their existing instances/DOM; only new or changed lines get fresh objects.
function reconcileLines(prev: ScrollerLine[], next: ScrollerLine[]): ScrollerLine[] {
    if (!prev.length) return next
    const byId = new Map<any, ScrollerLine>()
    for (const l of prev) byId.set(l.id, l)
    for (let i = 0; i < next.length; i++) {
        const old = byId.get(next[i].id)
        if (old && sameLine(old, next[i])) next[i] = old
    }
    return next
}

let _computingLines = false
function computeLines() {
    if (_computingLines) return
    _computingLines = true
    try {
        if (!props.manager.result.root) return
        let it = props.manager.getGroupIterator()
        if (!it?.group) {
            imageLines.value = []
            return
        }
        const lines = []
        const visited = new Set<number>()
        while (it) {
            const group = it.group
            if (visited.has(group.id)) break
            visited.add(group.id)
            groupIdx[group.id] = lines.length
            const gl = GroupToLines(it)
            for (let i = 0; i < gl.length; i++) lines.push(gl[i])
            it = it.nextGroup()
        }
        imageLines.value = reconcileLines(imageLines.value, lines)
    } finally {
        _computingLines = false
    }
}

// Per-cell widths that exactly fill a line: flooring the cell size leaves up to
// (itemsPerLine - 1) leftover px at the line end, so hand those out 1px at a time to the
// leading columns. The distribution depends only on lineWidth/itemsPerLine (constant across
// a group's lines), so grid columns stay aligned line-to-line and the line comps do no math.
function fillWidths(lineWidth: number, itemsPerLine: number): { lineImgSize: number, cardWidths: number[] } {
    const cardArea = lineWidth - GAP * (itemsPerLine - 1) // px available for cell OUTER widths
    const baseOuter = Math.floor(cardArea / itemsPerLine)
    const extraCount = cardArea - baseOuter * itemsPerLine
    const lineImgSize = Math.max(1, baseOuter - BORDER)
    const cardWidths: number[] = []
    for (let c = 0; c < itemsPerLine; c++) cardWidths.push(lineImgSize + (c < extraCount ? 1 : 0))
    return { lineImgSize, cardWidths }
}

function computeImageLines(it: GroupIterator, lines, imageHeight, totalWidth, parentGroup, isSimilarities = false) {
    // Empty group: no images, so emit no image line (avoids a blank/spinner row).
    if (!parentGroup.slots || parentGroup.slots.length === 0) return

    // imageHeight only decides how many images fit in a line...
    const lineWidth = totalWidth
    const itemsPerLine = Math.max(1, Math.floor(lineWidth / (imageHeight + BORDER + GAP)))
    // ...then images are stretched to exactly fill a FULL line. Every line uses these same
    // widths — a trailing/partial line (end of group, small group) keeps them too instead of
    // blowing its images up to fill the leftover space; the empty slots are simulated
    // (reserved, not rendered) so alignment across lines stays consistent.
    const { lineImgSize, cardWidths } = fillWidths(lineWidth, itemsPerLine)
    let groupLineIndex = 0

    let addLine = (line: ImageIterator[]) => {
        lines.push({
            id: parentGroup.id + '|img-' + groupLineIndex++,
            type: 'images',
            data: line,
            groupId: parentGroup.id,
            depth: parentGroup.depth + 1,
            imageSize: lineImgSize,
            emptyCount: itemsPerLine - line.length,
            cardWidths,
            size: isSimilarities ? simiImageLineSizeFor(lineImgSize) : imageLineSizeFor(lineImgSize),
            isSimilarities: isSimilarities
        })
    }

    let newLine: ImageIterator[] = []
    let imgIt = ImageIterator.fromGroupIterator(it)
    while (imgIt && imgIt.isValid && imgIt.groupId == it.groupId) {
        newLine.push(imgIt)
        imgIt = imgIt.nextImages()
        if (newLine.length >= itemsPerLine) {
            addLine(newLine)
            newLine = []
        }
    }

    if (newLine.length > 0) {
        addLine(newLine)
    }
}

function computeImagePileLines(it: GroupIterator, lines: ScrollerPileLine[], imageHeight, totalWidth, parentGroup) {
    // Empty leaf: no piles, so emit no image line.
    if (!parentGroup.slots || parentGroup.slots.length === 0) return

    const lineWidth = totalWidth
    const itemsPerLine = Math.max(1, Math.floor(lineWidth / (imageHeight + BORDER + GAP)))
    const { lineImgSize, cardWidths } = fillWidths(lineWidth, itemsPerLine)
    let groupLineIndex = 0

    let addLine = (line: ImageIterator[]) => {
        lines.push({
            id: parentGroup.id + '|pile-' + groupLineIndex++,
            type: 'piles',
            data: line,
            groupId: parentGroup.id,
            depth: parentGroup.depth + 1,
            imageSize: lineImgSize,
            emptyCount: itemsPerLine - line.length,
            cardWidths,
            size: pileLineSizeFor(lineImgSize)
        })
    }

    let newLine: ImageIterator[] = []
    let imgIt = ImageIterator.fromGroupIterator(it)
    while (imgIt && imgIt.isValid && imgIt.groupId == it.groupId) {
        newLine.push(imgIt)
        imgIt = imgIt.nextImages()
        if (newLine.length >= itemsPerLine) {
            addLine(newLine)
            newLine = []
        }
    }

    if (newLine.length > 0) {
        addLine(newLine)
    }
}

function scrollTo(groupId) {
    const idx = groupIdx[groupId]
    scroller.value.scrollToItem(idx)
    nextTick(() => scroller.value.updateVisibleItems(true))
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

function getImageLineParents(item) {
    return [...getParents(props.manager.result.index[item.groupId]), item.groupId]
}

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
    const iterator = props.manager.getGroupIterator(groupId)
    if (iterator) props.manager.toggleGroupIterator(iterator, keyState.shift)
}

let _triggerHandle: ReturnType<typeof setTimeout> | undefined
function triggerUpdate() {
    clearTimeout(_triggerHandle)
    _triggerHandle = setTimeout(computeLines, 50)
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
watch(visiblePropertiesNb, () => {
    const lines = imageLines.value
    if (!lines.length) return

    // Snapshot current scroll position before any layout change
    const scrollPos = scroller.value.getScroll().start + margin_scroll_offset

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

    // Set scroll first so that when z's watcher fires pe(false) it reads the
    // correct scrollTop and positions items at the right offset immediately.
    scroller.value.$el.scrollTop = newScrollPos - margin_scroll_offset

    // Mutate sizes on the reactive line objects. Because RecycleScroller's
    // accumulator (z) is a computed that reads item.size, these mutations mark
    // z dirty. RecycleScroller's own q(z, ...) watcher then calls pe(false).
    // pe(false) skips Oe() when the visible range is stable — no full pool
    // reset, no LIFO slot scramble, no sha1 changes, no blank flash.
    for (const l of lines) {
        if (l.type === 'images') l.size = imageLineSizeFor(l.imageSize)
        else if (l.type === 'piles') l.size = pileLineSizeFor(l.imageSize)
    }

    imageLines.value = [...lines ]
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
    <RecycleScroller :items="imageLines" key-field="id" ref="scroller" :style="'height: ' + props.height + 'px;'"
        :buffer="400" :min-item-size="0" :emitUpdate="true" @update="onScrollerUpdate" :page-mode="false" :prerender="0">
        <template v-slot="{ item, index, active }">
            <template v-if="true">
                <!-- <DynamicScrollerItem :item="item" :active="active" :data-index="index" :size-dependencies="[item.size]"> -->
                <div v-if="item.type == 'group' && !props.hideGroup">
                    <GroupLineVue :item="item" :hover-border="hoverGroupBorder" :parent-ids="getParents(item.data)"
                        :manager="props.manager" :hide-options="props.hideOptions"
                        :data="props.manager.result" @scroll="scrollTo" @hover="updateHoverBorder"
                        @unhover="hoverGroupBorder = -1" @group:close="closeGroup" @group:open="openGroup"
                        @select="toggleGroupSelect" @reco="emit('reco', $event)" />
                </div>
                <div v-else-if="item.type == 'images'">
                    <ImageLineVue :image-size="item.imageSize" :input-index="index * maxPerLine" :item="item"
                        :index="props.manager.result.index" :hover-border="hoverGroupBorder"
                        :parent-ids="getImageLineParents(item)" :properties="props.properties"
                        @update:selected-image="e => updateImageSelection(e, item)" @scroll="scrollTo"
                        @hover="updateHoverBorder" @unhover="hoverGroupBorder = -1" />
                </div>
                <div v-else-if="item.type == 'piles'">
                    <PileLine :image-size="item.imageSize" :input-index="index * maxPerLine" :item="item"
                        :index="props.manager.result.index" :hover-border="hoverGroupBorder"
                        :parent-ids="getImageLineParents(item)" :properties="visiblePropertiesCluster"
                        :sha1-scores="props.sha1Scores"
                        :preview="props.preview" @update:selected-image="e => updateImageSelection(e, item)"
                        @scroll="scrollTo" @hover="updateHoverBorder" @unhover="hoverGroupBorder = -1"
                        />
                </div>
                <div v-else-if="item.type == 'filler'">
                    <div :style="{ height: item.size + 'px' }" class=""></div>
                </div>
            </template>
            <!-- </DynamicScrollerItem> -->
        </template>
    </RecycleScroller>
    </InstanceData>
</template>

<style scoped>
.text-div {
    position: absolute;
    z-index: 900;
    background-color: wheat;
    top: 100px;
}
</style>
