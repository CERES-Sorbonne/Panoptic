<script setup lang="ts">
// Tab bar island — the open tabs, a tab-picker dropdown and the add-tab button.
import IslandPanel from '@/layouts/IslandPanel.vue'
import TabButton from '@/components/mainview/TabButton.vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import { useTabStore } from '@/data/tabStore'

const tabStore = useTabStore()

async function addTab() {
    await tabStore.addTab('New Tab')
}

function selectTab(tabId: string) {
    tabStore.selectMainTab(tabId)
}
</script>

<template>
    <IslandPanel v-if="tabStore.loaded">
        <div class="tab-bar">
            <div class="tab-scroll">
                <template v-for="tabId in tabStore.loadedTabs" :key="tabId">
                    <TabButton :tab="tabStore.getTab(tabId)" />
                </template>
            </div>

            <Dropdown placement="bottom-end" class="tab-picker">
                <template #button>
                    <div class="tab-tool" title="All tabs">
                        <span class="bi bi-chevron-down"></span>
                    </div>
                </template>
                <template #popup="{ hide }">
                    <div class="tab-picker-popup">
                        <div
                            v-for="tabId in tabStore.loadedTabs"
                            :key="tabId"
                            class="tab-picker-item"
                            :class="{ 'is-selected': tabId === tabStore.mainTab }"
                            @click="selectTab(tabId); hide()"
                        >
                            {{ tabStore.getTab(tabId).state.name }}
                        </div>
                    </div>
                </template>
            </Dropdown>

            <button class="tab-tool" @click="addTab" id="add-tab-button" title="New tab">
                <span class="bi bi-plus"></span>
            </button>
        </div>
    </IslandPanel>
</template>

<style scoped>
.tab-bar {
    display: flex;
    align-items: center;
    height: var(--toolbar-height);
    max-width: 600px;
    padding: 0 6px;
    gap: 2px;
}

/* Tabs live in a horizontally-scrollable strip so the bar never grows past its
   max-width. The picker dropdown / add button stay pinned at the end. */
.tab-scroll {
    display: flex;
    align-items: center;
    gap: 2px;
    flex: 1 1 auto;
    min-width: 0;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
}

.tab-scroll::-webkit-scrollbar {
    display: none;
}

.tab-picker {
    display: inline-flex;
    flex-shrink: 0;
}

.tab-picker-popup {
    display: flex;
    flex-direction: column;
    min-width: 140px;
    max-height: 320px;
    overflow-y: auto;
}

.tab-picker-item {
    padding: 4px 10px;
    font-size: 13px;
    color: var(--text-secondary);
    white-space: nowrap;
    cursor: pointer;
    transition: background-color var(--transition-fast);
}

.tab-picker-item:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.tab-picker-item.is-selected {
    color: var(--primary);
    font-weight: var(--font-weight-medium);
}

/* Tab pills — flat, rounded, PyCharm "island" look. The global .tab-button
   ships a 30px line-height and an active border-bottom; override both here so
   tabs sit centred inside the bar and read as soft pills, not underlined tabs. */
.tab-bar :deep(.tab-button) {
    display: flex;
    align-items: center;
    height: 24px;
    padding: 0 8px;
    border: none;
    border-radius: var(--radius-sm);
    background-color: transparent;
    line-height: 1;
    font-size: 13px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: background-color var(--transition-fast), color var(--transition-fast);
}

.tab-bar :deep(.tab-button:hover) {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.tab-bar :deep(.tab-button.active) {
    background-color: var(--primary-light);
    border-bottom: none;
    color: var(--primary);
}

/* Close (×) button — floats over the top-right corner of the pill on hover
   instead of reserving space beside it, so tabs stay flush. Tabs keep their
   full width (no shrinking) so names never wrap — overflow scrolls instead. */
.tab-bar :deep(.tab-item) {
    position: relative;
    flex-shrink: 0;
}

.tab-bar :deep(.tab-button span) {
    white-space: nowrap;
}

.tab-bar :deep(.tab-close) {
    position: absolute;
    top: 2px;
    right: 2px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 15px;
    height: 20px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    line-height: 1;
    color: var(--text-secondary);
    background-color: var(--hover-bg);
    cursor: pointer;
}

/* The tooltip wrapper is inline (with an inline style, hence !important) — force
   it and the inner wrapper / icon to fill the button and centre the glyph. */
.tab-bar :deep(.tab-close > *),
.tab-bar :deep(.tab-close .d-flex),
.tab-bar :deep(.tab-close i) {
    display: flex !important;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
    line-height: 1;
}

.tab-bar :deep(.tab-close:hover) {
    /* background-color: var(--border-color); */
    color: var(--accent-red);
}

.tab-bar :deep(.tab-close.hidden) {
    display: none;
}

/* Inline rename field — shrink TextInput so it fits the 24px pill without
   stretching the bar, and let it blend with the island surface. */
.tab-bar :deep(.tab-button .input-field) {
    height: 22px;
    background-color: var(--bg-primary);
    border-color: var(--border-color);
    border-radius: var(--radius-sm);
}

.tab-bar :deep(.tab-button .text-input2) {
    height: 20px;
    padding: 0 4px;
    font-size: 13px;
    color: var(--text-primary);
}

/* Compact, borderless PyCharm-style icon button used for the add-tab button.
   Neutralises the global <button> border/background. */
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

</style>
