<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed, shallowRef, provide, getCurrentInstance } from 'vue';
import ClusterLineVue from './ClusterLine.vue';
import { Group } from '@/core/GroupManager'
import type { GroupInspector } from '@/core/group/inspector'
import { keyState } from '@/data/composables/keyState';
import { Property, ModalId } from '@/data/models';
import { ClusterLine, GroupViewMode, mosaicSlotCount } from '@/components/scrollers/types';
import { usePanopticStore } from '@/data/stores/panopticStore';
import { useColumnStore } from '@/data/stores/columnStore';
import InstanceData from '@/components/data/InstanceData.vue';
import VirtualScroller from '@/components/scrollers/virtual/VirtualScroller.vue';
import { ScrollLayout, lineKey } from '@/components/scrollers/virtual/scrollLayout';
import type { LayoutSource, LineRef } from '@/components/scrollers/virtual/scrollLayout';
import type { ViewRange } from '@/components/scrollers/virtual/virtualView';

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

const emit = defineEmits(['reco', 'open-cluster', 'open-group', 'close-group', 'clear-clusters', 'assign-cluster-value', 'choose-target', 'create-target'])

provide('inputKey', props.inputKey)
provide('selectNamespace', computed(() => props.manager?.selectionNamespace ?? 'global'))

const hoverGroupBorder = ref(-1)

// The hovered group's indent borders are lit by one CSS rule written here rather than a prop handed
// to every line (each hover re-rendered every line on screen). Scoped to this scroller.
const borderScope = 'cluster-' + getCurrentInstance()!.uid
const hoverBorderCss = computed(() => hoverGroupBorder.value < 0 ? '' :
    `.vscroller[data-border-scope="${borderScope}"] [data-border-group="${hoverGroupBorder.value}"] { border-left-color: blue; }`)

const MARGIN_STEP = 20

const GAP = 8 // must match the .cluster-card "me-2" margin in ClusterLine.vue
const BORDER = 2 // .cluster-card's 1px border on each side, added on top of its width style
const INPUT_ROW = 26 // .cc-input-row height below each card's image (must match ClusterLine.vue)
const SCROLLBAR = 8 // the scroller's vertical scrollbar (theme.css ::-webkit-scrollbar width)

// The `width` prop is the box this scroller occupies; its scrollbar eats SCROLLBAR px off the
// usable content width — subtract it up front so the line math matches what's actually available.
// No ResizeObserver: the prop is the single source of truth, and every per-card size is precomputed
// here (never inside ClusterLine).
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

// Handed to every line: the same array while the prop is unset (`?? []` in the template would be a
// new one, i.e. a changed prop for every line, on each render).
const NONE: number[] = []

// ── Layout ────────────────────────────────────────────────────────────────────
// The cards (computeLines), and what every line of them shares. The list is a single node of the
// scroller's layout with one body line per `perLine` cards; a line object is only made for the
// lines on screen (lineItem).
let candidates: ClusterEntry[] = []
let rootGroup: Group | undefined
let geo = { perLine: 1, frozenHeight: 1, cardWidths: [] as number[], size: 1 }
let lineCount = 0
const empty = shallowRef(true)

const source: LayoutSource = {
    root: () => 0,
    childCount: () => 0,
    child: () => 0,
    isOpen: () => true,
    headerSize: () => 0,
    bodyLines: () => lineCount,
    lineEstimate: () => geo.size,
    lineType: () => 'cluster',
}
const layout = new ScrollLayout(source)
const vs = ref<InstanceType<typeof VirtualScroller>>()

const range = shallowRef<ViewRange | null>(null)

