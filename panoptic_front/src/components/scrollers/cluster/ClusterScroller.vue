<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed, Ref, shallowRef, provide } from 'vue';
import ClusterLineVue from './ClusterLine.vue';
import { GroupManager, Group } from '@/core/GroupManager';
import { keyState } from '@/data/keyState';
import { Property, ClusterLine, ModalId } from '@/data/models';
import { RecycleScroller } from 'vue-virtual-scroller';
import { usePanopticStore } from '@/data/panopticStore';
import { useColumnStore } from '@/data/columnStore';
import InstanceData from '@/components/data/InstanceData.vue';

const panoptic = usePanopticStore()
const columnStore = useColumnStore()

const props = defineProps<{
    imageSize: number,
    height: number,
    width: number,
    groupManager: GroupManager,
    properties: Property[],
    hideIfModal?: boolean,
    inputKey: string,
    // Group ids currently open in the right-side inspector panel.
    openedIds?: number[]
}>()

const emit = defineEmits(['reco', 'open-cluster'])

provide('inputKey', props.inputKey)
provide('selectNamespace', computed(() => props.groupManager?.selectionNamespace ?? 'global'))

const clusterLines = shallowRef([]) as Ref<ClusterLine[]>

const hoverGroupBorder = ref(-1)

const scroller = ref(null)
const MARGIN_STEP = 20

const GAP = 8 // must match the .cluster-card "me-2" margin in ClusterLine.vue
const BORDER = 2 // .cluster-card's 1px border on each side, added on top of its width style
const SCROLLBAR = 8 // RecycleScroller's vertical scrollbar (theme.css ::-webkit-scrollbar width)

// The `width` prop is the box this scroller occupies. RecycleScroller scrolls vertically,
// so its scrollbar eats SCROLLBAR px off the usable content width — subtract it up front so
// the line math matches what's actually available. No ResizeObserver: the prop is the single
// source of truth, and every per-card size is precomputed here (never inside ClusterLine).
const contentWidth = computed(() => Math.max(0, props.width - SCROLLBAR))

const maxPerLine = computed(() => Math.ceil(contentWidth.value / props.imageSize * 1.5))

const hideFromModal = computed(() => props.hideIfModal && (panoptic.openModalId == ModalId.IMAGE || panoptic.openModalId == ModalId.TAG))

provide('hideImg', hideFromModal)

const windowStart = ref(0)
const windowEnd   = ref(0)

function onScrollerUpdate(startIndex: number, endIndex: number) {
    windowStart.value = startIndex
    windowEnd.value   = endIndex
}

const windowIds = computed(() => {
    const ids: number[] = []
    const lines = clusterLines.value
    if (!lines.length) return ids

    let start = Math.max(0, Math.min(windowStart.value, lines.length - 1))
    let end   = Math.max(0, Math.min(windowEnd.value, lines.length - 1))

    let preCount = 0
    while (start > 0 && preCount < 5) {
        start--
        if (lines[start].type === 'cluster') preCount++
    }

    let postCount = 0
    while (end < lines.length - 1 && postCount < 5) {
        end++
        if (lines[end].type === 'cluster') postCount++
    }

    for (let i = start; i <= end; i++) {
        const line = lines[i]
        if (line.type === 'cluster') {
            for (const entry of (line as ClusterLine).data) {
                const instanceId = columnStore.instanceIds()[entry.slot]
                if (instanceId !== undefined && !isNaN(instanceId)) {
                    ids.push(instanceId)
                }
            }
        }
    }
    return ids
})

const windowPropIds = computed(() => props.properties?.map(p => p.id) ?? [])

defineExpose({
    computeLines,
    clear
})

function clear() {
    clusterLines.value = []
}

function sameLine(a: ClusterLine, b: ClusterLine): boolean {
    if (!a || a.type !== b.type || a.size !== b.size) return false
    if (a.id !== b.id) return false
    const ad = a.data, bd = b.data
    if (ad.length !== bd.length) return false
    for (let i = 0; i < ad.length; i++) {
        if (ad[i].slot !== bd[i].slot || ad[i].group.id !== bd[i].group.id) return false
    }
    return true
}

function reconcileLines(prev: ClusterLine[], next: ClusterLine[]): ClusterLine[] {
    if (!prev.length) return next
    const byId = new Map<any, ClusterLine>()
    for (const l of prev) byId.set(l.id, l)
    for (let i = 0; i < next.length; i++) {
        const old = byId.get(next[i].id)
        if (old && sameLine(old, next[i])) next[i] = old
    }
    return next
}

type ClusterEntry = { group: Group, slot: number }

