<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed, shallowRef, provide, getCurrentInstance } from 'vue';
import ImageLineVue from './ImageLine.vue';
import PileLine from './PileLine.vue';
import GroupLineVue from './GroupLine.vue';
import { Group, SelectedImages } from '@/core/GroupManager'
import type { GroupInspector } from '@/core/group/inspector'
import { keyState } from '@/data/composables/keyState';
import { Property, Sha1Scores, PropertyMode, ModalId } from '@/data/models';
import { GroupLine, ImageLine } from '@/components/scrollers/types';
import {
    GROUP_LINE_SIZE, TreeGeometry, type TreeLineParams, leafLine, lineFirstSlots, treeCellWalk, treeLinesBuiltKey, treeSource,
} from './treeLines';
import { usePanopticStore } from '@/data/stores/panopticStore';
import { useColumnStore } from '@/data/stores/columnStore';
import InstanceData from '@/components/data/InstanceData.vue';
import VirtualScroller from '@/components/scrollers/virtual/VirtualScroller.vue';
import { ScrollLayout, lineKey } from '@/components/scrollers/virtual/scrollLayout';
import type { LineRef } from '@/components/scrollers/virtual/scrollLayout';
import type { ViewRange } from '@/components/scrollers/virtual/virtualView';
import CellHoverTip from '@/components/scrollers/CellHoverTip.vue';
import { cellEditingKey, CellKey, useCellEditing } from '@/components/scrollers/cellEditing';
import { cellPointedKey, useCellHover } from '@/components/scrollers/cellHover';
import { adjacentCellIn, revealOffset } from '@/components/scrollers/cellNavigation';
import { useDataStore } from '@/data/stores/dataStore';
import { useInstanceStore } from '@/data/stores/instanceStore';
import { cellFullText } from './cellDisplay';

const panoptic = usePanopticStore()
const columnStore = useColumnStore()

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

const hoverGroupBorder = ref(-1)

// The hovered group's indent borders are lit by one CSS rule written here, not by a prop handed to
// every line: as a prop, each hover in or out of a border re-rendered every line on screen. The
// borders only carry their group id (data-border-group); the rule is scoped to this scroller, so
// the other pane's tree keeps its own borders.
const borderScope = 'tree-' + getCurrentInstance()!.uid
const hoverBorderCss = computed(() => hoverGroupBorder.value < 0 ? '' :
    `.vscroller[data-border-scope="${borderScope}"] [data-border-group="${hoverGroupBorder.value}"] { border-left-color: blue; }`)

// Trim off the width prop: the vertical scrollbar (15) + 2px so cells don't touch it.
const WIDTH_OFFSET = 17

// The `width` prop is the box this scroller occupies; its scrollbar (plus a small margin) eats
// WIDTH_OFFSET px off the usable content width. No ResizeObserver: the prop is the single source of
// truth, and every per-cell size is precomputed here (never inside the line comps).
const contentWidth = computed(() => Math.max(0, props.width - WIDTH_OFFSET))

const visiblePropertiesNb = computed(() => props.properties.length)
const visiblePropertiesCluster = computed(() => props.properties.filter(p => p.mode == PropertyMode.sha1))
const visiblePropertiesClusterNb = computed(() => visiblePropertiesCluster.value.length)

// ── Layout ──────────────────────────────────────────────────────────────────
// The tree is handed to the VirtualScroller as it is (treeSource): a leaf's line count is a
// division, and a line object is only made for the lines on screen (lineItem). Nothing here is
// built per image or per line of the whole tree.
function lineParams(): TreeLineParams {
    return {
        contentWidth: contentWidth.value,
        imageSize: props.imageSize,
        propertyCount: visiblePropertiesNb.value,
        pilePropertyCount: visiblePropertiesClusterNb.value,
    }
}
const geometry = new TreeGeometry(lineParams())
const layout = new ScrollLayout(treeSource(() => props.manager.result, geometry, () => !!props.hideGroup))
const vs = ref<InstanceType<typeof VirtualScroller>>()

// Bumped each time the tree is read again; the line components re-check their iterators on it
// (see treeLinesBuiltKey).
const linesBuilt = shallowRef(0)
provide(treeLinesBuiltKey, linesBuilt)

// The line objects handed to the line components, by line key: handed back while they come out
// the same, so a line component whose line did not change is not re-rendered. Only lines that were
// on screen are here; the map is emptied when it grows past what a screen ever shows.
const items = new Map<string, GroupLine | ImageLine>()
function remember<T extends GroupLine | ImageLine>(key: string, item: T): T {
    if (items.size > 2000 && !items.has(key)) items.clear()
    items.set(key, item)
    return item
}

