<script setup lang="ts">
// Tab bar island — the open tabs and add-tab button.
import IslandPanel from '@/layouts/IslandPanel.vue'
import TabButton from '@/components/mainview/TabButton.vue'
import { useTabStore } from '@/data/tabStore'

const tabStore = useTabStore()

async function addTab() {
    await tabStore.addTab('New Tab')
}
</script>

<template>
    <IslandPanel v-if="tabStore.loaded">
        <div class="tab-bar">
            <template v-for="tabId in tabStore.loadedTabs" :key="tabId">
                <TabButton :tab="tabStore.getTab(tabId)" />
            </template>
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
    height: 28px;
    padding: 0 4px;
    gap: 2px;
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
