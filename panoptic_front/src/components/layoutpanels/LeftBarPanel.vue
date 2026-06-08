<script setup lang="ts">
// Left activity bar root node — inserted into AppShellLayout's #activity slot.
// Toggles the folder panel and the bottom (properties / export) panels.
import { useUiStore, type BottomPanel } from '@/data/uiStore'

const uiStore = useUiStore()

// Activity-bar panel toggles: Folders, separated from Properties + Export.
const folderPanels = [
    { id: 'folders', icon: 'bi-folder2-open', title: 'Folders' },
]

const bottomPanels = [
    { id: 'properties', icon: 'bi-list-ul', title: 'Properties' },
    { id: 'export', icon: 'bi-download', title: 'Export' },
]

function togglePanel(id: string) {
    if (id === 'folders') {
        uiStore.panelStates.leftPanelOpen = !uiStore.panelStates.leftPanelOpen
        return
    }
    uiStore.panelStates.activeBottomPanel = uiStore.panelStates.activeBottomPanel === id ? null : (id as BottomPanel)
}

function isPanelActive(id: string) {
    if (id === 'folders') return uiStore.panelStates.leftPanelOpen
    return uiStore.panelStates.activeBottomPanel === id
}
</script>

<template>
    <div class="activity">
        <div class="activity-group">
            <button
                v-for="t in folderPanels"
                :key="t.id"
                class="activity-btn"
                :class="{ active: isPanelActive(t.id) }"
                :title="t.title"
                @click="togglePanel(t.id)"
            ><i :class="'bi ' + t.icon"></i></button>
            <div class="activity-sep"></div>
            <button
                v-for="t in bottomPanels"
                :key="t.id"
                class="activity-btn"
                :class="{ active: isPanelActive(t.id) }"
                :title="t.title"
                @click="togglePanel(t.id)"
            ><i :class="'bi ' + t.icon"></i></button>
        </div>
    </div>
</template>

<style scoped>
.activity {
    display: flex;
    flex-direction: column;
    width: 100%;
    padding: var(--spacing-xs) 0;
}

.activity-group {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
}

.activity-sep {
    width: 20px;
    height: 1px;
    margin: var(--spacing-xs) 0;
    background-color: var(--border-light);
}

.activity-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    background: none;
    border: none;
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    font-size: 16px;
    transition: background-color var(--transition-fast);
}

.activity-btn:hover {
    background-color: var(--hover-bg);
}

.activity-btn.active {
    background-color: var(--primary-light);
    color: var(--primary);
}
</style>
