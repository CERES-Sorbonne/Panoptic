<script setup lang="ts">
// One row of the folder tree. The tree itself is flattened and virtualized by FolderPanel,
// so this renders a single folder at the given depth and never recurses.
import { FilterManager } from '@/core/FilterManager'
import { Folder } from '@/data/models'
import { getFolderChildren, getFolderAndParents } from '@/utils/folders'
import { useDataStore } from '@/data/stores/dataStore'
import { TabManager } from '@/core/TabManager'
import { useUiStore } from '@/data/stores/uiStore'
import FolderOptionDropdown from '../dropdowns/FolderOptionDropdown.vue'

const data = useDataStore()
const uiStore = useUiStore()
const props = defineProps<{
    folder: Folder
    depth: number
    selected: boolean
    filterManager?: FilterManager
    tab?: TabManager
}>()

function toggleVisible(folderId: number) {
    const visibleFolders = uiStore.panelStates.folderExpansions
    if (visibleFolders[folderId]) {
        delete visibleFolders[folderId]
    } else {
        visibleFolders[folderId] = true
    }
}

function toggleSelect(folderId: number) {
    if (!props.filterManager || !props.tab) return

    const selected = new Set(props.filterManager.state.folders)
    const folder = data.folders[folderId]
    if (!folder) return

    if (selected.has(folderId)) {
        selected.delete(folderId)
        getFolderChildren(folderId).forEach(c => selected.delete(c.id))
    } else {
        getFolderAndParents(folder).forEach(c => selected.delete(c.id))
        selected.add(folderId)
        getFolderChildren(folderId).forEach(c => selected.add(c.id))
    }

    props.filterManager.setFolders(Array.from(selected))
    props.tab.setSelectedFolder(new Set(selected))
}

function isExpanded(folderId: number): boolean {
    return !!uiStore.panelStates.folderExpansions[folderId]
}

function hasChildren(folderId: number): boolean {
    return (data.folders[folderId]?.children?.length ?? 0) > 0
}

function getCount(folderId: number): number {
    return data.folders[folderId]?.count ?? 0
}

function handleToggle(e: MouseEvent) {
    if ((e.target as HTMLElement).closest('.folder-option')) return
    toggleSelect(props.folder.id)
}

function handleExpand(e: MouseEvent) {
    e.stopPropagation()
    toggleVisible(props.folder.id)
}
</script>

<template>
    <div
        class="tree-node"
        :class="{ selected }"
        :style="{ paddingLeft: 8 + depth * 14 + 'px' }"
        @click="handleToggle($event)"
    >
        <span class="tree-caret" @click.capture="handleExpand($event)">
            <i v-if="hasChildren(folder.id)" :class="isExpanded(folder.id) ? 'bi bi-chevron-down' : 'bi bi-chevron-right'" style="font-size: 10px;"></i>
            <span v-else class="tree-caret-spacer">&nbsp;</span>
        </span>
        <span class="tree-label">{{ folder.name }}</span>
        <span v-if="getCount(folder.id) > 0" class="tree-count">{{ getCount(folder.id) }}</span>
        <span class="folder-option">
            <FolderOptionDropdown :folder="folder" />
        </span>
    </div>
</template>

<style scoped>
.tree-node {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 24px;
    padding: 0 var(--spacing-sm);
    cursor: pointer;
    white-space: nowrap;
    position: relative;
}

.tree-node:hover {
    background-color: var(--hover-bg);
}

.tree-node.selected {
    background-color: rgba(38, 117, 191, 0.32);
}

.tree-caret {
    width: 14px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    color: var(--text-tertiary);
    flex-shrink: 0;
}

.tree-caret-spacer {
    width: 8px;
    display: inline-block;
}

.tree-icon {
    color: var(--primary);
    font-size: 10px;
    flex-shrink: 0;
}

.tree-label {
    color: var(--text-primary);
    font-size: var(--font-size-xs);
    overflow: hidden;
    text-overflow: ellipsis;
}

.tree-count {
    color: var(--text-secondary);
    font-size: var(--font-size-xs);
    margin-left: auto;
}

.tree-label {
    min-width: 0;
}

/* Overlays the end of the row (over the name / count) on hover */
.folder-option {
    display: none;
    position: absolute;
    right: 2px;
    top: 50%;
    transform: translateY(-50%);
    background-color: var(--bg-primary);
    border-radius: var(--radius-sm);
    z-index: 1;
}

.tree-node:hover .folder-option {
    display: inline-flex;
}
</style>
