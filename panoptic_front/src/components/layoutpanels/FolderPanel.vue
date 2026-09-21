<script setup lang="ts">
// Folders tool-window root node — inserted into the sidebar split's #primary.
import IslandPanel from '@/layouts/IslandPanel.vue'
import FolderRow from '@/components/folder_tree/FolderRow.vue'
import { RecycleScroller } from 'vue-virtual-scroller'
import FileSourceOptionDropdown from '@/components/dropdowns/FileSourceOptionDropdown.vue'
import wTT from '@/components/tooltips/withToolTip.vue'
import { computed } from 'vue'
import { useUiStore } from '@/data/stores/uiStore'
import { useDataStore } from '@/data/stores/dataStore'
import { useTabStore } from '@/data/stores/tabStore'
import { usePanopticStore } from '@/data/stores/panopticStore'
import { Folder, ModalId, SourceNode } from '@/data/models'
import { getFolderChildren } from '@/utils/folders'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const uiStore = useUiStore()
const data = useDataStore()
const tabStore = useTabStore()
const panoptic = usePanopticStore()

// File-source groups (local filesystem, IIIF, …) with their root folders.
// The default local filesystem source is permanent, so hide it while it has no
// folders — an empty "local_filesystem" header would just be noise.
const sourceGroups = computed(() => (data.rootNodes.filter(n => n.type === 'file_source') as SourceNode[])
    .filter(n => !(data.fileSources[n.id]?.dtype === 'local' && n.children.length === 0)))
// Root folders that don't belong to any file source.
const looseFolders = computed(() =>
    data.rootNodes.filter(n => n.type === 'folder').map(n => data.folders[n.id]).filter(Boolean)
)

// The default local source carries the backend id "local_filesystem"; show a
// translated label for it and the source's own name for everything else.
function sourceName(node: SourceNode) {
    if (data.fileSources[node.id]?.dtype === 'local') return t('main.nav.folders.local_source')
    return node.name
}

// IIIF sources show the official IIIF logo; other sources use a disk icon.
function isIiif(node: SourceNode) {
    return data.fileSources[node.id]?.dtype === 'iiif'
}

// The whole tree (source headers, expanded folders, trailing "add source" row) is flattened
// into one list of fixed-height rows so RecycleScroller only mounts what is in view: every
// folder row carries a dropdown, and mounting thousands of them made the panel slow to open.
// Keep ROW_HEIGHT in sync with .tree-node / .source-header / .add-source heights.
const ROW_HEIGHT = 24

type Row =
    | { key: string, kind: 'source', node: SourceNode }
    | { key: string, kind: 'folder', folder: Folder, depth: number }
    | { key: string, kind: 'empty' }
    | { key: string, kind: 'add' }

const filterManager = computed(() => tabStore.getMainTab()?.collection.filterManager)
const mainTab = computed(() => tabStore.getMainTab())
const selectedFolders = computed(() => new Set(filterManager.value?.state.folders ?? []))

function pushFolders(rows: Row[], folders: Folder[], depth: number) {
    const expansions = uiStore.panelStates.folderExpansions
    for (const f of folders) {
        rows.push({ key: 'f-' + f.id, kind: 'folder', folder: f, depth })
        const children = data.folders[f.id]?.children
        if (children?.length && expansions[f.id]) pushFolders(rows, children, depth + 1)
    }
}

const rows = computed(() => {
    const res: Row[] = []
    for (const group of sourceGroups.value) {
        res.push({ key: 'src-' + group.id, kind: 'source', node: group })
        if (!isSourceExpanded(group.id)) continue
        if (group.children.length > 0) pushFolders(res, group.children as Folder[], 0)
        else res.push({ key: 'empty-' + group.id, kind: 'empty' })
    }
    pushFolders(res, looseFolders.value, 0)
    res.push({ key: 'add', kind: 'add' })
    return res
})

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
    const selected = selectedFolders.value
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
                <span class="tw-title">{{ $t('main.nav.folders.title') }}</span>
                <div class="tw-actions">
                    <wTT message="modals.filesource.add_source" pos="bottom">
                        <button class="tw-action" @click="promptFolder()">＋</button>
                    </wTT>
                    <wTT message="main.nav.hide_panel" pos="bottom">
                        <button class="tw-action" @click="uiStore.panelStates.leftPanelOpen = false">－</button>
                    </wTT>
                </div>
            </div>
        </template>
        <RecycleScroller class="tw-body" :items="rows" key-field="key" :item-size="ROW_HEIGHT" :buffer="ROW_HEIGHT * 10">
            <template v-slot="{ item }">
                <div v-if="item.kind === 'source'" class="source-header" :class="{ selected: sourceSelected(item.node) }"
                    @click="handleSourceClick(item.node, $event)" style="cursor: pointer;">
                    <span class="source-chevron" @click.capture.stop="toggleSourceExpansion(item.node.id)">
                        <i :class="isSourceExpanded(item.node.id) ? 'bi bi-chevron-down' : 'bi bi-chevron-right'" style="font-size: 10px;" />
                    </span>
                    <img v-if="isIiif(item.node)" src="/icons/iiif.svg" class="source-logo" alt="IIIF" />
                    <i v-else class="bi bi-hdd source-icon" />
                    <span class="source-name">{{ sourceName(item.node) }}</span>
                    <span class="source-option">
                        <FileSourceOptionDropdown :source="data.fileSources[item.node.id]" />
                    </span>
                </div>
                <FolderRow v-else-if="item.kind === 'folder'" :folder="item.folder" :depth="item.depth"
                    :selected="selectedFolders.has(item.folder.id)" :filter-manager="filterManager" :tab="mainTab" />
                <div v-else-if="item.kind === 'empty'" class="source-empty">No folders</div>
                <!-- Same action as the header + button, spelled out -->
                <div v-else class="add-source" @click="promptFolder()">
                    <i class="bi bi-plus" />
                    <span>{{ $t('modals.filesource.add_source') }}</span>
                </div>
            </template>
        </RecycleScroller>
    </IslandPanel>
</template>

<style scoped>
/* Tool window header (shared pattern across panels) */
.tw-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 30px;
    padding: 0 2px 0 var(--spacing-sm);
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

.source-header {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 24px;
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

.add-source {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 24px;
    padding: 0 2px;
    font-size: var(--font-size-xs);
    color: var(--text-tertiary);
    cursor: pointer;
    border-radius: var(--radius-sm);
}

.add-source:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.source-empty {
    height: 24px;
    line-height: 24px;
    padding-left: 20px;
    font-size: var(--font-size-xs);
    color: var(--text-tertiary);
}
</style>