function groupItem(line: LineRef): GroupLine | undefined {
    const group = props.manager.result.index[line.node]
    if (!group) return undefined
    const key = lineKey(line)
    const old = items.get(key) as GroupLine | undefined
    // GroupManager rebuilds the tree with new Group objects: a line holding the old one is stale.
    if (old && old.data === group && old.depth === group.depth) return old
    return remember(key, { id: group.id, type: 'group', data: group, depth: group.depth, size: GROUP_LINE_SIZE, nbClusters: 10 })
}

function imageItem(line: LineRef): ImageLine | undefined {
    const key = lineKey(line)
    const item = leafLine(props.manager.result, line.node, line.index, geometry, items.get(key) as ImageLine | undefined)
    return item && remember(key, item)
}

// What the layout was last read from: a version bump with the same tree (an open/close, already
// applied by openGroup/closeGroup) needs no rebuild, only a refresh.
let builtResult: unknown
let builtRev = -1
let builtVersion = -1

/**
 * Reads the tree again. A new tree (another result, or a structural change: `rev`) is rebuilt;
 * the same tree is refreshed — open states, line counts and sizes, O(groups) either way.
 */
function computeLines(force = true) {
    const result = props.manager.result
    geometry.setParams(lineParams())
    if (force || result !== builtResult || result.rev !== builtRev) layout.rebuild()
    else layout.refresh()
    builtResult = result
    builtRev = result.rev
    builtVersion = props.manager.version.value
    linesBuilt.value++
    // Group lines hold their Group object, and a leaf's lines their counts: let every mounted line
    // check its item (unchanged ones come back the same, and their component is not re-rendered).
    vs.value?.relayout({ rerender: true })
}

function clear() {
    items.clear()
    builtResult = undefined
    layout.clear()
    vs.value?.relayout({ rerender: true })
}

// The line toggled (or its children) bumped the version before emitting: apply it to the layout
// right away — only those groups, O(depth · log siblings) each — and stamp the version so the
// version watcher has nothing left to do.
function onToggled(groupIds: number | number[]) {
    const ids = Array.isArray(groupIds) ? groupIds : [groupIds]
    const result = props.manager.result
    if (result !== builtResult || result.rev !== builtRev) return computeLines(false)
    for (const id of ids) layout.refreshNode(id)
    builtVersion = props.manager.version.value
    vs.value?.relayout()
}

function scrollTo(groupId: number) {
    vs.value?.scrollTo(groupId)
}

function updateHoverBorder(value) {
    hoverGroupBorder.value = value
}

// ── Parent chains (the indent borders) ───────────────────────────────────────
// A new array is a changed prop for the line: handed back the same one while the chain is the
// same, so a rebuild does not re-render every line on screen for its borders.
const parentsCache = new Map<string, number[]>()

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

function cachedChain(key: string, ids: number[]): number[] {
    const old = parentsCache.get(key)
    if (old && old.length === ids.length && old.every((v, i) => v === ids[i])) return old
    if (parentsCache.size > 2000) parentsCache.clear()
    parentsCache.set(key, ids)
    return ids
}

function groupLineParents(group: Group) {
    return cachedChain('g' + group?.id, getParents(group))
}

function imageLineParents(groupId: number) {
    return cachedChain('l' + groupId, [...getParents(props.manager.result.index[groupId]), groupId])
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

// The cells of `propertyId` in display order (see treeCellWalk).
function cellWalk(propertyId: number) {
    const onPiles = visiblePropertiesCluster.value.some(p => p.id === propertyId)
    return treeCellWalk(props.manager.result, layout, geometry, columnStore.instanceIds(), onPiles)
}

// Tab / Shift-Tab: the same property on the next / previous image, scrolled into view first.
async function navigateCell(from: CellKey, backwards: boolean): Promise<CellKey | undefined> {
    const to = adjacentCellIn(cellWalk(from.propertyId), from, backwards)
    if (!to || to.cell.instanceId === undefined || !vs.value) return undefined
    const offset = revealOffset(layout.offsetOf(to.line), layout.sizeOf(to.line), vs.value.scrollTop(), props.height)
    if (offset !== undefined) {
        // The editor being left commits on its blur: give it that now, while its card is still
        // there — the scroll can recycle it, and the popups close on scroll anyway.
        ;(document.activeElement as HTMLElement)?.blur?.()
        vs.value.scrollToOffset(offset)
        // Open only once the scroll has landed and the target card is drawn: an editor opened
        // before would be closed by the scroll it is waiting on.
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    }
    return { ...to.cell, propertyId: from.propertyId }
}

const hideFromModal = computed(() => props.hideIfModal && (panoptic.openModalId == ModalId.IMAGE || panoptic.openModalId == ModalId.TAG))

provide('hideImg', hideFromModal)

// ── Instance data for the lines around the viewport ──────────────────────────
// All instance IDs of the prefetch range (the mounted lines, and a viewport ahead in the scroll
// direction) are registered in one shot, so the backend is hit with a single batched request.
// The scroller holds the range while flinging, so what is flown past is not asked for.
const range = shallowRef<ViewRange | null>(null)

const windowIds = computed(() => {
    const r = range.value
    linesBuilt.value
    if (!r) return []
    const host = props.manager.result
    const colIds = columnStore.instanceIds()
    const slots: number[] = []
    for (const line of layout.between(r.prefetch[0], r.prefetch[1], 500)) {
        if (line.index < 0) continue
        const item = leafLine(host, line.node, line.index, geometry)
        if (item) lineFirstSlots(host, item, slots)
    }
    const ids: number[] = []
    for (const slot of slots) {
        const instanceId = colIds[slot]
        if (instanceId !== undefined && !isNaN(instanceId)) ids.push(instanceId)
    }
    return ids
})
const windowPropIds = computed(() => props.properties?.map(p => p.id) ?? [])

defineExpose({
    scrollTo,
    computeLines: () => computeLines(true),
    clear
})

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
    // Checked when the timer fires, not now: a toggle handled in between may already cover this bump.
    _triggerHandle = setTimeout(() => {
        const result = props.manager.result
        if (result === builtResult && result.rev === builtRev && builtVersion === props.manager.version.value) return
        computeLines(false)
    }, 50)
}

