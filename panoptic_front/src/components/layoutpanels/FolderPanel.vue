<script setup lang="ts">
// Folders tool-window root node — inserted into the sidebar split's #primary.
import IslandPanel from '@/layouts/IslandPanel.vue'
import FolderList from '@/components/FolderTree/FolderList.vue'
import { computed } from 'vue'
import { useUiStore } from '@/data/uiStore'
import { useDataStore } from '@/data/dataStore'
import { useTabStore } from '@/data/tabStore'
import { usePanopticStore } from '@/data/panopticStore'
import { ModalId } from '@/data/models'

const uiStore = useUiStore()
const data = useDataStore()
const tabStore = useTabStore()
const panoptic = usePanopticStore()

const rootFolders = computed(() => data.folderRoots)

function promptFolder() {
    panoptic.showModal(ModalId.FILESOURCE)
}
</script>

<template>
    <IslandPanel grow>
        <template #header>
            <div class="tw-header">
                <span class="tw-title">Folders</span>
                <div class="tw-actions">
                    <button class="tw-action" title="Add folder" @click="promptFolder()">＋</button>
                    <button class="tw-action" title="Options">⋯</button>
                    <button class="tw-action" title="Hide" @click="uiStore.panelStates.leftPanelOpen = false">－</button>
                </div>
            </div>
        </template>
        <div class="tw-body">
            <FolderList v-if="rootFolders.length > 0" :folders="rootFolders" :filter-manager="tabStore.getMainTab()?.collection.filterManager" :tab="tabStore.getMainTab()" />
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
    padding: 0 var(--spacing-md) 0 var(--spacing-sm);
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
    padding: var(--spacing-xs) var(--spacing-sm);
}
</style>
