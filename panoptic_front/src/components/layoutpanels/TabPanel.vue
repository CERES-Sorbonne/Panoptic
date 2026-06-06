<script setup lang="ts">
// Tab bar + filter zone root node — the shared island stacked above the view
// island(s) in the center column. Owns the open tabs and the split toggle.
import IslandPanel from '@/layouts/IslandPanel.vue'
import TabButton from '@/components/mainview/TabButton.vue'
import TextSearchInput from '@/components/inputs/TextSearchInput.vue'
import FilterForm from '@/components/forms/FilterForm.vue'
import GroupForm from '@/components/forms/GroupForm.vue'
import SortForm from '@/components/forms/SortForm.vue'
import { useTabStore } from '@/data/tabStore'
import { useUiStore } from '@/data/uiStore'

const tabStore = useTabStore()
const uiStore = useUiStore()

async function addTab() {
    await tabStore.addTab('New Tab')
}

function toggleFilter() {
    // filter open/close can be wired to a parent or store state if needed
}

function updateSha1Mode(value: boolean) {
    const tab = tabStore.getMainTab()
    if (tab) {
        tab.collection.groupManager.setSha1Mode(value, true)
    }
}



</script>

<template>
    <IslandPanel v-if="tabStore.loaded">
        <template #header>
            <div v-if="tabStore.loaded" class="tab-bar">
                <div class="filter-toggle" @click="toggleFilter">
                    <i v-if="uiStore.panelStates.activeBottomPanel === 'properties'" class="bb bi bi-chevron-down" />
                    <i v-else class="bb bi bi-chevron-right" />
                </div>
                <template v-for="tabId in tabStore.loadedTabs" :key="tabId">
                    <TabButton :tab="tabStore.getTab(tabId)" />
                </template>
                <button class="tab-icon hover-light ps-1 pe-1" @click="addTab" id="add-tab-button">
                    <span class="bi bi-plus"></span>
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

        <div class="content-filter">
            <!-- Single row: text search, instance/image mode, filter, group, sort -->
            <div class="filter-row">
                <TextSearchInput :tab="tabStore.getMainTab()" />

                <div class="tool-group">
                    <button
                        class="tool-sm"
                        :class="{ selected: !tabStore.getMainTab().collection.groupManager.state.sha1Mode }"
                        title="Instance mode"
                        @click="updateSha1Mode(false)"
                    >
                        <i class="bi bi-image"></i>
                    </button>
                    <button
                        class="tool-sm"
                        :class="{ selected: tabStore.getMainTab().collection.groupManager.state.sha1Mode }"
                        title="Image mode"
                        @click="updateSha1Mode(true)"
                    >
                        <i class="bi bi-images"></i>
                    </button>
                </div>

                <FilterForm :tab="tabStore.getMainTab()" />
                <GroupForm :manager="tabStore.getMainTab().collection.groupManager" class="me-1" />
                <SortForm :manager="tabStore.getMainTab().collection.sortManager" class="me-1" />
                <div class="flex-grow-1"></div>
            </div>
        </div>
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

.filter-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 26px;
    cursor: pointer;
    color: var(--text-secondary);
}

.filter-toggle:hover {
    color: var(--text-primary);
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

.content-filter {
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
}

.filter-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-xs) var(--spacing-sm);
}

.sub-row {
    padding-top: 0;
}

.tool-group {
    display: flex;
    align-items: center;
    gap: 2px;
}

.tool-sm {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    background: none;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
    transition: background-color var(--transition-fast);
}

.tool-sm:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.tool-sm.selected {
    background-color: var(--primary-light);
    color: var(--primary);
}

.content-container {
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 5px;
}

.hover-light:hover {
    background-color: var(--hover-bg);
}
</style>
