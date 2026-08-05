<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed, Ref, shallowRef, provide } from 'vue';
import ClusterLineVue from './ClusterLine.vue';
import { Group } from '@/core/GroupManager'
import type { GroupInspector } from '@/core/group/inspector'
import { keyState } from '@/data/keyState';
import { Property, ClusterLine, ModalId, GroupViewMode, mosaicSlotCount } from '@/data/models';
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
    // Stable width used to SIZE the images: the full workspace width, which does not change
    // when the inspector opens. Column sizing keys off this so the per-image pixel size stays
    // frozen; only how many columns fit (from `width`) reflows. Defaults to `width`.
    layoutWidth?: number,
    manager: GroupInspector,
    properties: Property[],
    hideIfModal?: boolean,
    inputKey: string,
    // Group ids currently open in the right-side inspector panel.
    openedIds?: number[],
    // Group ids to highlight (e.g. the clusters created by the last action).
    highlightIds?: number[],
    // One assignment target per grouping level (outermost first): each card gets one input row
    // per level, so grouping by A then B shows both A's and B's value.
    targetPropertyIds?: number[],
    // How each card renders its group: one representative image, or a mosaic of the first few.
    viewMode?: GroupViewMode
}>()

const emit = defineEmits(['reco', 'open-cluster', 'open-group', 'close-group', 'clear-clusters', 'assign-cluster-value'])

provide('inputKey', props.inputKey)
provide('selectNamespace', computed(() => props.manager?.selectionNamespace ?? 'global'))

const clusterLines = shallowRef([]) as Ref<ClusterLine[]>

const hoverGroupBorder = ref(-1)

const scroller = ref(null)
const MARGIN_STEP = 20

const GAP = 8 // must match the .cluster-card "me-2" margin in ClusterLine.vue
const BORDER = 2 // .cluster-card's 1px border on each side, added on top of its width style
const INPUT_ROW = 26 // .cc-input-row height below each card's image (must match ClusterLine.vue)
const SCROLLBAR = 8 // RecycleScroller's vertical scrollbar (theme.css ::-webkit-scrollbar width)

// The `width` prop is the box this scroller occupies. RecycleScroller scrolls vertically,
// so its scrollbar eats SCROLLBAR px off the usable content width — subtract it up front so
// the line math matches what's actually available. No ResizeObserver: the prop is the single
// source of truth, and every per-card size is precomputed here (never inside ClusterLine).
const contentWidth = computed(() => Math.max(0, props.width - SCROLLBAR))
// The width the image size is derived from. Falls back to the actual width when no stable
// width is supplied, so a standalone scroller behaves exactly as before.
const layoutContentWidth = computed(() => Math.max(0, (props.layoutWidth ?? props.width) - SCROLLBAR))

const maxPerLine = computed(() => Math.ceil(contentWidth.value / props.imageSize * 1.5))

