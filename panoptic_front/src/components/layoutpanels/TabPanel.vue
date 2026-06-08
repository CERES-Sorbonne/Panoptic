<script setup lang="ts">
// Tab bar + filter zone root node — the shared island stacked above the view
// island(s) in the center column. Owns the open tabs and the split toggle.
import IslandPanel from '@/layouts/IslandPanel.vue'
import TabButton from '@/components/mainview/TabButton.vue'
import TextSearchInput from '@/components/inputs/TextSearchInput.vue'
import FilterForm from '@/components/forms/FilterForm.vue'
import GroupForm from '@/components/forms/GroupForm.vue'
import SortForm from '@/components/forms/SortForm.vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
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

function updateSha1Mode(value: boolean) {
    if (tab.value) {
        tab.value.collection.groupManager.setSha1Mode(value, true)
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
                    :class="{ active: tab?.state.splitView }"
                    :title="tab?.state.splitView ? 'Unsplit' : 'Split right'"
                    @click="toggleSplit"
                >⫿</button>
            </div>
        </template>

        <div class="content-filter" v-if="tab">
            <!-- Single row: text search, instance/image mode, filter, group, sort -->
            <div class="filter-row">
                <TextSearchInput :tab="tab" />

                <Dropdown placement="bottom-start">
                    <template #button>
                        <button
                            class="tool-sm mode-trigger"
                            :title="tab.collection.groupManager.state.sha1Mode ? 'Image mode' : 'Instance mode'"
                        >
                            <i :class="tab.collection.groupManager.state.sha1Mode ? 'bi bi-images' : 'bi bi-image'"></i>
                            <!-- <i class="bi bi-chevron-down mode-chevron"></i> -->
                        </button>
                    </template>
                    <template #popup="{ hide }">
                        <div class="mode-menu">
                            <div
                                class="mode-option"
                                :class="{ selected: !tab.collection.groupManager.state.sha1Mode }"
                                @click="updateSha1Mode(false); hide()"
                            >
                                <i class="bi bi-image"></i><span>Instance</span>
                            </div>
                            <div
                                class="mode-option"
                                :class="{ selected: tab.collection.groupManager.state.sha1Mode }"
                                @click="updateSha1Mode(true); hide()"
                            >
                                <i class="bi bi-images"></i><span>Image</span>
                            </div>
                        </div>
                    </template>
                </Dropdown>

                <FilterForm :tab="tab" />
                <GroupForm :manager="tab.collection.groupManager" class="me-1" />
                <SortForm :manager="tab.collection.sortManager" class="me-1" />
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

.mode-trigger {
    width: auto;
    gap: 3px;
    padding: 0 5px;
}

.mode-chevron {
    font-size: 9px;
    color: var(--text-tertiary);
}

.mode-menu {
    padding: 3px;
}

.mode-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 10px 4px 8px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    white-space: nowrap;
    color: var(--text-secondary);
}

.mode-option:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.mode-option.selected {
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
