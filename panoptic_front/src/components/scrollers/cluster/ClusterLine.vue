<script setup lang="ts">
import { ComputedRef, computed, inject, nextTick, ref } from 'vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import PropertyValue from '@/components/properties/PropertyValue.vue'
import { ClusterLine } from '@/data/models'
import { GroupManager, Group, GroupType } from '@/core/GroupManager'
import { useColumnStore } from '@/data/columnStore'
import { useDataStore } from '@/data/dataStore'
import CenteredImage from '@/components/images/CenteredImage.vue'
import ActionButton2 from '@/components/actions/ActionButton2.vue'
import { badgeState } from '@/core/group/clusterOverlay'
import { isTag } from '@/utils/utils'

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
    // Assignment target property — the value each card's badge reflects. undefined = none.
    targetPropertyId?: number
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'select-cluster', 'reco', 'open-cluster', 'add-clusters', 'rename-cluster', 'delete-cluster', 'assign-cluster'])

const hoveredCard = ref<number | null>(null)

// ── Inline assignment (click the tag icon → type a value → commit) ────────────
const assigningId = ref<number | null>(null)
const assignText = ref('')
const assignInput = ref<HTMLInputElement | null>(null)

function startAssign(group: Group) {
    assigningId.value = group.id
    assignText.value = ''
    nextTick(() => { assignInput.value?.focus() })
}

function commitAssign(group: Group) {
    if (assigningId.value !== group.id) return
    const v = assignText.value.trim()
    assigningId.value = null
    if (v) emits('assign-cluster', group.id, v)
}

function cancelAssign() {
    assigningId.value = null
}

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

// A property group's label is its real property value (rendered via <PropertyValue>), not a
// "Cluster N" fallback. Only real Cluster groups use the editable text name.
function isPropertyGroup(group: Group) {
    return group.type === GroupType.Property && (group.meta?.propertyValues?.length ?? 0) > 0
}

// ── Inline rename (double-click the name) ────────────────────────────────────
const editingId = ref<number | null>(null)
const editValue = ref('')
const nameInput = ref<HTMLInputElement | null>(null)

function startRename(group: Group) {
    editingId.value = group.id
    editValue.value = clusterName(group)
    nextTick(() => { nameInput.value?.focus(); nameInput.value?.select() })
}

function commitRename(group: Group) {
    if (editingId.value !== group.id) return
    const v = editValue.value.trim()
    editingId.value = null
    // Rename on the OWNING collection GroupManager (not the cluster-view clone) so the new
    // name also shows in the normal tree; the version bump re-clones the cluster view.
    if (v) emits('rename-cluster', group.id, v)
}

function cancelRename() {
    editingId.value = null
}

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

// ── Target-property badge (homogeneity of the cluster on the assignment target) ──
// Precomputed per line so each card reads it by group id. Recomputes when the target or the
// line's data changes; value edits reflow the line via the manager version bump.
const targetBadges = computed(() => {
    const m = new Map<number, { label: string, mixed: boolean }>()
    const pid = props.targetPropertyId
    if (pid == null) return m
    const prop = data.properties?.[pid]
    const tag = prop ? isTag(prop.type) : false
    const read = (slot: number) => columnStore.readSlot(pid, slot)
    const canon = tag ? (v: unknown) => Array.isArray(v) ? v.slice().sort().join(',') : v : undefined
    for (const entry of props.item.data) {
        const g = entry.group
        const b = badgeState(g.slots ?? [], read, canon)
        if (b.kind === 'empty') continue
        if (b.kind === 'mixed') { m.set(g.id, { label: '⇄ ' + b.count, mixed: true }); continue }
        m.set(g.id, { label: formatValue(pid, b.value), mixed: false })
    }
    return m
})

