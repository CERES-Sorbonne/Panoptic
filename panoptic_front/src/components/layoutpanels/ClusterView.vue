<script setup lang="ts">
// Cluster view. Header: title + a group-selection dropdown listing the
// GroupType.Cluster groups already present in the tab's collection tree
// (clusters are computed elsewhere — tree/map view — this only displays
// them). Body: a ClusterScroller showing one representative image per
// cluster, fed a standalone GroupManager that is a clone of the selected
// cluster group re-rooted at depth 0.
import { onUnmounted, shallowRef, computed, watch } from 'vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import ClusterBadge from '@/components/cluster/ClusterBadge.vue'
import ClusterScroller from '@/components/scrollers/cluster/ClusterScroller.vue'
import ActionButton2 from '@/components/actions/ActionButton2.vue'
import { Group, GroupManager, GroupType } from '@/core/GroupManager'
import { CollectionManager } from '@/core/CollectionManager'
import { TabManager } from '@/core/TabManager'
import { ClusterOptions, Property } from '@/data/models'
import { useColumnStore } from '@/data/columnStore'
import { useDataStore } from '@/data/dataStore'

const col = useColumnStore()
const data = useDataStore()

const props = defineProps<{
    tab: TabManager
    collection: CollectionManager
    clusterOptions: ClusterOptions
    imageSize: number
    properties: Property[]
    width: number
    height: number
}>()

const HEADER_PX = 42

// ---- Group selection ---------------------------------------------------------

function isEligible(g: Group): boolean {
    return g.type === GroupType.Cluster && g.slots.length > 0
}

// Eligible cluster groups in display order (DFS).
const eligibleGroups = computed(() => {
    props.collection.groupManager.version.value // reactive dep on the group tree
    const root = props.collection.groupManager.result?.root
    if (!root) return [] as Group[]
    const res: Group[] = []
    const stack: Group[] = [root]
    while (stack.length) {
        const g = stack.pop()!
        if (isEligible(g)) res.push(g)
        for (let i = g.children.length - 1; i >= 0; i--) stack.push(g.children[i])
    }
    return res
})

// Selected group, revalidated against the eligible list (falls back to first).
const group = computed<Group | null>(() => {
    const groups = eligibleGroups.value
    if (!groups.length) return null
    return groups.find(g => g.id === props.clusterOptions.selectedGroupId) ?? groups[0]
})

function groupLabel(g: Group) {
    return g.name ?? ('Cluster ' + g.parentIdx)
}

function selectGroup(g: Group) {
    props.clusterOptions.selectedGroupId = g.id
}

// ---- Clustering ---------------------------------------------------------------

function getAllImages() {
    const root = props.collection.groupManager.result?.root
    if (!root) return []
    const slots = root.slots ?? []
    if (!slots.length) return []
    const ids = col.instanceIds()
    const sha1s = col.sha1s()
    return slots.map(slot => ({
        id: ids[slot],
        imageUrl: data.baseImgUrl + 'by_size/' + sha1s[slot],
        sha1: sha1s[slot]
    }))
}

function addClusters(groups: Group[]) {
    const rootId = props.collection.groupManager.result.root?.id
    if (rootId != null) {
        props.collection.groupManager.addCustomGroups(rootId, groups, true)
    }
}

// ---- Standalone tree fed to ClusterScroller --------------------------------------

const NAMESPACE = 'cluster-view'
const clusterTreeManager = shallowRef<GroupManager>()

function rebuildTree() {
    if (!group.value) {
        clusterTreeManager.value = undefined
        return
    }
    // If the selected group is an individual cluster whose parent is a cluster
    // container (subGroupType == Cluster), root at the parent so root.children
    // yields all sibling clusters. Otherwise root at the selected group itself.
    const parent = group.value.parent
    const useParent = parent != null && parent.subGroupType === GroupType.Cluster
    const rootId = useParent ? parent.id : group.value.id

    clusterTreeManager.value = props.collection.groupManager.rootedAt(rootId)
    if (clusterTreeManager.value) clusterTreeManager.value.setSelectionNamespace(NAMESPACE)
}

watch([group, () => props.collection.groupManager.version.value], rebuildTree, { immediate: true })

onUnmounted(() => col.disposeNamespace(NAMESPACE))
</script>

<template>
    <div class="cluster-workspace" :style="{ height: props.height + 'px' }">
        <div class="cluster-header">
            <div class="cluster-title">{{ $t('main.cluster.title') }}</div>
            <!-- <div class="cluster-controls">
                <Dropdown v-if="eligibleGroups.length" placement="bottom-start">
                    <template #button>
                        <div class="group-select-button">
                            <template v-if="group">
                                <ClusterBadge :value="group.slots.length" />
                                <span class="ms-1">{{ groupLabel(group) }}</span>
                            </template>
                            <i class="bi bi-chevron-down ms-2"></i>
                        </div>
                    </template>
                    <template #popup="{ hide }">
                        <div class="group-select-popup">
                            <div
                                v-for="g in eligibleGroups"
                                :key="g.id"
                                class="group-select-item"
                                :class="{ 'is-selected': group && g.id === group.id }"
                                @click="selectGroup(g); hide()"
                            >
                                <ClusterBadge :value="g.slots.length" />
                                <span class="ms-1">{{ groupLabel(g) }}</span>
                            </div>
                        </div>
                    </template>
                </Dropdown>
            </div> -->
        </div>

        <div v-if="!group" class="cluster-empty">
            <span class="text-secondary">{{ $t('main.cluster.empty') }}</span>
            <ActionButton2 action="group" :images="getAllImages" @groups="addClusters" :no-border="true">
                <div class="cluster-create-btn">
                    <i class="bi bi-diagram-2 me-1" />
                    <span>{{ $t('action.group') }}</span>
                </div>
            </ActionButton2>
        </div>

        <ClusterScroller
            v-else-if="clusterTreeManager"
            input-key="cluster-view"
            :group-manager="clusterTreeManager"
            :image-size="props.imageSize"
            :height="props.height - HEADER_PX"
            :width="props.width"
            :properties="props.properties"
            :hide-if-modal="true"
        />
    </div>
</template>

<style scoped>
.cluster-workspace {
    display: flex;
    flex-direction: column;
    min-height: 0;
    padding-top: var(--spacing-xs);
}

.cluster-header {
    flex-shrink: 0;
    padding: var(--spacing-xs) var(--spacing-sm) var(--spacing-sm);
}

.cluster-title {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    font-size: var(--font-size-md, 15px);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    margin-bottom: var(--spacing-xs);
}

.cluster-controls {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
}

.group-select-button {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
    color: var(--text-secondary);
    transition: background-color var(--transition-fast);
}

.group-select-button:hover {
    background-color: var(--hover-bg);
}

.group-select-popup {
    display: flex;
    flex-direction: column;
    max-height: 400px;
    overflow-y: auto;
}

.group-select-item {
    display: inline-flex;
    align-items: center;
    padding: 4px 8px;
    cursor: pointer;
    white-space: nowrap;
    transition: background-color var(--transition-fast);
}

.group-select-item:hover {
    background-color: var(--hover-bg);
}

.group-select-item.is-selected {
    color: var(--primary);
    font-weight: var(--font-weight-medium);
}

.cluster-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    gap: var(--spacing-sm);
}

.cluster-create-btn {
    display: flex;
    align-items: center;
    padding: 4px 10px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
    color: var(--text-secondary);
    transition: background-color var(--transition-fast);
}

.cluster-create-btn:hover {
    background-color: var(--hover-bg);
}
</style>
