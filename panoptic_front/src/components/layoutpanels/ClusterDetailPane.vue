<script setup lang="ts">
// A single cluster inspector pane (header with a close button + an ImageScroller).
// Rendered on the right side of the ClusterView, one or two stacked at a time.
// It shows a plain list of the cluster's instances; when two panes are open they share a
// `dragGroup` so images can be dragged between the two clusters.
import ImageScroller from '@/components/scrollers/image/ImageScroller.vue'
import ClusterPropertyInput from '@/components/scrollers/cluster/ClusterPropertyInput.vue'
import { computed } from 'vue'
import { Instance, Property } from '@/data/models'

const props = defineProps<{
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
    // The leaf grouping property (the assignment target), and this group's value on it — same
    // pair the cluster cards show. Absent when the view has no grouping: then no input is shown.
    targetProperty?: Property
    targetValue?: any
}>()

defineEmits<{
    close: []
    // The typed value picked in the header input, to assign to the whole inspected group.
    'assign-value': [value: any]
    'instance-added': [payload: { instance: Instance, index: number }]
    'instance-removed': [payload: { instance: Instance }]
}>()

// Horizontal padding of the header (2 × --spacing-sm), taken out before splitting the
// header in two so the name and the value input each get exactly half of it.
const HEADER_PADDING = 16
// The input's half of the header — both its resting width and the cap on its edit popup,
// so opening the input never spills over the group name.
const halfWidth = computed(() => Math.max(40, Math.round((props.width - HEADER_PADDING) / 2)))
</script>

<template>
    <div class="cluster-detail" :class="position">
        <div class="cluster-header">
            <div class="cluster-title">
                <button class="detail-close" @click="$emit('close')">&times;</button>
                <span class="detail-name">{{ name }}</span>
            </div>
            <!-- Same typed input as the cluster cards: editing it assigns the value to the
                 whole inspected pile. -->
            <div v-if="targetProperty" class="detail-input" @click.stop>
                <ClusterPropertyInput
                    :property="targetProperty"
                    :model-value="targetValue"
                    :instance-id="instances[0]?.id"
                    :width="halfWidth"
                    :max-width="halfWidth"
                    @update:model-value="v => $emit('assign-value', v)"
                />
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
    /* Fixed half of the header: the name half never grows, and never shrinks when the
       value input on the other half renders a wide value. */
    flex: 0 0 50%;
    display: flex;
    min-width: 0;
    overflow: hidden;
    align-items: center;
    gap: var(--spacing-xs);
    font-size: var(--font-size-md, 15px);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.detail-input {
    /* The other fixed half — an open text input can't push past it. */
    flex: 0 0 50%;
    min-width: 0;
    overflow: hidden;
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