function formatValue(pid: number, v: unknown): string {
    const prop = data.properties?.[pid]
    if (Array.isArray(v)) return v.map(id => data.tags?.[id]?.value ?? id).join(', ')
    if (prop && isTag(prop.type)) return data.tags?.[v as number]?.value ?? String(v)
    return String(v)
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
            :class="{ opened: props.openedIds.includes(entry.group.id) }"
            :style="{ width: cardInner(i) + 2 + 'px' }"
            @mouseenter="hoveredCard = entry.group.id"
            @mouseleave="hoveredCard = null"
        >
            <div class="cluster-header">
                <input v-if="editingId === entry.group.id" ref="nameInput" v-model="editValue"
                    class="cluster-name-input" @click.stop @dblclick.stop
                    @keydown.enter="commitRename(entry.group)" @keydown.esc="cancelRename"
                    @blur="commitRename(entry.group)" />
                <span v-else-if="isPropertyGroup(entry.group)" class="cluster-name-text cluster-name-prop">
                    <PropertyValue :value="entry.group.meta.propertyValues[0]" />
                </span>
                <span v-else class="cluster-name-text" @dblclick.stop="startRename(entry.group)">{{ clusterName(entry.group) }}</span>
                <!-- Sub-cluster this group. @click.stop so the card's open-cluster click doesn't fire. -->
                <div class="cluster-header-action" @click.stop>
                    <ActionButton2 action="group" :no-border="true"
                        :images="() => getClusterImages(entry.group)"
                        @groups="g => addClusters(entry.group.id, g)">
                        <i class="bi bi-diagram-2 cluster-cluster-btn" />
                    </ActionButton2>
                </div>
                <!-- Assign the target property's value to this whole cluster. -->
                <div v-if="props.targetPropertyId != null" class="cluster-header-action"
                    @click.stop="startAssign(entry.group)" title="Assign a value to this cluster">
                    <i class="bi bi-tag cluster-cluster-btn" />
                </div>
                <!-- Delete this group: its images move to the leftover "Unclustered" bucket. -->
                <div class="cluster-header-action" @click.stop="$emit('delete-cluster', entry.group.id)">
                    <i class="bi bi-trash cluster-cluster-btn" />
                </div>
            </div>
            <!-- Only clicking the image opens the cluster in the split window (not the name). -->
            <div class="cluster-image" :style="{ width: cardInner(i) + 'px', height: props.imageSize + 'px', cursor: 'pointer' }"
                @click="$emit('open-cluster', entry.group.id, $event.shiftKey)">
                <CenteredImage
                    v-if="getInstanceId(entry.slot) !== undefined"
                    :instance-id="getInstanceId(entry.slot)"
                    :width="cardInner(i)"
                    :height="props.imageSize"
                    :no-click="true"
                />
                <SelectCircle
                    v-if="hoveredCard === entry.group.id || isSelected(entry.group)"
                    :model-value="isSelected(entry.group)"
                    @update:model-value="$emit('select-cluster', entry.group.id)"
                    @click.stop
                    class="cluster-select"
                    :light-mode="true"
                />
            </div>
            <div class="cluster-footer">
                <template v-if="assigningId === entry.group.id">
                    <input ref="assignInput" v-model="assignText" class="assign-input" placeholder="value…"
                        @click.stop @keydown.enter="commitAssign(entry.group)" @keydown.esc="cancelAssign"
                        @blur="commitAssign(entry.group)" />
                </template>
                <template v-else>
                    <span class="cluster-badge cluster-badge-count"><i class="bi bi-image me-1"></i>{{ entry.group.slots.length }}</span>
                    <span v-if="targetBadges.get(entry.group.id)" class="cluster-badge cluster-badge-target"
                        :class="{ mixed: targetBadges.get(entry.group.id)!.mixed }"
                        :title="targetBadges.get(entry.group.id)!.label">{{ targetBadges.get(entry.group.id)!.label }}</span>
                    <span v-else-if="entry.group.score?.value != undefined" class="cluster-badge cluster-badge-score">{{ Math.round(entry.group.score.value) }}</span>
                </template>
            </div>
        </div>
        <!-- Reserve the space of the images missing from this (partial) line so it keeps
             the same card size as a full line instead of stretching to fill the gap. -->
        <div
            v-for="n in props.item.emptyCount"
            :key="'empty-' + n"
            class="cluster-card cluster-card-empty me-2 mb-2"
            :style="{ width: cardInner(props.item.data.length + n - 1) + 2 + 'px', height: props.imageSize + 44 + 'px' }"
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

.cluster-card {
    position: relative;
    background-color: white;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    overflow: hidden;
    cursor: pointer;
}

/* Clusters open in the right inspector get a colored header bar. */
.cluster-card.opened .cluster-header {
    background: var(--primary-light);
}

.cluster-card-empty {
    visibility: hidden;
    pointer-events: none;
    border: none;
}

.cluster-image {
    position: relative;
    background-color: white;
}

/* Header above the image: the cluster name. */
.cluster-header {
    display: flex;
    align-items: center;
    height: 22px;
    padding: 0 4px;
    background: var(--bg-subtle);
    border-bottom: 1px solid var(--border-color);
}

/* Footer below the image: image count (left), cluster score (right). */
.cluster-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 22px;
    padding: 0 4px;
    font-size: 10px;
    color: var(--text-secondary);
    background: var(--bg-subtle);
    border-top: 1px solid var(--border-color);
}

.cluster-name-text {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
    font-weight: 600;
    font-size: 11px;
    color: var(--text-primary);
    cursor: text;
}

/* Property-group label: the real value chip, non-editable. */
.cluster-name-prop {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    cursor: default;
}

.cluster-name-input {
    flex: 1;
    min-width: 0;
    font-weight: 600;
    font-size: 11px;
    color: var(--text-primary);
    background: var(--island-surface, #fff);
    border: 1px solid var(--primary, #4f46e5);
    border-radius: 3px;
    padding: 0 3px;
    height: 18px;
    outline: none;
}

.cluster-header-action {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    margin-left: 4px;
}

.cluster-cluster-btn {
    font-size: 13px;
    line-height: 1;
    color: var(--text-secondary);
    cursor: pointer;
}

.cluster-header-action:hover .cluster-cluster-btn {
    color: var(--text-primary);
}

.cluster-badge {
    flex-shrink: 0;
    padding: 0px 5px;
    border-radius: 4px;
    font-size: 10px;
    line-height: 16px;
}

.cluster-badge-count {
    background: var(--border-color);
    color: var(--text-secondary);
}

.cluster-badge-score {
    background: #d1fae5;
    color: #065f46;
}

/* Assignment-target value badge: a single common value, or amber "mixed" when heterogeneous. */
.cluster-badge-target {
    max-width: 60%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    background: var(--primary-light, #e0e7ff);
    color: var(--primary, #4f46e5);
}

.cluster-badge-target.mixed {
    background: #fef3c7;
    color: #92400e;
}

.assign-input {
    flex: 1;
    min-width: 0;
    font-size: 10px;
    height: 16px;
    padding: 0 4px;
    border: 1px solid var(--primary, #4f46e5);
    border-radius: 4px;
    outline: none;
    background: var(--island-surface, #fff);
    color: var(--text-primary);
}

.cluster-select {
    position: absolute;
    top: 2px;
    left: 2px;
}
</style>
