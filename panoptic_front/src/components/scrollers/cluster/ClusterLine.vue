<script setup lang="ts">
import { ComputedRef, computed, inject, ref } from 'vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import { ClusterLine, GroupViewMode, MOSAIC_GRID, mosaicSlotCount } from '@/data/models'
import { ClusterRequest, Group, GroupType } from '@/core/GroupManager'
import type { GroupInspector } from '@/core/group/inspector'
import { useColumnStore } from '@/data/columnStore'
import { useDataStore } from '@/data/dataStore'
import CenteredImage from '@/components/images/CenteredImage.vue'
import ActionButton2 from '@/components/actions/ActionButton2.vue'
import ClusterPropertyInput from './ClusterPropertyInput.vue'
import ClusterBadge from '@/components/cluster/ClusterBadge.vue'
import wTT from '@/components/tooltips/withToolTip.vue'
import { isTag } from '@/utils/utils'

// Height reserved below each card's image for the typed property-input row. Must match the
// per-line `size` reserved in ClusterScroller.computeLines.
const INPUT_ROW = 26

const columnStore = useColumnStore()
const data = useDataStore()
const selectNamespace = inject<ComputedRef<string>>('selectNamespace', computed(() => 'global'))

const props = defineProps<{
    imageSize: number
    inputIndex: number
    item: ClusterLine
    parentIds: number[]
    hoverBorder: number
    manager: GroupInspector
    properties: any[]
    // Group ids currently open in the right-side inspector panel.
    openedIds: number[]
    // Group ids to highlight (e.g. the clusters created by the last action).
    highlightIds?: number[]
    // Assignment target property — the value each card's top chip reflects. undefined = none.
    targetPropertyId?: number
    // 'single' = one representative image fills the card; the mosaic modes show several of the
    // group's images, gridded — with or without a large one on the left half (see MOSAIC_GRID).
    viewMode?: GroupViewMode
}>()

// Gap between the tiles of a mosaic card (the card's own background shows through).
const MOSAIC_GAP = 2

// The tiles of one mosaic card: the group's first images, laid out as an optional [big left half]
// plus [the others gridded into the space left], the shape coming from the mode. Returns null
// when there is no mosaic to draw (single mode, or a group with a single image) — such a card
// falls back to the plain single-image layout.
// Sizes are computed here, in px, so the tiles add up to EXACTLY the card box (the leftover
// pixels of each floor go to the last column / row), as everywhere else in this view.
function mosaicTiles(group: Group, width: number) {
    const grid = MOSAIC_GRID[props.viewMode ?? 'single'] ?? MOSAIC_GRID.single
    if (!grid.cols || !grid.rows) return null
    const slots = (group.slots ?? []).slice(0, mosaicSlotCount(props.viewMode ?? 'single'))
    if (slots.length < 2) return null

    const h = props.imageSize
    // With a large image the grid gets the right half; without one it spans the whole card.
    const leftW = grid.big ? Math.floor((width - MOSAIC_GAP) / 2) : 0
    const rightW = grid.big ? width - MOSAIC_GAP - leftW : width

    // Shrink the grid to what the group actually has, so a small group fills its space instead
    // of leaving holes: as many columns as fit its images, and only the rows it needs.
    const rest = grid.big ? slots.length - 1 : slots.length
    const cols = Math.min(grid.cols, rest)
    const rows = Math.min(grid.rows, Math.ceil(rest / cols))

    const rowBase = Math.floor((h - MOSAIC_GAP * (rows - 1)) / rows)
    const rowLast = h - MOSAIC_GAP * (rows - 1) - rowBase * (rows - 1)

    return {
        big: grid.big ? { slot: slots[0], width: leftW, height: h } : null,
        gridWidth: rightW,
        tiles: (grid.big ? slots.slice(1) : slots).map((slot, i) => {
            const c = i % cols, r = Math.floor(i / cols)
            // A short last row shares the half between its own tiles, so it fills the width
            // instead of leaving a hole beside it.
            const inRow = r === rows - 1 ? rest - cols * r : cols
            const base = Math.floor((rightW - MOSAIC_GAP * (inRow - 1)) / inRow)
            return {
                slot,
                width: c === inRow - 1 ? rightW - MOSAIC_GAP * (inRow - 1) - base * (inRow - 1) : base,
                height: r === rows - 1 ? rowLast : rowBase,
            }
        }),
    }
}