onMounted(() => computeLines(true))

// The manager prop can be swapped for a brand-new instance (e.g. re-rooting the tree at a
// different group) without its `version` changing. Watch the reference itself so the scroller
// content always follows which group is being shown.
watch(() => props.manager, () => nextTick(() => computeLines(true)))

// Every line changes size: the same fraction of the top line stays at the top. A new image size
// or width also changes how many images a line holds, so what each line draws: re-render them.
function resized() {
    if (!geometry.setParams(lineParams())) return
    layout.refresh()
    vs.value?.relayout({ anchor: 'scale', rerender: true })
}

watch(() => props.imageSize, () => nextTick(resized))
watch(() => props.hideGroup, () => computeLines(false))

// The visible properties only change the line height: no line is given another range, so nothing is
// re-rendered by the scroller (the cards redraw their property rows themselves). Runs before the
// render (flush 'pre'), so the taller cards are never drawn at the old positions.
watch([visiblePropertiesNb, visiblePropertiesClusterNb], () => {
    if (!geometry.setParams(lineParams())) return
    layout.refresh()
    vs.value?.relayout({ anchor: 'scale' })
})

// Width drives per-line/per-cell sizing — recompute when it changes, once the resize settles.
let resizeWidthHandler: ReturnType<typeof setTimeout> | undefined
watch(contentWidth, () => {
    clearTimeout(resizeWidthHandler)
    resizeWidthHandler = setTimeout(resized, 200)
})

// Re-render on result change via the version tick. Vue stops this watch automatically on unmount.
watch(() => props.manager.version.value, triggerUpdate)

</script>

<template>
    <InstanceData :instance-ids="windowIds" :prop-ids="windowPropIds">
        <VirtualScroller ref="vs" :layout="layout" :height="props.height" :overscan="300"
            :data-border-scope="borderScope" v-on="cellHover.listeners" @range="r => range = r">
            <template #default="{ line }">
                <template v-if="line.index < 0">
                    <GroupLineVue v-if="!props.hideGroup && groupItem(line)" :item="groupItem(line)!"
                        :parent-ids="groupLineParents(groupItem(line)!.data)"
                        :manager="props.manager" :hide-options="props.hideOptions" :data="props.manager.result"
                        @scroll="scrollTo" @hover="updateHoverBorder" @unhover="hoverGroupBorder = -1"
                        @group:close="onToggled" @group:open="onToggled" @select="toggleGroupSelect"
                        @reco="emit('reco', $event)" />
                </template>
                <template v-else-if="imageItem(line)">
                    <ImageLineVue v-if="imageItem(line)!.type == 'images'" :image-size="imageItem(line)!.imageSize"
                        :item="imageItem(line)!" :result="props.manager.result"
                        :parent-ids="imageLineParents(line.node)" :properties="props.properties"
                        @update:selected-image="e => updateImageSelection(e, imageItem(line)!)" @scroll="scrollTo"
                        @hover="updateHoverBorder" @unhover="hoverGroupBorder = -1" />
                    <PileLine v-else :image-size="imageItem(line)!.imageSize" :item="imageItem(line)!"
                        :result="props.manager.result"
                        :parent-ids="imageLineParents(line.node)" :properties="visiblePropertiesCluster"
                        :sha1-scores="props.sha1Scores" :preview="props.preview"
                        @update:selected-image="e => updateImageSelection(e, imageItem(line)!)" @scroll="scrollTo"
                        @hover="updateHoverBorder" @unhover="hoverGroupBorder = -1" />
                </template>
            </template>
        </VirtualScroller>
    </InstanceData>
    <CellHoverTip :tip="cellHover.tip.value" @hide="cellHover.hideTip" />
    <component :is="'style'" v-if="hoverBorderCss">{{ hoverBorderCss }}</component>
</template>
