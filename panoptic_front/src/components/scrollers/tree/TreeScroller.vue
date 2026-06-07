<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed, Ref, shallowRef, shallowReactive, provide, onUnmounted, triggerRef } from 'vue';
import ImageLineVue from './ImageLine.vue';
import PileLine from './PileLine.vue';
import GroupLineVue from './GroupLine.vue';
import { GroupManager, Group, GroupType, GroupIterator, ImageIterator, SelectedImages } from '@/core/GroupManager';
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
    groupManager: GroupManager,
    properties: Property[],
    hideOptions?: boolean,
    hideGroup?: boolean,
    sha1Scores?: Sha1Scores,
    hideIfModal?: boolean
    preview?: SelectedImages
    inputKey: string
}>()

const emits = defineEmits(['recommend'])

provide('inputKey', props.inputKey)

const groupIdx = {}
const imageLines = shallowRef([]) as Ref<ScrollerLine[]>

const hoverGroupBorder = ref(-1)

const scroller = ref(null)
const MARGIN_STEP = 20

const visiblePropertiesNb = computed(() => props.properties.length)
const visiblePropertiesCluster = computed(() => props.properties.filter(p => p.mode == PropertyMode.sha1))
const visiblePropertiesClusterNb = computed(() => visiblePropertiesCluster.value.length)

const maxPerLine = computed(() => Math.ceil(props.width / props.imageSize * 1.5))

const imageLineSize = computed(() => {
    let nb = visiblePropertiesNb.value
    let offset = 0
    if (nb > 0) {
        offset += 28
    }
    if (nb > 1) {
        offset += (nb - 1) * 27
    }
    return props.imageSize + offset + 10
})

const pileLineSize = computed(() => {
    let nb = visiblePropertiesClusterNb.value
    let offset = 0
    if (nb > 0) {
        offset += 28
    }
    if (nb > 1) {
        offset += (nb - 1) * 27
    }
    return props.imageSize + offset + 10
})

const simiImageLineSize = computed(() => {
    return props.imageSize + 40
})

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

    if (group.children.length > 0 && group.subGroupType != GroupType.Sha1) return lines
    if (group.view.closed) return lines

    if (group.subGroupType != GroupType.Sha1) {
        computeImageLines(it, lines, props.imageSize, props.width - (group.depth * MARGIN_STEP), group)
    } else {
        computeImagePileLines(it, lines as ScrollerPileLine[], props.imageSize, props.width - (group.depth * MARGIN_STEP), group)
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
        console.time('compute Lines')
        if (!props.groupManager.result.root) return
        let it = props.groupManager.getGroupIterator()
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
        // [grp-debug] remove once grouping render is confirmed
        const root = props.groupManager.result.root
        console.log('[grp] groupBy=', JSON.stringify(props.groupManager.state.groupBy),
            'root.children=', root?.children.length,
            'subGroupType=', root?.subGroupType,
            'rootSlots=', root?.slots.length,
            'lines=', lines.length,
            'groupLines=', lines.filter((l: any) => l.type === 'group').length,
            'imageLines=', lines.filter((l: any) => l.type === 'images').length,
            'firstChildSlots=', root?.children[0]?.slots.length)
        imageLines.value = reconcileLines(imageLines.value, lines)
        console.timeEnd('compute Lines')
    } finally {
        _computingLines = false
    }
}

function computeImageLines(it: GroupIterator, lines, imageHeight, totalWidth, parentGroup, isSimilarities = false) {
    // Empty group: no images, so emit no image line (avoids a blank/spinner row).
    if (!parentGroup.slots || parentGroup.slots.length === 0) return

    let lineWidth = totalWidth
    let newLine = []
    let actualWidth = 0
    let groupLineIndex = 0 // <-- ADD LOCAL COUNTER

    let addLine = (line) => {
        lines.push({
            id: parentGroup.id + '|img-' + groupLineIndex++, // <-- USE LOCAL COUNTER
            type: 'images',
            data: line,
            groupId: parentGroup.id,
            depth: parentGroup.depth + 1,
            size: isSimilarities ? simiImageLineSize.value : imageLineSize.value,
            isSimilarities: isSimilarities
        })
    }

    let imgIt = ImageIterator.fromGroupIterator(it)
    while (imgIt && imgIt.isValid && imgIt.groupId == it.groupId && lines.length !== undefined) {
        let imgWidth = imageHeight + 12
        if (actualWidth + imgWidth < lineWidth) {
            newLine.push(imgIt)
            actualWidth += imgWidth
            imgIt = imgIt.nextImages()
            continue
        }
        if (newLine.length == 0) {
            newLine.push(imgIt)
        }
        addLine(newLine)
        newLine = [imgIt]
        actualWidth = imgWidth

        imgIt = imgIt.nextImages()
    }

    if (newLine.length > 0) {
        addLine(newLine)
    }
}

