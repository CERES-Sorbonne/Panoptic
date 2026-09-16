<script setup lang="ts">
import { FilterManager } from '@/core/FilterManager'
import { Folder } from '@/data/models'
import { getFolderChildren, getFolderAndParents } from '@/utils/utils'
import { computed } from 'vue'
import { useDataStore } from '@/data/dataStore'
import { TabManager } from '@/core/TabManager'
import { useUiStore } from '@/data/uiStore'
import FolderOptionDropdown from '../dropdowns/FolderOptionDropdown.vue'

const data = useDataStore()
const uiStore = useUiStore()
const props = defineProps<{
    folders: Folder[]
    filterManager?: FilterManager
    tab?: TabManager
    depth?: number
}>()

const folderDepth = props.depth ?? 0
const visibleFolders = uiStore.panelStates.folderExpansions

const isSelected = computed(() => {
    if (!props.filterManager) return {} as Record<number, boolean>
    const res = {} as Record<number, boolean>
    const folderSet = new Set(props.filterManager.state.folders)
    props.folders.forEach(f => {
        if (folderSet.has(f.id)) res[f.id] = true
    })
    return res
})

const folderClass = computed(() => {
    const res: Record<number, string> = {}
    props.folders.forEach(f => {
        const classes: string[] = []
        if (isSelected.value[f.id]) classes.push('selected')
        res[f.id] = classes.join(' ')
    })
    return res
})

function toggleVisible(folderId: number) {
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

function getChildren(folderId: number): Folder[] {
    return data.folders[folderId]?.children ?? []
}

function isExpanded(folderId: number): boolean {
    return !!visibleFolders[folderId]
}

function hasChildren(folderId: number): boolean {
    return (data.folders[folderId]?.children?.length ?? 0) > 0
}

function getCount(folderId: number): number {
    return data.folders[folderId]?.count ?? 0
}

function handleToggle(folder: Folder, e: MouseEvent) {
    if ((e.target as HTMLElement).closest('.folder-option')) return
    toggleSelect(folder.id)
}

function handleExpand(folder: Folder, e: MouseEvent) {
    e.stopPropagation()
    toggleVisible(folder.id)
}

</script>

<template>
    <div>
        <div v-for="folder in folders" :key="folder.id">
        <div
            class="tree-node"
            :class="folderClass[folder.id]"
            :style="{ paddingLeft: 8 + folderDepth * 14 + 'px' }"
            @click="handleToggle(folder, $event)"
        >
            <span
                class="tree-caret"
                @click.capture="handleExpand(folder, $event)"
            >
                <i v-if="hasChildren(folder.id)" :class="isExpanded(folder.id) ? 'bi bi-chevron-down' : 'bi bi-chevron-right'" style="font-size: 10px;"></i>
                <span v-else class="tree-caret-spacer">&nbsp;</span>
            </span>
            <span class="tree-label">{{ folder.name }}</span>
            <span v-if="getCount(folder.id) > 0" class="tree-count">{{ getCount(folder.id) }}</span>
            <span class="folder-option">
                <FolderOptionDropdown :folder="folder" />
            </span>
        </div>
        <template v-if="hasChildren(folder.id) && isExpanded(folder.id)">
            <FolderList
                :folders="getChildren(folder.id)"
                :filter-manager="props.filterManager"
                :tab="props.tab"
                :depth="folderDepth + 1"
            />
        </template>
    </div>
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

.folder-option {
    opacity: 0;
    padding-left: 0px;
}

.tree-node:hover .folder-option {
    opacity: 1;
}
</style>