let _computingLines = false
function computeLines() {
    if (_computingLines) return
    _computingLines = true
    try {
        const root = props.groupManager.result.root
        if (!root) {
            clusterLines.value = []
            return
        }
        const candidates: ClusterEntry[] = []
        for (const child of root.children) {
            if (child.slots && child.slots.length > 0) {
                candidates.push({ group: child, slot: child.slots[0] })
            }
        }
        if (candidates.length === 0 && root.slots && root.slots.length > 0) {
            candidates.push({ group: root, slot: root.slots[0] })
        }

        // Reserve one MARGIN_STEP per parent-border column that ClusterLine will
        // actually render. That count comes from getClusterLineParents, which returns
        // NOTHING when the (rooted) tree's root id is 0 — the flat cluster-view case —
        // because it early-returns on the falsy id. Mirror that here so we don't reserve
        // indent width for columns that never get drawn (which left a ~20px gap).
        const borderCols = root.id ? getParents(root).length + 1 : 0
        const lineWidth = contentWidth.value - (borderCols * MARGIN_STEP)

        // imageSize only decides how many images fit in a line...
        // (+BORDER accounts for .cluster-card's 1px border on each side, which is added
        // on top of the image-size we set as its width)
        const rawItemWidth = props.imageSize + BORDER + GAP
        const itemsPerLine = Math.max(1, Math.floor(lineWidth / rawItemWidth))
        // ...then images are stretched to exactly fill a FULL line. Every line uses this
        // same size — a trailing/partial line (end of group, small group) keeps it too
        // instead of blowing its images up to fill the leftover space; the empty slots are
        // simulated (reserved, not rendered) so alignment across lines stays consistent.
        // Flooring the per-card size leaves up to (itemsPerLine - 1) leftover px at the line
        // end; hand those out 1px at a time to the leading columns so the line fills the full
        // width. The per-column widths are computed once here and shared by every line, so
        // grid columns stay aligned line-to-line and ClusterLine does no width math itself.
        const cardArea = lineWidth - GAP * (itemsPerLine - 1) // px available for card OUTER widths
        const baseOuter = Math.floor(cardArea / itemsPerLine)
        const extraCount = cardArea - baseOuter * itemsPerLine
        const lineImageSize = Math.max(1, baseOuter - BORDER)
        const cardWidths: number[] = []
        for (let c = 0; c < itemsPerLine; c++) cardWidths.push(lineImageSize + (c < extraCount ? 1 : 0))

        const lines: ClusterLine[] = []
        let groupLineIndex = 0
        for (let i = 0; i < candidates.length; i += itemsPerLine) {
            const chunk = candidates.slice(i, i + itemsPerLine)
            lines.push({
                id: root.id + '|cli-' + groupLineIndex++,
                type: 'cluster',
                data: chunk,
                groupId: root.id,
                depth: root.depth + 1,
                imageSize: lineImageSize,
                emptyCount: itemsPerLine - chunk.length,
                cardWidths,
                size: lineImageSize + 40
            })
        }

        clusterLines.value = reconcileLines(clusterLines.value, lines)
    } finally {
        _computingLines = false
    }
}

function scrollTo(groupId) {
    const idx = clusterLines.value.findIndex(l => l.groupId === groupId)
    if (idx >= 0) {
        scroller.value.scrollToItem(idx)
        nextTick(() => scroller.value.updateVisibleItems(true))
    }
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

function getClusterLineParents(item: ClusterLine) {
    if (!item.groupId) return []
    const parentGroup = props.groupManager.result.index[item.groupId]
    return parentGroup ? [...getParents(parentGroup), item.groupId] : [item.groupId]
}

function toggleClusterSelect(groupId: number) {
    const iterator = props.groupManager.getGroupIterator(groupId)
    if (iterator) props.groupManager.toggleGroupIterator(iterator, keyState.shift)
}

let _triggerHandle: ReturnType<typeof setTimeout> | undefined
function triggerUpdate() {
    clearTimeout(_triggerHandle)
    _triggerHandle = setTimeout(computeLines, 50)
}

onMounted(computeLines)

// The groupManager prop can be swapped for a brand-new instance (e.g. re-rooting the
// tree at a different group) without its `version` changing, since a fresh manager
// starts at the same baseline version as the one it replaced. Watch the reference
// itself so the scroller content always follows which group is being shown.
watch(() => props.groupManager, () => {
    nextTick(computeLines)
})

// Width and imageSize both drive the per-line/per-card sizing — recompute on either.
// The width prop is the single source of truth (no observer), so one pass per change.
watch([contentWidth, () => props.imageSize], () => {
    nextTick(computeLines)
})

watch(() => props.groupManager.version.value, triggerUpdate)
</script>

<template>
    <div style="width: 100%; min-width: 0;">
        <div v-if="clusterLines.length === 0" class="p-3 text-secondary">No clusters to display</div>
        <InstanceData v-else :instance-ids="windowIds" :prop-ids="windowPropIds">
        <RecycleScroller :items="clusterLines" key-field="id" ref="scroller" :style="'height: ' + props.height + 'px;'"
            :buffer="400" :min-item-size="0" :emitUpdate="true" @update="onScrollerUpdate" :page-mode="false" :prerender="0">
            <template v-slot="{ item, index, active }">
                <div v-if="item.type == 'cluster'">
                    <ClusterLineVue :image-size="item.imageSize" :input-index="index * maxPerLine" :item="item"
                        :parent-ids="getClusterLineParents(item)"
                        :hover-border="hoverGroupBorder"
                        :manager="props.groupManager"
                        :properties="props.properties"
                        :opened-ids="props.openedIds ?? []"
                        @hover="updateHoverBorder"
                        @unhover="hoverGroupBorder = -1"
                        @select-cluster="toggleClusterSelect"
                        @open-cluster="(id, shift) => emit('open-cluster', id, shift)"
                        @scroll="scrollTo"
                        @reco="emit('reco', $event)" />
                </div>
            </template>
        </RecycleScroller>
        </InstanceData>
    </div>
</template>