// One input row per grouping level, but always at least one so a card keeps its shape when
// there is no target at all. ClusterLine applies the same rule to what it renders.
const inputRows = computed(() => Math.max(1, props.targetPropertyIds?.length ?? 0))

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
                // A mosaic card shows the group's first images, so preload all of them —
                // otherwise only the representative one has its data ready.
                const count = mosaicSlotCount(props.viewMode ?? 'single')
                const slots = count > 1 ? (entry.group.slots ?? []).slice(0, count) : [entry.slot]
                for (const slot of slots) {
                    const instanceId = columnStore.instanceIds()[slot]
                    if (instanceId !== undefined && !isNaN(instanceId)) {
                        ids.push(instanceId)
                    }
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
    if (a.cardWidths[0] !== b.cardWidths[0] || a.cardWidths.length !== b.cardWidths.length) return false
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

// Collect the cards to show, following the tree view's open/close semantics rather than the
// old leaves-only rule: an OPEN group with children is replaced by those children (so
// sub-dividing turns one card into several), while a CLOSED one stands in for its whole
// subtree as a single card that can be re-opened from its + button. sha1 piling is a leaf
// overlay (pileIndex), not children, so a piled leaf still surfaces as one card here.
function collectCandidates(group: Group, out: ClusterEntry[]) {
    for (const child of group.children) {
        // subGroupType is not reliable (a level can mix cluster + property children), so key
        // off children + the group's own open state.
        if (child.children.length > 0 && !child.view.closed) {
            collectCandidates(child, out)
        } else if (child.slots && child.slots.length > 0) {
            out.push({ group: child, slot: child.slots[0] })
        }
    }
}

let _computingLines = false
function computeLines() {
    if (_computingLines) return
    _computingLines = true
    try {
        const root = props.manager.result.root
        if (!root) {
            clusterLines.value = []
            return
        }
        const candidates: ClusterEntry[] = []
        collectCandidates(root, candidates)
        if (candidates.length === 0 && root.slots && root.slots.length > 0) {
            candidates.push({ group: root, slot: root.slots[0] })
        }

        // Reserve one MARGIN_STEP per parent-border column that ClusterLine will
        // actually render. That count comes from getClusterLineParents, which returns
        // NOTHING when the (rooted) tree's root id is 0 — the flat cluster-view case —
        // because it early-returns on the falsy id. Mirror that here so we don't reserve
        // indent width for columns that never get drawn (which left a ~20px gap).
        const borderCols = root.id ? getParents(root).length + 1 : 0
        // The image HEIGHT is frozen against the STABLE line width (the full workspace), so it does
        // NOT change when the inspector opens and narrows the pane. The ACTUAL line width sets how
        // many cards fit and how WIDE each one stretches to fill the pane — only the width flexes,
        // so the vertical rhythm stays perfectly stable while the space is still fully used.
        const stableLineWidth = layoutContentWidth.value - (borderCols * MARGIN_STEP)
        const actualLineWidth = contentWidth.value - (borderCols * MARGIN_STEP)

        // imageSize sets how many cards fit a full (stable) line...
        // (+BORDER accounts for .cluster-card's 1px border on each side, which is added
        // on top of the image-size we set as its width)
        const rawItemWidth = props.imageSize + BORDER + GAP
        const stableItemsPerLine = Math.max(1, Math.floor(stableLineWidth / rawItemWidth))
        // ...and the frozen HEIGHT is derived to fill that full line. This one number is the stable
        // image height used on every line, independent of the current pane width.
        const stableCardArea = stableLineWidth - GAP * (stableItemsPerLine - 1)
        const frozenHeight = Math.max(1, Math.floor(stableCardArea / stableItemsPerLine) - BORDER)
        const frozenOuter = frozenHeight + BORDER

        // How many cards fit the CURRENT pane, targeting the frozen size. Fewer columns when the
        // pane narrows; the WIDTH of each then stretches to fill (below).
        const itemsPerLine = Math.max(1, Math.floor((actualLineWidth + GAP) / (frozenOuter + GAP)))

        // Stretch the card WIDTHS to fill the actual line exactly (fixed gap). Flooring leaves up
        // to (itemsPerLine - 1) leftover px; hand those out 1px at a time to the leading columns so
        // the line covers the full width with no trailing whitespace. Height stays frozenHeight, so
        // cards become slightly wider than tall when a column is dropped, never taller/shorter.
        const cardArea = actualLineWidth - GAP * (itemsPerLine - 1) // px for card OUTER widths
        const baseOuter = Math.floor(cardArea / itemsPerLine)
        const extraCount = cardArea - baseOuter * itemsPerLine
        const lineImageWidth = Math.max(1, baseOuter - BORDER)
        const cardWidths: number[] = []
        for (let c = 0; c < itemsPerLine; c++) cardWidths.push(lineImageWidth + (c < extraCount ? 1 : 0))

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
                imageSize: frozenHeight,
                emptyCount: itemsPerLine - chunk.length,
                cardWidths,
                // card == image height + one typed property-input row (INPUT_ROW) per grouping
                // level; +10 for the card's bottom margin (mb-2) + gap
                size: frozenHeight + INPUT_ROW * inputRows.value + 10
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
    const parentGroup = props.manager.result.index[item.groupId]
    return parentGroup ? [...getParents(parentGroup), item.groupId] : [item.groupId]
}

function toggleClusterSelect(groupId: number) {
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

// Width and imageSize both drive the per-line/per-card sizing — recompute on either.
// The width prop is the single source of truth (no observer), so one pass per change.
watch([contentWidth, layoutContentWidth, () => props.imageSize, inputRows], () => {
    nextTick(computeLines)
})

watch(() => props.manager.version.value, triggerUpdate)
</script>

<template>
    <div style="width: 100%; min-width: 0;">
        <div v-if="clusterLines.length === 0" class="p-3 text-secondary">{{ $t('main.group.no_lines') }}</div>
        <InstanceData v-else :instance-ids="windowIds" :prop-ids="windowPropIds">
        <RecycleScroller :items="clusterLines" key-field="id" ref="scroller" :style="'height: ' + props.height + 'px;'"
            :buffer="400" :min-item-size="0" :emitUpdate="true" @update="onScrollerUpdate" :page-mode="false" :prerender="0">
            <template v-slot="{ item, index, active }">
                <div v-if="item.type == 'cluster'">
                    <ClusterLineVue :image-size="item.imageSize" :input-index="index * maxPerLine" :item="item"
                        :parent-ids="getClusterLineParents(item)"
                        :hover-border="hoverGroupBorder"
                        :manager="props.manager"
                        :properties="props.properties"
                        :target-property-ids="props.targetPropertyIds ?? []"
                        :highlight-ids="props.highlightIds ?? []"
                        :opened-ids="props.openedIds ?? []"
                        :view-mode="props.viewMode ?? 'single'"
                        @hover="updateHoverBorder"
                        @unhover="hoverGroupBorder = -1"
                        @select-cluster="toggleClusterSelect"
                        @open-cluster="(id, shift) => emit('open-cluster', id, shift)"
                        @open-group="id => emit('open-group', id)"
                        @close-group="id => emit('close-group', id)"
                        @clear-clusters="id => emit('clear-clusters', id)"
                        @assign-cluster-value="(id, val, propId) => emit('assign-cluster-value', id, val, propId)"
                        @scroll="scrollTo"
                        @reco="emit('reco', $event)" />
                </div>
            </template>
        </RecycleScroller>
        </InstanceData>
    </div>
</template>