const windowIds = computed(() => {
    const r = range.value
    if (!r) return []
    const ids: number[] = []
    const colIds = columnStore.instanceIds()
    // A mosaic card shows the group's first images, so preload all of them — otherwise only the
    // representative one has its data ready.
    const count = mosaicSlotCount(props.viewMode ?? 'single')
    const from = Math.max(0, r.prefetch[0].index * geo.perLine)
    const to = Math.min(candidates.length, (r.prefetch[1].index + 1) * geo.perLine)
    for (let i = from; i < to; i++) {
        const entry = candidates[i]
        const slots = count > 1 ? (entry.group.slots ?? []).slice(0, count) : [entry.slot]
        for (const slot of slots) {
            const instanceId = colIds[slot]
            if (instanceId !== undefined && !isNaN(instanceId)) ids.push(instanceId)
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
    candidates = []
    lineCount = 0
    empty.value = true
    items.clear()
    layout.clear()
    vs.value?.relayout({ rerender: true })
}

function sameLine(a: ClusterLine | undefined, b: ClusterLine): boolean {
    if (!a || a.type !== b.type || a.size !== b.size) return false
    if (a.id !== b.id || a.imageSize !== b.imageSize) return false
    if (a.cardWidths[0] !== b.cardWidths[0] || a.cardWidths.length !== b.cardWidths.length) return false
    const ad = a.data, bd = b.data
    if (ad.length !== bd.length) return false
    for (let i = 0; i < ad.length; i++) {
        if (ad[i].slot !== bd[i].slot || ad[i].group !== bd[i].group) return false
    }
    return true
}

const items = new Map<string, ClusterLine>()

function lineItem(line: LineRef): ClusterLine | undefined {
    const start = line.index * geo.perLine
    if (line.index < 0 || start >= candidates.length || !rootGroup) return undefined
    const chunk = candidates.slice(start, start + geo.perLine)
    const item: ClusterLine = {
        id: rootGroup.id + '|cli-' + line.index,
        type: 'cluster',
        data: chunk,
        groupId: rootGroup.id,
        depth: rootGroup.depth + 1,
        imageSize: geo.frozenHeight,
        emptyCount: geo.perLine - chunk.length,
        cardWidths: geo.cardWidths,
        size: geo.size,
    }
    const key = lineKey(line)
    const previous = items.get(key)
    if (sameLine(previous, item)) return previous
    if (items.size > 2000) items.clear()
    items.set(key, item)
    return item
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

function computeLines() {
    const root = props.manager.result.root
    rootGroup = root
    const found: ClusterEntry[] = []
    if (root) {
        collectCandidates(root, found)
        if (found.length === 0 && root.slots && root.slots.length > 0) {
            found.push({ group: root, slot: root.slots[0] })
        }
    }
    candidates = found
    empty.value = found.length === 0
    if (!root || !found.length) {
        lineCount = 0
        layout.rebuild()
        vs.value?.relayout({ rerender: true })
        return
    }

    // Reserve one MARGIN_STEP per parent-border column that ClusterLine will
    // actually render. That count comes from clusterLineParents, which returns
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

    // card == image height + one typed property-input row (INPUT_ROW) per grouping level; +10 for
    // the card's bottom margin (mb-2) + gap
    geo = { perLine: itemsPerLine, frozenHeight, cardWidths, size: frozenHeight + INPUT_ROW * inputRows.value + 10 }
    lineCount = Math.ceil(found.length / itemsPerLine)
    // One node: rebuilding is O(1).
    layout.rebuild()
    vs.value?.relayout({ rerender: true })
}

function scrollTo(groupId: number) {
    if (groupId === rootGroup?.id) return vs.value?.scrollToOffset(0)
    const i = candidates.findIndex(e => e.group.id === groupId)
    if (i >= 0) vs.value?.scrollTo({ node: 0, index: Math.floor(i / geo.perLine) })
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

// The same array while the chain is the same: a new one is a changed prop for every line.
let parentsCache: number[] = []
function clusterLineParents(): number[] {
    const id = rootGroup?.id
    if (!id) return NONE
    const parentGroup = props.manager.result.index[id]
    const ids = parentGroup ? [...getParents(parentGroup), id] : [id]
    if (ids.length !== parentsCache.length || ids.some((v, i) => v !== parentsCache[i])) parentsCache = ids
    return parentsCache
}

function toggleClusterSelect(groupId: number) {
    // isValid, not truthiness: getGroupIterator always returns an object, so a stale line
    // pointing at a group a rebuild removed would pass `if (iterator)` and then throw.
    const iterator = props.manager.getGroupIterator(groupId)
    if (iterator.isValid) props.manager.toggleGroupIterator(iterator, keyState.shift)
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
        <div v-if="empty" class="p-3 text-secondary">{{ $t('main.group.no_lines') }}</div>
        <InstanceData v-else :instance-ids="windowIds" :prop-ids="windowPropIds">
        <VirtualScroller ref="vs" :layout="layout" :height="props.height" :overscan="400"
            :data-border-scope="borderScope" @range="r => range = r">
            <template #default="{ line }">
                <ClusterLineVue v-if="lineItem(line)" :image-size="lineItem(line)!.imageSize" :input-index="line.index * maxPerLine"
                    :item="lineItem(line)!"
                    :parent-ids="clusterLineParents()"
                    :manager="props.manager"
                    :properties="props.properties"
                    :target-property-ids="props.targetPropertyIds ?? NONE"
                    :highlight-ids="props.highlightIds ?? NONE"
                    :opened-ids="props.openedIds ?? NONE"
                    :view-mode="props.viewMode ?? 'single'"
                    @hover="updateHoverBorder"
                    @unhover="hoverGroupBorder = -1"
                    @select-cluster="toggleClusterSelect"
                    @open-cluster="(id, shift) => emit('open-cluster', id, shift)"
                    @open-group="id => emit('open-group', id)"
                    @close-group="id => emit('close-group', id)"
                    @clear-clusters="id => emit('clear-clusters', id)"
                    @assign-cluster-value="(id, val, propId) => emit('assign-cluster-value', id, val, propId)"
                    @choose-target="(id, propId) => emit('choose-target', id, propId)"
                    @create-target="id => emit('create-target', id)"
                    @scroll="scrollTo"
                    @reco="emit('reco', $event)" />
            </template>
        </VirtualScroller>
        </InstanceData>
        <component :is="'style'" v-if="hoverBorderCss">{{ hoverBorderCss }}</component>
    </div>
</template>
