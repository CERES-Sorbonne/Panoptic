<script setup lang="ts">
import { ComputedRef, computed, inject, ref } from 'vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import { ClusterLine } from '@/data/models'
import { GroupManager, Group, GroupType } from '@/core/GroupManager'
import { useColumnStore } from '@/data/columnStore'
import { useDataStore } from '@/data/dataStore'
import CenteredImage from '@/components/images/CenteredImage.vue'
import ActionButton2 from '@/components/actions/ActionButton2.vue'
import ClusterPropertyInput from './ClusterPropertyInput.vue'
import ClusterBadge from '@/components/cluster/ClusterBadge.vue'
import { isTag } from '@/utils/utils'

// Height reserved below each card's image for the typed property-input row. Must match the
// per-line `size` reserved in ClusterScroller.computeLines.
const INPUT_ROW = 30

const columnStore = useColumnStore()
const data = useDataStore()
const selectNamespace = inject<ComputedRef<string>>('selectNamespace', computed(() => 'global'))

const props = defineProps<{
    imageSize: number
    inputIndex: number
    item: ClusterLine
    parentIds: number[]
    hoverBorder: number
    manager: GroupManager
    properties: any[]
    // Group ids currently open in the right-side inspector panel.
    openedIds: number[]
    // Group ids to highlight (e.g. the clusters created by the last action).
    highlightIds?: number[]
    // Assignment target property — the value each card's top chip reflects. undefined = none.
    targetPropertyId?: number
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'select-cluster', 'reco', 'open-cluster', 'add-clusters', 'delete-cluster', 'assign-cluster-value'])

const hoveredCard = ref<number | null>(null)

// The assignment target property, whose value each card's input edits.
const targetProperty = computed(() =>
    props.targetPropertyId != null ? data.properties?.[props.targetPropertyId] : null)

// Inner (image) width for the card at column `i` — precomputed by the scroller so the
// cards add up to exactly the line width. Falls back to the line's base image size.
function cardInner(i: number) {
    return props.item.cardWidths[i] ?? props.imageSize
}

function getInstanceId(slot: number) {
    return columnStore.instanceIds()[slot]
}

function clusterName(group: Group) {
    return group.name ?? ('Cluster ' + group.parentIdx)
}

// A cluster card: a real Cluster group — a sub-cluster of the parent, or the "New" leftover pile
// of images not covered by any cluster. Only these are deletable; property value-groups are not.
function isClusterCard(group: Group) {
    return group.type === GroupType.Cluster
}

const highlightSet = computed(() => new Set(props.highlightIds ?? []))

// Images of one cluster, for the clustering action (same shape as GroupLine.getImages).
function getClusterImages(group: Group) {
    const ids = columnStore.instanceIds()
    const sha1s = columnStore.sha1s()
    return (group.slots ?? []).map(slot => ({
        id: ids[slot],
        imageUrl: data.baseImgUrl + 'by_size/' + sha1s[slot],
        sha1: sha1s[slot],
    }))
}

// Sub-divide a cluster: bubble the action's result up so the OWNING collection GroupManager
// (not the cluster-view clone) attaches them — otherwise the split doesn't reach the normal
// tree. The clone is rebuilt from the collection tree, so the cluster view still updates.
function addClusters(groupId: number, groups: Group[]) {
    emits('add-clusters', groupId, groups)
}

function isSelected(group: Group) {
    const ns = selectNamespace.value
    columnStore.selectionTick(ns)
    const slots = group.slots ?? []
    if (!slots.length) return false
    return !slots.some(slot => !columnStore.isSelected(slot, ns))
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
                <div class="cluster-image">
                    <CenteredImage
                        v-if="getInstanceId(entry.slot) !== undefined"
                        :instance-id="getInstanceId(entry.slot)"
                        :width="cardInner(i)"
                        :height="props.imageSize"
                        :no-click="true"
                    />
                </div>

                <!-- Top overlay: select circle + cluster name (left), score (right). -->
                <div class="cc-top" :class="{ 'cc-scrim': isClusterCard(entry.group) }">
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

                <!-- Hover action pill, centered over the image: subdivide · inspect · delete. -->
                <div v-show="hoveredCard === entry.group.id" class="cc-actions" @click.stop>
                    <ActionButton2 action="group" :no-border="true"
                        :images="() => getClusterImages(entry.group)"
                        @groups="g => addClusters(entry.group.id, g)">
                        <div class="cc-btn" title="Sub-cluster this group">
                            <i class="bi bi-intersect" />
                        </div>
                    </ActionButton2>
                    <div class="cc-btn" title="Inspect in the side panel"
                        @click.stop="$emit('open-cluster', entry.group.id, $event.shiftKey)">
                        <i class="bi bi-eye" />
                    </div>
                    <div v-if="isClusterCard(entry.group)" class="cc-btn cc-danger" title="Delete this cluster"
                        @click.stop="$emit('delete-cluster', entry.group.id)">
                        <i class="bi bi-trash" />
                    </div>
                </div>

                <!-- Bottom-left image count: a self-contained chip, so no full-width scrim is needed. -->
                <span class="cc-count">
                    <i class="bi bi-images me-1" />{{ entry.group.slots.length }}
                </span>
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
                    :width="cardInner(i)"
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
    background-color: var(--bg-subtle, #f3f4f6);
    border-radius: 5px;
    overflow: hidden;
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
    border-radius: 5px;
    pointer-events: none;
    z-index: 4;
}

.cluster-card.opened::after {
    border: 2px solid var(--primary, #4f46e5);
}

/* Last-made clusters: warm ring so a fresh clustering pass stands out at a glance. */
.cluster-card.highlighted::after {
    border: 2px solid #f59e0b;
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
}

.cluster-image {
    position: absolute;
    inset: 0;
    background-color: var(--bg-subtle, #f3f4f6);
}

.cc-input-row {
    display: flex;
    align-items: center;
    height: 30px;
    padding: 2px 6px;
    background: var(--island-surface, #fff);
    overflow: hidden;
    cursor: default;
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
    gap: 4px;
    padding: 3px 5px;
    pointer-events: none;
    z-index: 2;
}

/* Scrim only when there is a title to keep legible — a nameless card stays clean. */
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

/* Image count: its own pill at the bottom-left, dark enough to read on any image
   without darkening the whole bottom of the card. */
.cc-count {
    position: absolute;
    left: 4px;
    bottom: 4px;
    z-index: 2;
    padding: 1px 5px;
    border-radius: 999px;
    background: rgba(0, 0, 0, 0.55);
    font-size: 10px;
    color: #fff;
    white-space: nowrap;
}
</style>