function computeImagePileLines(it: GroupIterator, lines: ScrollerPileLine[], imageHeight, totalWidth, parentGroup) {
    // Empty sha1 group: no piles, so emit no image line.
    if (!parentGroup.children || parentGroup.children.length === 0) return

    let lineWidth = totalWidth
    let newLine: ImageIterator[] = []
    let actualWidth = 0
    let groupLineIndex = 0 // <-- ADD LOCAL COUNTER

    let addLine = (line: ImageIterator[]) => {
        lines.push({
            id: parentGroup.id + '|pile-' + groupLineIndex++, // <-- USE LOCAL COUNTER (changed to 'pile' for uniqueness)
            type: 'piles',
            data: line,
            groupId: parentGroup.id,
            depth: parentGroup.depth + 1,
            size: pileLineSize.value
        })
    }

    let imgIt = ImageIterator.fromGroupIterator(it)
    while (imgIt && imgIt.isValid && imgIt.groupId == it.groupId) {
        let imgWidth = imageHeight + 10
        if (actualWidth + imgWidth < lineWidth) {
            newLine.push(imgIt)
            actualWidth += imgWidth
            imgIt = imgIt.nextImages()
            continue
        }
        if (newLine.length == 0) {
            throw new Error('Images seems to be to big for the line')
        }
        addLine(newLine)
        newLine = [imgIt]
        actualWidth = imgWidth

        imgIt = imgIt.nextImages()
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
    return [...getParents(props.groupManager.result.index[item.groupId]), item.groupId]
}

function closeGroup(groupIds) {
    computeLines()
}

function openGroup(groupId) {
    computeLines()
}

function updateImageSelection(data: { id: number, value: boolean }, item: ImageLine) {
    const iterator = props.groupManager.findImageIterator(item.groupId, data.id)
    if (iterator) props.groupManager.toggleImageIterator(iterator, keyState.shift)
}

function toggleGroupSelect(groupId: number) {
    const iterator = props.groupManager.getGroupIterator(groupId)
    if (iterator) props.groupManager.toggleGroupIterator(iterator, keyState.shift)
}

let _triggerHandle: ReturnType<typeof setTimeout> | undefined
function triggerUpdate() {
    clearTimeout(_triggerHandle)
    _triggerHandle = setTimeout(computeLines, 50)
}


onMounted(computeLines)

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

    const newSizeOf = (l) => l.type === 'images' ? imageLineSize.value
        : l.type === 'piles' ? pileLineSize.value
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
        if (l.type === 'images') l.size = imageLineSize.value
        else if (l.type === 'piles') l.size = pileLineSize.value
    }

    imageLines.value = [...lines ]
})

let resizeWidthHandler: ReturnType<typeof setTimeout> | undefined
watch(() => props.width, () => {
    clearTimeout(resizeWidthHandler)
    resizeWidthHandler = setTimeout(computeLines, 200)
})

onMounted(() => props.groupManager.onResultChange.addListener(triggerUpdate))
onUnmounted(() => props.groupManager.onResultChange.removeListener(triggerUpdate))

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
                        :manager="props.groupManager" :hide-options="props.hideOptions"
                        :data="props.groupManager.result" @scroll="scrollTo" @hover="updateHoverBorder"
                        @unhover="hoverGroupBorder = -1" @group:close="closeGroup" @group:open="openGroup"
                        @select="toggleGroupSelect" @recommend="(groupId) => emits('recommend', groupId)" />
                </div>
                <div v-else-if="item.type == 'images'">
                    <!-- +1 on imageSize to avoid little gap. TODO: Find if there is a real fix -->
                    <ImageLineVue :image-size="props.imageSize + 1" :input-index="index * maxPerLine" :item="item"
                        :index="props.groupManager.result.index" :hover-border="hoverGroupBorder"
                        :parent-ids="getImageLineParents(item)" :properties="props.properties"
                        :selected-images="props.groupManager.selectedImages"
                        @update:selected-image="e => updateImageSelection(e, item)" @scroll="scrollTo"
                        @hover="updateHoverBorder" @unhover="hoverGroupBorder = -1" />
                </div>
                <div v-else-if="item.type == 'piles'">
                    <PileLine :image-size="props.imageSize + 1" :input-index="index * maxPerLine" :item="item"
                        :index="props.groupManager.result.index" :hover-border="hoverGroupBorder"
                        :parent-ids="getImageLineParents(item)" :properties="visiblePropertiesCluster"
                        :selected-images="props.groupManager.selectedImages" :sha1-scores="props.sha1Scores"
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
