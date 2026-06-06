<script setup lang="ts">
// Tab bar + filter zone root node — the shared island stacked above the view
// island(s) in the center column. Owns the open tabs and the split toggle.
import { ref } from 'vue'
import IslandPanel from '@/layouts/IslandPanel.vue'
import ContentFilterSim from '@/components/mainview/ContentFilterSim.vue'
import { useUiStore } from '@/data/uiStore'

const uiStore = useUiStore()

const activeTab = ref(1)

const editorTabs = [
    { id: 1, name: 'media_db.py', modified: false },
    { id: 2, name: 'data_reader.py', modified: true },
    { id: 3, name: 'project_routes.py', modified: false },
]

function selectTab(id: number) {
    activeTab.value = id
}
</script>

<template>
    <IslandPanel>
        <template #header>
            <div class="tab-bar">
                <button
                    v-for="tab in editorTabs"
                    :key="tab.id"
                    class="tab"
                    :class="{ active: tab.id === activeTab }"
                    @click="selectTab(tab.id)"
                >
                    <span class="tab-icon">🐍</span>
                    <span class="tab-name">{{ tab.name }}</span>
                    <span class="tab-close">{{ tab.modified ? '●' : '×' }}</span>
                </button>
                <div class="tab-spacer"></div>
                <button
                    class="tab-action"
                    :class="{ active: uiStore.panelStates.viewSplitEnabled }"
                    :title="uiStore.panelStates.viewSplitEnabled ? 'Unsplit' : 'Split right'"
                    @click="uiStore.panelStates.viewSplitEnabled = !uiStore.panelStates.viewSplitEnabled"
                >⫿</button>
            </div>
        </template>
        <ContentFilterSim />
    </IslandPanel>
</template>

<style scoped>
.tab-bar {
    display: flex;
    align-items: center;
    height: 34px;
    padding: 4px 4px 0;
    gap: 2px;
    border-bottom: 1px solid var(--border-light);
}

.tab-spacer {
    flex: 1;
}

.tab-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    background: none;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    transition: background-color var(--transition-fast);
}

.tab-action:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.tab-action.active {
    background-color: var(--primary-light);
    color: var(--primary);
}

.tab {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 0 10px;
    background: none;
    border: none;
    border-radius: var(--radius-md) var(--radius-md) 0 0;
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
    white-space: nowrap;
    transition: background-color var(--transition-fast);
}

.tab:hover {
    background-color: var(--hover-bg);
}

.tab.active {
    background-color: var(--primary-light);
    color: var(--text-primary);
    font-weight: var(--font-weight-medium);
}

.tab-icon {
    font-size: 11px;
}

.tab-close {
    color: var(--text-tertiary);
    font-size: 11px;
}
</style>
