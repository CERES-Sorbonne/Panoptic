<script setup lang="ts">
// Folders tool-window root node — inserted into the sidebar split's #primary.
import IslandPanel from '@/layouts/IslandPanel.vue'
import FolderList from '@/components/FolderTree/FolderList.vue'
import FileSourceOptionDropdown from '@/components/dropdowns/FileSourceOptionDropdown.vue'
import { computed } from 'vue'
import { useUiStore } from '@/data/uiStore'
import { useDataStore } from '@/data/dataStore'
import { useTabStore } from '@/data/tabStore'
import { usePanopticStore } from '@/data/panopticStore'
import { ModalId, SourceNode } from '@/data/models'
import { getFolderChildren } from '@/utils/utils'

const uiStore = useUiStore()
const data = useDataStore()
const tabStore = useTabStore()
const panoptic = usePanopticStore()

// File-source groups (local filesystem, IIIF, …) with their root folders.
const sourceGroups = computed(() => data.rootNodes.filter(n => n.type === 'file_source') as SourceNode[])
// Root folders that don't belong to any file source.
const looseFolders = computed(() =>
    data.rootNodes.filter(n => n.type === 'folder').map(n => data.folders[n.id]).filter(Boolean)
)

// IIIF sources show the official IIIF logo; other sources use a disk icon.
function isIiif(node: SourceNode) {
    return data.fileSources[node.id]?.dtype === 'iiif'
}

function isSourceExpanded(sourceId: number): boolean {
    return !!uiStore.panelStates.sourceExpansions[sourceId]
}

function toggleSourceExpansion(sourceId: number) {
    const state = uiStore.panelStates.sourceExpansions
    if (state[sourceId]) {
        delete state[sourceId]
    } else {
        state[sourceId] = true
    }
}

function promptFolder() {
    panoptic.showModal(ModalId.FILESOURCE)
}

function getSourceFolderIds(group: SourceNode): number[] {
    const ids: number[] = []
    group.children.forEach(child => {
        ids.push(child.id)
        getFolderChildren(child.id).forEach(c => ids.push(c.id))
    })
    return ids
}

function sourceSelected(group: SourceNode): boolean {
    const filterManager = tabStore.getMainTab()?.collection.filterManager
    if (!filterManager) return false
    const selected = new Set(filterManager.state.folders)
    return getSourceFolderIds(group).some(id => selected.has(id))
}

function handleSourceClick(group: SourceNode, e: MouseEvent) {
    if ((e.target as HTMLElement).closest('.source-option')) return
    toggleSourceSelect(group)
}

function toggleSourceSelect(group: SourceNode) {
    const filterManager = tabStore.getMainTab()?.collection.filterManager
    const tab = tabStore.getMainTab()
    if (!filterManager || !tab) return

    const selected = new Set(filterManager.state.folders)
    const sourceFolderIds = getSourceFolderIds(group)

    if (sourceSelected(group)) {
        sourceFolderIds.forEach(id => selected.delete(id))
    } else {
        sourceFolderIds.forEach(id => selected.add(id))
    }

    filterManager.setFolders(Array.from(selected))
    tab.setSelectedFolder(new Set(selected))
}
</script>

<template>
    <IslandPanel grow>
        <template #header>
            <div class="tw-header">
                <span class="tw-title">Folders</span>
                <div class="tw-actions">
                    <button class="tw-action" title="Add folder" @click="promptFolder()">＋</button>
                    <button class="tw-action" title="Hide" @click="uiStore.panelStates.leftPanelOpen = false">－</button>
                </div>
            </div>
        </template>
        <div class="tw-body">
            <!-- One group per file source, root folders nested inside -->
            <div v-for="group in sourceGroups" :key="'src-' + group.id" class="source-group">
                <div class="source-header" :class="{ selected: sourceSelected(group) }" @click="handleSourceClick(group, $event)" style="cursor: pointer;">
                    <span class="source-chevron" @click.capture.stop="toggleSourceExpansion(group.id)">
                        <i :class="isSourceExpanded(group.id) ? 'bi bi-chevron-down' : 'bi bi-chevron-right'" style="font-size: 10px;" />
                    </span>
                    <img v-if="isIiif(group)" src="/icons/iiif.svg" class="source-logo" alt="IIIF" />
                    <i v-else class="bi bi-hdd source-icon" />
                    <span class="source-name">{{ group.name }}</span>
                    <span class="source-option">
                        <FileSourceOptionDropdown :source="data.fileSources[group.id]" />
                    </span>
                </div>
                <template v-if="isSourceExpanded(group.id)">
                    <FolderList v-if="group.children.length > 0" :folders="group.children"
                        :filter-manager="tabStore.getMainTab()?.collection.filterManager" :tab="tabStore.getMainTab()" />
                    <div v-else class="source-empty">No folders</div>
                </template>
            </div>

            <!-- Folders not attached to any file source -->
            <FolderList v-if="looseFolders.length > 0" :folders="looseFolders"
                :filter-manager="tabStore.getMainTab()?.collection.filterManager" :tab="tabStore.getMainTab()" />
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

/* File-source group: a labelled header with its root folders nested below */
.source-group {
    margin-bottom: var(--spacing-xs);
}

.source-header {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 22px;
    padding: 0 2px;
}

.source-header:hover {
    background-color: var(--hover-bg);
}

.source-header.selected {
    background-color: rgba(38, 117, 191, 0.32);
}

.source-chevron {
    width: 14px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    color: var(--text-tertiary);
    flex-shrink: 0;
}

.source-icon {
    font-size: 12px;
    color: var(--text-tertiary);
    flex-shrink: 0;
}

.source-logo {
    height: 13px;
    width: auto;
    flex-shrink: 0;
    object-fit: contain;
}

.source-name {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.02em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.source-option {
    opacity: 0;
    margin-left: auto;
}

.source-header:hover .source-option {
    opacity: 1;
}

.source-empty {
    padding: 2px 0 4px 20px;
    font-size: var(--font-size-xs);
    color: var(--text-tertiary);
}
</style>
