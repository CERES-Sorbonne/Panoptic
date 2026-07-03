<script setup lang="ts">
import { ComputedRef, computed, inject, ref } from 'vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import { ClusterLine } from '@/data/models'
import { GroupManager, Group } from '@/core/GroupManager'
import { useColumnStore } from '@/data/columnStore'
import CenteredImage from '@/components/images/CenteredImage.vue'

const columnStore = useColumnStore()
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

const emits = defineEmits(['hover', 'unhover', 'scroll', 'select-cluster', 'reco', 'open-cluster'])

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
            @click="$emit('open-cluster', entry.group.id, $event.shiftKey)"
        >
            <div class="cluster-image" :style="{ width: cardInner(i) + 'px', height: props.imageSize + 'px' }">
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
                    class="cluster-select"
                    :light-mode="true"
                />
            </div>
            <div class="cluster-info">
                <span class="cluster-name-text">{{ clusterName(entry.group) }}</span>
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
            :style="{ width: cardInner(props.item.data.length + n - 1) + 2 + 'px', height: props.imageSize + 30 + 'px' }"
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

/* Clusters open in the right inspector get a colored label bar. */
.cluster-card.opened .cluster-info {
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

.cluster-info {
    display: flex;
    align-items: center;
    height: 30px;
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
}

.cluster-badge {
    flex-shrink: 0;
    padding: 0px 5px;
    border-radius: 4px;
    font-size: 10px;
    line-height: 16px;
    margin-left: 4px;
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
