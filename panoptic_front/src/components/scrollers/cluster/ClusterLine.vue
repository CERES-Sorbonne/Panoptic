<script setup lang="ts">
import { ComputedRef, computed, inject, nextTick, ref } from 'vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import { ClusterLine } from '@/data/models'
import { GroupManager, Group } from '@/core/GroupManager'
import { useColumnStore } from '@/data/columnStore'
import { useDataStore } from '@/data/dataStore'
import CenteredImage from '@/components/images/CenteredImage.vue'
import ActionButton2 from '@/components/actions/ActionButton2.vue'

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
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'select-cluster', 'reco', 'open-cluster', 'add-clusters', 'rename-cluster', 'delete-cluster'])

const hoveredCard = ref<number | null>(null)

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
                <span v-else class="cluster-name-text" @dblclick.stop="startRename(entry.group)">{{ clusterName(entry.group) }}</span>
                <!-- Sub-cluster this group. @click.stop so the card's open-cluster click doesn't fire. -->
                <div class="cluster-header-action" @click.stop>
                    <ActionButton2 action="group" :no-border="true"
                        :images="() => getClusterImages(entry.group)"
                        @groups="g => addClusters(entry.group.id, g)">
                        <i class="bi bi-diagram-2 cluster-cluster-btn" />
                    </ActionButton2>
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
                <span class="cluster-badge cluster-badge-count"><i class="bi bi-image me-1"></i>{{ entry.group.slots.length }}</span>
                <span v-if="entry.group.score?.value != undefined" class="cluster-badge cluster-badge-score">{{ Math.round(entry.group.score.value) }}</span>
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

.cluster-select {
    position: absolute;
    top: 2px;
    left: 2px;
}
</style>