const emits = defineEmits(['hover', 'unhover', 'scroll', 'select-cluster', 'reco', 'open-cluster', 'open-group', 'close-group', 'clear-clusters', 'assign-cluster-value'])

const hoveredCard = ref<number | null>(null)

// The assignment target property, whose value each card's input edits.
const targetProperty = computed(() =>
    props.targetPropertyId != null ? data.properties?.[props.targetPropertyId] : null)

// Inner (image) width for the card at column `i` — precomputed by the scroller so the
// cards add up to exactly the line width. Falls back to the line's base image size.
function cardInner(i: number) {
    return props.item.cardWidths[i] ?? props.imageSize
}

// One tile list per card of this line (empty in single mode, or for a one-image group), so the
// layout is computed once per render instead of once per template use.
const cardTiles = computed(() => props.item.data.map((e, i) => mosaicTiles(e.group, cardInner(i))))

function getInstanceId(slot: number) {
    return columnStore.instanceIds()[slot]
}

function clusterName(group: Group) {
    return group.name ?? ('Cluster ' + group.parentIdx)
}

// A cluster card: a real Cluster group — a sub-cluster of the parent, or the "New" leftover pile
// of images not covered by any cluster. Property value-groups carry their value in the input row.
function isClusterCard(group: Group) {
    return group.type === GroupType.Cluster
}

// This card stands in for a whole closed subtree: opening it swaps the card for its children.
// (An OPEN group with children is never a card — the scroller renders its children instead.)
function isCollapsed(group: Group) {
    return (group.children?.length ?? 0) > 0
}

// Collapsing goes UP: it closes this card's PARENT, so the parent's whole level folds back
// into a single card. Only a CLUSTER card may do it — clusters are what an action added on top
// of the grouping, so folding them away returns to the group they were made from. The property
// groups the GroupManager builds are the base of the view: they are always shown, never folded.
// Also not offered when the parent is the tree root, which is never a card.
function canCollapse(group: Group) {
    if (group.type !== GroupType.Cluster) return false
    const parent = group.parent
    return !!parent && !!parent.parent
}

// A collapsed card whose subtree is CLUSTERS (not property value-groups) can drop them
// outright, like the tree view's "close clusters" button — same delCustomGroups call.
function hasClusterChildren(group: Group) {
    return (group.children ?? []).some(c => c.type === GroupType.Cluster)
}

const highlightSet = computed(() => new Set(props.highlightIds ?? []))

// Sub-divide a cluster. The card only names its group and the function to run: the collection's
// ClusterManager owns the run and the grafting, so the result lands even if this card has been
// recycled out of the virtualized list before the backend answers.
function cluster(groupId: number, req: ClusterRequest) {
    props.manager.cluster(groupId, req)
}

// Reactive via the namespace's selection tick, read inside isGroupSelected.
function isSelected(group: Group) {
    return props.manager.isGroupSelected(group)
}

// The value shown (and editable) in each card's input, ALWAYS on the current target property. Every
// card is editable now — including value-groups (edit re-attributes the whole group). There is no
// `mixed` state: a value-group is homogeneous by construction. A card inherits the value of its
// nearest ancestor value-group KEYED ON THE TARGET PROPERTY only (so a value-group shows its own
// value, a sub-cluster of it pre-fills with it), and undefined otherwise (undecided). Ancestors
// grouped by a *different* property (nested grouping) are skipped — their value is not the target's,
// and feeding it to the target input would be a type mismatch (e.g. a tag array into a text input).
function inheritedValue(group: Group): any {
    const tpid = props.targetPropertyId
    if (tpid == null) return undefined
    let g: Group | undefined = group
    while (g) {
        if (g.type === GroupType.Property) {
            const pv = g.meta?.propertyValues?.[0]
            if (pv && pv.propertyId === tpid) {
                if (pv.value === null || pv.value === undefined || pv.value === '') return undefined
                // Tag properties store an id array; a value-group's key value is a single tag id.
                return isTag(data.properties?.[tpid]?.type) ? [pv.value] : pv.value
            }
        }
        g = g.parent
    }
    return undefined
}

