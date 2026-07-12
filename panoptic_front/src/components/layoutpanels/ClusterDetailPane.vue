<script setup lang="ts">
// A single cluster inspector pane (header with a close button + an ImageScroller).
// Rendered on the right side of the ClusterView, one or two stacked at a time.
// It shows a plain list of the cluster's instances; when two panes are open they share a
// `dragGroup` so images can be dragged between the two clusters.
import ImageScroller from '@/components/scrollers/image/ImageScroller.vue'
import { Instance, Property } from '@/data/models'

defineProps<{
    inputKey: string
    instances: Instance[]
    name: string
    imageSize: number
    width: number
    height: number
    properties: Property[]
    // Shared vuedraggable group so images can be dragged between the two stacked panes.
    dragGroup?: string
    // Which touching corners round: single pane, or the top / bottom of a stack.
    position: 'solo' | 'top' | 'bottom'
}>()

defineEmits<{
    close: []
    'instance-added': [payload: { instance: Instance, index: number }]
    'instance-removed': [payload: { instance: Instance }]
}>()
</script>

<template>
    <div class="cluster-detail" :class="position">
        <div class="cluster-header">
            <div class="cluster-title">
                <button class="detail-close" @click="$emit('close')">&times;</button>
                <span class="detail-name">{{ name }}</span>
            </div>
        </div>
        <ImageScroller
            :input-key="inputKey"
            :select-namespace="inputKey"
            :instances="instances"
            :drag-group="dragGroup"
            :image-size="imageSize"
            :height="height"
            :width="width"
            :properties="properties"
            :hide-if-modal="true"
            @instance-added="$emit('instance-added', $event)"
            @instance-removed="$emit('instance-removed', $event)"
        />
    </div>
</template>

<style scoped>
.cluster-detail {
    display: flex;
    flex-direction: column;
    flex: 1;
    height: 100%;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    background-color: var(--island-surface);
}

/* Only the corners that face a gap (never an outer container edge) are rounded.
   Every detail pane sits against the primary pane on its left, so its left
   corners always round; the mutual edge of a stacked pair rounds too. */
.cluster-detail.solo {
    border-top-left-radius: var(--island-radius);
    border-bottom-left-radius: var(--island-radius);
}

.cluster-detail.top {
    border-top-left-radius: var(--island-radius);
    border-bottom-left-radius: var(--island-radius);
    border-bottom-right-radius: var(--island-radius);
}

.cluster-detail.bottom {
    border-top-left-radius: var(--island-radius);
    border-top-right-radius: var(--island-radius);
    border-bottom-left-radius: var(--island-radius);
}

.cluster-header {
    flex-shrink: 0;
    height: 32px;
    display: flex;
    align-items: center;
    padding: 0 var(--spacing-sm);
}

.cluster-title {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    font-size: var(--font-size-md, 15px);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.detail-close {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border: none;
    background: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 16px;
    line-height: 1;
    margin-right: var(--spacing-xs);
}

.detail-close:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.detail-name {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>
