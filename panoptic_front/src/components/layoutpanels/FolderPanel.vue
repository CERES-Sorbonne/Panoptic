<script setup lang="ts">
// Folders tool-window root node — inserted into the sidebar split's #primary.
import IslandPanel from '@/layouts/IslandPanel.vue'
import { useUiStore } from '@/data/uiStore'

const uiStore = useUiStore()

const folderTree = [
    { id: 1, name: 'panoptic_back', type: 'module', depth: 0 },
    { id: 2, name: 'PanopticML', type: 'module', depth: 0 },
    { id: 3, name: 'External Libraries', type: 'libs', depth: 0 },
    { id: 4, name: 'Scratches and Consoles', type: 'libs', depth: 0 },
]
</script>

<template>
    <IslandPanel grow>
        <template #header>
            <div class="tw-header">
                <span class="tw-title">Folders</span>
                <div class="tw-actions">
                    <button class="tw-action" title="Options">⋯</button>
                    <button class="tw-action" title="Hide" @click="uiStore.panelStates.leftPanelOpen = false">－</button>
                </div>
            </div>
        </template>
        <div class="tw-body">
            <div
                v-for="node in folderTree"
                :key="node.id"
                class="tree-node"
                :style="{ paddingLeft: 8 + node.depth * 14 + 'px' }"
            >
                <span class="tree-caret">›</span>
                <span class="tree-icon" :class="node.type">{{ node.type === 'module' ? '▣' : '▤' }}</span>
                <span class="tree-label">{{ node.name }}</span>
            </div>
        </div>
    </IslandPanel>
</template>

<style scoped>
/* Tool window header (shared pattern across panels) */
.tw-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 30px;
    padding: 0 var(--spacing-sm);
}

.tw-title {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.02em;
}

.tw-actions {
    display: flex;
    gap: 2px;
}

.tw-action {
    width: 22px;
    height: 22px;
    background: none;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-tertiary);
}

.tw-action:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.tw-body {
    flex: 1;
    min-height: 0;
    overflow: auto;
    padding: var(--spacing-xs) 0;
}

/* Project tree */
.tree-node {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 24px;
    padding: 0 var(--spacing-sm);
    cursor: default;
    white-space: nowrap;
}

.tree-node:hover {
    background-color: var(--hover-bg);
}

.tree-caret {
    color: var(--text-tertiary);
    width: 10px;
}

.tree-icon.module {
    color: var(--primary);
}

.tree-icon.libs {
    color: var(--accent-orange);
}

.tree-label {
    color: var(--text-primary);
}
</style>