function groupScore(group: Group): number | null {
    const s = group.score?.value
    return (s != undefined && group.type === GroupType.Cluster) ? Math.round(s) : null
}
</script>

<template>
    <div class="d-flex flex-row">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2"
            @click="$emit('scroll', parentId)" @mouseenter="$emit('hover', parentId)" @mouseleave="$emit('unhover')">
            <div class="cluster-line-border" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <div
            v-for="(entry, i) in props.item.data"
            :key="entry.group.id"
            class="cluster-card me-2 mb-2"
            :class="{
                opened: props.openedIds.includes(entry.group.id),
                highlighted: highlightSet.has(entry.group.id),
            }"
            :style="{ width: cardInner(i) + 'px', height: (props.imageSize + INPUT_ROW) + 'px' }"
            @mouseenter="hoveredCard = entry.group.id"
            @mouseleave="hoveredCard = null"
        >
            <!-- Image area (fixed height); the name / stats / hover actions float over it.
                 Click opens the cluster in the split inspector. -->
            <div class="cc-image-wrap" :style="{ height: props.imageSize + 'px', cursor: 'pointer' }"
                @click="$emit('open-cluster', entry.group.id, $event.shiftKey)">
                <!-- Mosaic: one large image on the left half, the next ones gridded into the
                     right half. A group with a single image has no tiles and falls back below. -->
                <div v-if="cardTiles[i]" class="cluster-image cluster-mosaic" :style="{ gap: MOSAIC_GAP + 'px' }">
                    <CenteredImage
                        v-if="cardTiles[i].big && getInstanceId(cardTiles[i].big.slot) !== undefined"
                        :instance-id="getInstanceId(cardTiles[i].big.slot)"
                        :width="cardTiles[i].big.width"
                        :height="cardTiles[i].big.height"
                        :no-click="true"
                        :cover="true"
                    />
                    <div class="cluster-mosaic-grid"
                        :style="{ gap: MOSAIC_GAP + 'px', width: cardTiles[i].gridWidth + 'px' }">
                        <template v-for="tile in cardTiles[i].tiles" :key="'m' + tile.slot">
                            <CenteredImage
                                v-if="getInstanceId(tile.slot) !== undefined"
                                :instance-id="getInstanceId(tile.slot)"
                                :width="tile.width"
                                :height="tile.height"
                                :no-click="true"
                                :cover="true"
                            />
                        </template>
                    </div>
                </div>
                <div v-else class="cluster-image">
                    <CenteredImage
                        v-if="getInstanceId(entry.slot) !== undefined"
                        :instance-id="getInstanceId(entry.slot)"
                        :width="cardInner(i)"
                        :height="props.imageSize"
                        :no-click="true"
                    />
                </div>

                <!-- The corner toggle is pinned to the card, NOT a child of the .cc-top flex row:
                     as a flex item it was re-centered whenever the row's height changed (the
                     hover-revealed select circle is taller), which made it jump on hover. Pinned,
                     its position is fixed for good. `+` on a card standing in for a closed subtree
                     (open it to swap this card for its children), `−` otherwise (fold this whole
                     level back into the parent card). -->
                <div v-if="isCollapsed(entry.group) || canCollapse(entry.group)" class="cc-corner-wrap" @click.stop>
                    <wTT v-if="isCollapsed(entry.group)" message="btn.open-group">
                        <div class="cc-btn cc-corner" @click.stop="$emit('open-group', entry.group.id)">
                            <i class="bi bi-plus-square-dotted" />
                        </div>
                    </wTT>
                    <wTT v-else message="btn.close-group">
                        <div class="cc-btn cc-corner" @click.stop="$emit('close-group', entry.group.parent.id)">
                            <i class="bi bi-dash-square-dotted" />
                        </div>
                    </wTT>
                </div>

                <!-- Top overlay: select circle · name (left), score (right). Indented past the
                     pinned corner toggle when there is one. -->
                <div class="cc-top"
                    :class="{
                        'cc-scrim': isClusterCard(entry.group) || hoveredCard === entry.group.id,
                        'cc-indent': isCollapsed(entry.group) || canCollapse(entry.group),
                    }">
                    <SelectCircle
                        v-if="hoveredCard === entry.group.id || isSelected(entry.group)"
                        :model-value="isSelected(entry.group)"
                        @update:model-value="$emit('select-cluster', entry.group.id)"
                        @click.stop
                        class="cc-select"
                        :light-mode="true"
                    />
                    <!-- Title only for clusters (incl. the "New" leftover pile of images not covered
                         by any cluster). Property value-groups — including the null-value "no value"
                         group — are real groups that carry their value in the input row, so no title. -->
                    <span v-if="isClusterCard(entry.group)" class="cc-name">{{ clusterName(entry.group) }}</span>
                    <ClusterBadge v-if="groupScore(entry.group) != null" class="cc-score"
                        :value="groupScore(entry.group)" />
                </div>

                <!-- Hover action pill, centered over the image: subdivide · inspect · clear. -->
                <div v-show="hoveredCard === entry.group.id" class="cc-actions" @click.stop>
                    <ActionButton2 action="group" :no-border="true" :defer="true"
                        :busy="props.manager.isClustering(entry.group.id)"
                        @submit="req => cluster(entry.group.id, req)">
                        <!-- ActionButton2 wraps its slot in its own wTT ('dropdown.action.group'). -->
                        <div class="cc-btn">
                            <i class="bi bi-intersect" />
                        </div>
                    </ActionButton2>
                    <wTT message="btn.inspect-group">
                        <div class="cc-btn" @click.stop="$emit('open-cluster', entry.group.id, $event.shiftKey)">
                            <i class="bi bi-eye" />
                        </div>
                    </wTT>
                    <!-- Collapsed card holding clusters: drop them, as in the tree view. -->
                    <wTT v-if="isCollapsed(entry.group) && hasClusterChildren(entry.group)" message="btn.close-clusters">
                        <div class="cc-btn cc-danger" @click.stop="$emit('clear-clusters', entry.group.id)">
                            <i class="bi bi-x-lg" />
                        </div>
                    </wTT>
                </div>

                <!-- Bottom-left counts: self-contained chips, so no full-width scrim is needed.
                     Images, then the sub-group count on a card that holds a (closed) subtree. -->
                <div class="cc-counts">
                    <span class="cc-chip">
                        <i class="bi bi-images me-1" />{{ entry.group.slots.length }}
                    </span>
                    <span v-if="isCollapsed(entry.group)" class="cc-chip">
                        <i class="bi bi-intersect me-1" />{{ entry.group.children.length }}
                    </span>
                </div>
            </div>

            <!-- Below the image: an editable typed input on the target property, for EVERY card.
                 A value-group shows its own value (editing re-attributes the whole group); a cluster
                 or empty bucket inherits its ancestor value-group's value (undefined = undecided).
                 Assigning writes to the whole pile, which then drains into its value-group. -->
            <div class="cc-input-row" @click.stop>
                <ClusterPropertyInput
                    v-if="targetProperty"
                    :property="targetProperty"
                    :model-value="inheritedValue(entry.group)"
                    :instance-id="getInstanceId(entry.slot)"
                    @update:model-value="v => $emit('assign-cluster-value', entry.group.id, v)"
                />
            </div>
        </div>
        <!-- Reserve the space of the images missing from this (partial) line so it keeps
             the same card size as a full line instead of stretching to fill the gap. -->
        <div
            v-for="n in props.item.emptyCount"
            :key="'empty-' + n"
            class="cluster-card cluster-card-empty me-2 mb-2"
            :style="{ width: cardInner(props.item.data.length + n - 1) + 'px', height: (props.imageSize + INPUT_ROW) + 'px' }"
        ></div>
    </div>
