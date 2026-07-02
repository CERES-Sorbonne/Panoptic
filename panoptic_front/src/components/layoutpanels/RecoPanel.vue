<script setup lang="ts">
// One labeled, collapsible panel inside the reco workspace. Wraps a virtualized
// TreeScroller sized to its own body via a ResizeObserver (same pattern as
// ViewPanel). Fed a standalone GroupManager built from an arbitrary image list
// (queue / group / blacklist). When collapsed only the header remains.
import { onMounted, onUnmounted, ref } from 'vue'
import IslandPanel from '@/layouts/IslandPanel.vue'
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue'
import { GroupManager } from '@/core/GroupManager'

const props = defineProps<{
    title: string
    count: number
    groupManager: GroupManager
    ready: boolean
    imageSize: number
    inputKey: string
    collapsed?: boolean
    emptyMessage?: string
}>()

const emit = defineEmits(['toggle'])

const bodyRef = ref<HTMLElement>()
const dims = ref({ width: 0, height: 0 })

let observer: ResizeObserver | null = null

onMounted(() => {
    if (bodyRef.value) {
        observer = new ResizeObserver(entries => {
            for (const entry of entries) {
                const { width, height } = entry.contentRect
                dims.value = { width, height }
            }
        })
        observer.observe(bodyRef.value)
    }
})

onUnmounted(() => {
    if (observer && bodyRef.value) observer.unobserve(bodyRef.value)
})
</script>

<template>
    <IslandPanel :grow="!collapsed">
        <template #header>
            <div class="tw-header" @click="emit('toggle')">
                <button class="collapse-btn" @click.stop="emit('toggle')">
                    <i :class="collapsed ? 'bi bi-chevron-right' : 'bi bi-chevron-down'"></i>
                </button>
                <span class="tw-title">{{ title }}</span>
                <span class="tw-count">{{ count }}</span>
            </div>
        </template>
        <!-- v-show (not v-if) keeps the observed element mounted across collapse. -->
        <div v-show="!collapsed" ref="bodyRef" class="panel-body">
            <TreeScroller
                v-if="ready && dims.width > 0 && dims.height > 0 && count > 0"
                :input-key="inputKey"
                :group-manager="groupManager"
                :image-size="imageSize"
                :height="dims.height"
                :width="dims.width"
                :properties="[]"
                :hide-group="true"
                :hide-options="true"
                :hide-if-modal="true"
            />
            <div v-else-if="count === 0" class="panel-empty text-secondary">
                {{ emptyMessage ?? '—' }}
            </div>
        </div>
    </IslandPanel>
</template>

<style scoped>
.tw-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    height: 26px;
    padding: 0 var(--spacing-xs);
    background-color: var(--bg-secondary);
    cursor: pointer;
    user-select: none;
}

.collapse-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border: none;
    background: none;
    padding: 0;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 11px;
}

.tw-title {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.02em;
}

.tw-count {
    font-size: var(--font-size-xs);
    color: var(--text-tertiary);
}

.panel-body {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow: hidden;
}

.panel-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    font-size: 13px;
}
</style>
