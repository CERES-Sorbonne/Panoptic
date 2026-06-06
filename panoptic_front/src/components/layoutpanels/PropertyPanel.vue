<script setup lang="ts">
// Properties / Export tool-window root node — inserted into the sidebar
// split's #secondary. Shows either the property list or the export actions
// depending on which bottom panel is active.
import IslandPanel from '@/layouts/IslandPanel.vue'
import { useUiStore } from '@/data/uiStore'

const uiStore = useUiStore()

const properties = [
    { id: 1, name: 'name', value: 'data_reader.py' },
    { id: 2, name: 'size', value: '4.2 KB' },
    { id: 3, name: 'type', value: 'Python file' },
    { id: 4, name: 'encoding', value: 'UTF-8' },
    { id: 5, name: 'line endings', value: 'LF' },
]

const exportFormats = [
    { id: 'csv', label: 'Export as CSV' },
    { id: 'json', label: 'Export as JSON' },
    { id: 'images', label: 'Export images' },
]
</script>

<template>
    <IslandPanel grow>
        <template #header>
            <div class="tw-header">
                <span class="tw-title">{{ uiStore.panelStates.activeBottomPanel === 'export' ? 'Export' : 'Properties' }}</span>
                <div class="tw-actions">
                    <button class="tw-action" title="Options">⋯</button>
                    <button class="tw-action" title="Hide" @click="uiStore.panelStates.activeBottomPanel = null">－</button>
                </div>
            </div>
        </template>
        <div class="tw-body">
            <template v-if="uiStore.panelStates.activeBottomPanel === 'export'">
                <button v-for="fmt in exportFormats" :key="fmt.id" class="export-row">
                    <span class="export-icon">⤓</span>
                    <span>{{ fmt.label }}</span>
                </button>
            </template>
            <template v-else>
                <div v-for="prop in properties" :key="prop.id" class="prop-row">
                    <span class="prop-name">{{ prop.name }}</span>
                    <span class="prop-value">{{ prop.value }}</span>
                </div>
            </template>
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

/* Properties list */
.prop-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    height: 24px;
    padding: 0 var(--spacing-sm);
    white-space: nowrap;
}

.prop-row:hover {
    background-color: var(--hover-bg);
}

.prop-name {
    width: 90px;
    flex-shrink: 0;
    color: var(--text-secondary);
}

.prop-value {
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Export list */
.export-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    width: 100%;
    height: 30px;
    padding: 0 var(--spacing-sm);
    background: none;
    border: none;
    text-align: left;
    color: var(--text-primary);
    font-size: var(--font-size-sm);
    transition: background-color var(--transition-fast);
}

.export-row:hover {
    background-color: var(--hover-bg);
}

.export-icon {
    color: var(--text-secondary);
}
</style>