</template>

<style scoped>
.cluster-line-border {
    height: 100%;
    border-left: 1px solid var(--border-color);
    padding-left: 10px;
}

.active {
    border-left: 1px solid blue;
}

.cluster-card:last-child {
    margin-right: 0;
}

/* Photo card: image area on top with floating info, a typed property-input row below. */
.cluster-card {
    position: relative;
    display: flex;
    flex-direction: column;
    /* No surface of its own: the input row shows the view's background through, as in Image.vue. */
    background-color: transparent;
    border-radius: 3px;
    overflow: hidden;
    flex: 0 0 auto;
    min-width: 0;
}

/* Every card carries a full ring around the whole card (image + input row), drawn as an inset
   overlay rather than an outline/box-shadow: it stays inside the card's own width (no bleed into
   the neighbour or the line) and paints above the image and the floating overlays, so the top edge
   stays visible instead of being covered by the scrim. Opened / highlighted just recolour it. */
.cluster-card::after {
    content: '';
    position: absolute;
    inset: 0;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    pointer-events: none;
    z-index: 4;
}

/* Above the input row (the tree cells sit at z-index 5), so their hover frame and full-bleed
   colour fill can't cut across the ring — same rule as Image.vue's selected cell. */
.cluster-card.opened::after {
    border: 2px solid var(--primary, #4f46e5);
    z-index: 10;
}

/* Last-made clusters: warm ring so a fresh clustering pass stands out at a glance. */
.cluster-card.highlighted::after {
    border: 2px solid #f59e0b;
    z-index: 10;
}

/* Opened wins the border colour when a card is both. */
.cluster-card.opened.highlighted::after {
    border-color: var(--primary, #4f46e5);
}

.cluster-card-empty {
    visibility: hidden;
    pointer-events: none;
    box-shadow: none;
}

/* The image area sits at the top of the card; the name / stats / hover pill float over it,
   and the typed property input sits in its own row below (.cc-input-row). */
.cc-image-wrap {
    position: relative;
    width: 100%;
    overflow: hidden;
    flex-shrink: 0;
    background-color: var(--bg-subtle, #f3f4f6);
    /* the image is the card's top edge: match the ring's corners (4px minus the 1px ring) */
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
}

.cluster-image {
    position: absolute;
    inset: 0;
    background-color: var(--bg-subtle, #f3f4f6);
}

/* Mosaic: the big image on the left, the stacked column on the right. Tile sizes are computed
   in JS (mosaicTiles) so the images add up to exactly the card's box, as everywhere else here. */
.cluster-mosaic {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: center;
}

.cluster-mosaic-grid {
    display: flex;
    flex-wrap: wrap;
    align-content: center;
    justify-content: center;
}

/* Each tile keeps exactly the size computed for it: no flex shrink/grow, so an image stays
   centred inside its own half instead of being pulled towards the card's edge. */
.cluster-mosaic > *,
.cluster-mosaic-grid > * {
    flex: 0 0 auto;
}

/* Same as Image.vue's .prop-container: the input row runs the full width of the card and
   paints over its edge ring, with no inset, no padding and no surface of its own. */
.cc-input-row {
    width: 100%;
    box-sizing: border-box;
    padding: 0;
    font-size: 12px;
    overflow: hidden;
    cursor: default;
}

/* The row is the card's bottom edge: follow the card ring's corners (4px minus the 1px ring)
   instead of running square into them — surface, hover/focus overlay and colour fill alike. */
.cc-input-row :deep(.tree-cell),
.cc-input-row :deep(.tree-cell::after),
.cc-input-row :deep(.chip) {
    border-bottom-left-radius: 3px;
    border-bottom-right-radius: 3px;
}

.cc-static-value {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 13px;
    color: var(--text-primary);
}

.cc-static-undef {
    color: var(--text-secondary);
}

.cc-top {
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    display: flex;
    align-items: center;
    /* Fixed 28px band (border-box, so the padding cannot grow it): the pinned corner toggle
       spans the same band, and the hover-revealed select circle cannot change the row height. */
    box-sizing: border-box;
    height: 28px;
    gap: 4px;
    padding: 0 5px;
    pointer-events: none;
    z-index: 2;
}

/* Scrim when there is a title to keep legible, and on hover for every card — the corner
   toggle and select circle then need the same backdrop a title does. */
.cc-top.cc-scrim {
    background: linear-gradient(to bottom, rgba(0, 0, 0, 0.55), rgba(0, 0, 0, 0));
}

/* Only interactive children opt back into pointer events. */
.cc-top > * {
    pointer-events: auto;
}

.cc-select {
    flex-shrink: 0;
}

/* The open/close toggle, pinned to the card's top-left corner: fixed coordinates, so no
   change in the overlay row can move it. Above the scrim (z-index 2) but below the ring.
   A plain div holds the position because wTT has two root nodes (trigger + teleported popup),
   and Vue cannot stamp this component's scope attribute on a fragment root — a scoped class
   put directly on wTT is emitted but never matches. */
.cc-corner-wrap {
    position: absolute;
    top: 0;
    left: 5px;
    z-index: 3;
    /* Span the same 28px band as .cc-top and centre inside it, so the toggle shares the
       overlay row's baseline with the select circle and the title instead of being offset
       by a hand-picked `top`. */
    height: 28px;
    display: inline-flex;
    align-items: center;
}

/* Same disc as the pill buttons, slightly smaller so it does not crowd the title. */
.cc-corner {
    width: 18px;
    height: 18px;
    font-size: 11px;
}

/* Keep the overlay row clear of the pinned toggle: 5px inset + 18px disc + 8px gap. */
.cc-top.cc-indent {
    padding-left: 31px;
}

/* Round icon buttons: subtle glass discs that read on top of a photo. */
.cc-btn {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: rgba(0, 0, 0, 0.45);
    color: #fff;
    font-size: 12px;
    cursor: pointer;
    transition: background-color 0.12s;
}

.cc-btn:hover {
    background: rgba(0, 0, 0, 0.7);
}

.cc-danger:hover {
    background: #dc2626;
}

/* wTT's trigger is an inline span; make it a flex item so the discs stay aligned in the pill. */
.cc-actions :deep(.wtt-trigger) {
    display: inline-flex;
    align-items: center;
}

/* ActionButton2 wraps its slot in its own `.sb` chrome (light hover background + radius), which
   fights the round dark discs used here. Strip it so the wrapped button hovers like a plain .cc-btn. */
.cc-actions :deep(.sb),
.cc-actions :deep(.sb:hover) {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin: 0 !important;
    border-radius: 50% !important;
}

.cc-actions {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 6px;
    border-radius: 999px;
    background: rgba(0, 0, 0, 0.25);
    z-index: 3;
}

.cc-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
    font-weight: 600;
    font-size: 11px;
    color: #fff;
    cursor: text;
}

/* Score badge, top-right on the title line — same color code as the tree view's ClusterBadge. */
.cc-score {
    flex-shrink: 0;
    margin-left: auto;
    font-size: 10px;
    line-height: 1;
}

/* Counts: their own pills at the bottom-left, dark enough to read on any image without
   darkening the whole bottom of the card. */
.cc-counts {
    position: absolute;
    left: 4px;
    bottom: 4px;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 4px;
}

.cc-chip {
    padding: 1px 5px;
    border-radius: 999px;
    background: rgba(0, 0, 0, 0.55);
    font-size: 10px;
    color: #fff;
    white-space: nowrap;
}
</style>
