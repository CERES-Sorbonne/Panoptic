<script setup lang="ts">
// Tab bar island — the open tabs, add-tab button, and the split toggle. The
// filter zone is now a separate island (FilterPanel) so it can split per-view.
import IslandPanel from '@/layouts/IslandPanel.vue'
import TabButton from '@/components/mainview/TabButton.vue'
import { useTabStore } from '@/data/tabStore'
import { useUiStore } from '@/data/uiStore'
import { useCurrentTab } from '@/data/useCurrentTab'

const tabStore = useTabStore()
const uiStore = useUiStore()
const tab = useCurrentTab()

async function addTab() {
    await tabStore.addTab('New Tab')
}

function toggleFilter() {
    // filter open/close can be wired to a parent or store state if needed
}

function toggleSplit() {
    if (tab.value) tab.value.state.splitView = !tab.value.state.splitView
}
</script>

<template>
    <IslandPanel v-if="tabStore.loaded">
        <div class="tab-bar">
            <div class="tab-tool" @click="toggleFilter">
                <i v-if="uiStore.panelStates.activeBottomPanel === 'properties'" class="bi bi-chevron-down" />
                <i v-else class="bi bi-chevron-right" />
            </div>
            <template v-for="tabId in tabStore.loadedTabs" :key="tabId">
                <TabButton :tab="tabStore.getTab(tabId)" />
            </template>
            <button class="tab-tool" @click="addTab" id="add-tab-button" title="New tab">
                <span class="bi bi-plus"></span>
            </button>
            <div class="tab-spacer"></div>
            <button
                class="tab-tool"
                :class="{ active: tab?.state.splitView }"
                :title="tab?.state.splitView ? 'Unsplit' : 'Split right'"
                @click="toggleSplit"
            >⫿</button>
        </div>
    </IslandPanel>
</template>

<style scoped>
.tab-bar {
    display: flex;
    align-items: center;
    height: 28px;
    padding: 0 4px;
    gap: 2px;
}

/* Compact, borderless PyCharm-style icon button used for the chevron, add-tab
   and split toggle. Neutralises the global <button> border/background. */
.tab-tool {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border: none !important;
    background: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: 14px;
    line-height: 1;
    cursor: pointer;
    transition: background-color var(--transition-fast), color var(--transition-fast);
}

.tab-tool:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.tab-tool.active {
    background-color: var(--primary-light);
    color: var(--primary);
}

.tab-spacer {
    flex: 1;
}
</style>
