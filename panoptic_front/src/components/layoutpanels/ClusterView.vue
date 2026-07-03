<script setup lang="ts">
// Cluster view. Header: title + a group-selection dropdown listing the
// GroupType.Cluster groups already present in the tab's collection tree
// (clusters are computed elsewhere — tree/map view — this only displays
// them). Body: a ClusterScroller showing one representative image per
// cluster, fed a standalone GroupManager that is a clone of the selected
// cluster group re-rooted at depth 0.
import { onUnmounted, shallowRef, computed, watch, ref } from 'vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import ClusterBadge from '@/components/cluster/ClusterBadge.vue'
import ClusterScroller from '@/components/scrollers/cluster/ClusterScroller.vue'
import ActionButton2 from '@/components/actions/ActionButton2.vue'
import SplitLayout from '@/layouts/SplitLayout.vue'
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue'
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

const HEADER_PX = 32

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

// ---- Detail split-view -------------------------------------------------------

const detailGroupId = ref<number | null>(null)
// Split position as a fraction of the total width (not an absolute px size), so
// the primary/detail ratio is preserved when the panel is resized.
const detailRatio = ref(0.35)
const SPLIT_GAP = 10

const detailGroupManager = computed(() => {
    if (detailGroupId.value == null) return null
    const m = props.collection.groupManager.rootedAt(detailGroupId.value)
    if (m) m.setSelectionNamespace('cluster-detail')
    return m
})

const detailGroupName = computed(() => {
    const g = detailGroupManager.value?.result?.root
    if (!g) return ''
    return g.name ?? ('Cluster ' + g.parentIdx)
})

// The primary pane's width is derived purely from the parent-supplied prop: the
// full width, minus the detail pane (and split gap) when it's open. No observer —
// props.width is the single source of truth, passed straight down to the scroller.
const totalWidth = computed(() =>
    props.width > 0 ? props.width : Math.max(200, props.imageSize * 3)
)

// Detail pane pixel width derived from the ratio — mirrors how SplitLayout sizes
// the (percentage-based) secondary pane, so the scroller matches the layout.
const detailWidth = computed(() => Math.round(totalWidth.value * detailRatio.value))

const primaryWidth = computed(() => {
    const w = totalWidth.value
    if (!detailGroupId.value) return w - SPLIT_GAP
    return Math.max(0, w - detailWidth.value - SPLIT_GAP)
})

function toggleDetail(groupId: number) {
    detailGroupId.value = detailGroupId.value === groupId ? null : groupId
}

onUnmounted(() => {
    col.disposeNamespace(NAMESPACE)
    col.disposeNamespace('cluster-detail')
})
</script>

<template>
    <div class="cluster-workspace" :class="{ split: detailGroupId }" :style="{ height: props.height + 'px' }">
        <div v-if="!group" class="cluster-primary-pane">
            <div class="cluster-header">
                <div class="cluster-title">{{ $t('main.cluster.title') }}</div>
            </div>
            <div class="cluster-empty">
                <span class="text-secondary">{{ $t('main.cluster.empty') }}</span>
                <ActionButton2 action="group" :images="getAllImages" @groups="addClusters" :no-border="true">
                    <div class="cluster-create-btn">
                        <i class="bi bi-diagram-2 me-1" />
                        <span>{{ $t('action.group') }}</span>
                    </div>
                </ActionButton2>
            </div>
        </div>

        <SplitLayout
            v-else-if="clusterTreeManager"
            direction="row"
            :secondary-ratio="detailRatio"
            @update:secondary-ratio="detailRatio = $event"
            :gap="SPLIT_GAP"
            resizable
            :min-secondary="150"
            :hide-secondary="!detailGroupId"
        >
            <template #primary>
                <div class="cluster-primary-pane" :class="{ split: detailGroupId }">
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
                    <ClusterScroller
                        input-key="cluster-view"
                        :group-manager="clusterTreeManager"
                        :image-size="props.imageSize"
                        :height="props.height - HEADER_PX"
                        :width="primaryWidth"
                        :properties="props.properties"
                        :hide-if-modal="true"
                        @open-cluster="toggleDetail"
                    />
                </div>
            </template>
            <template #secondary>
                <div v-if="detailGroupManager" class="cluster-detail">
                    <div class="cluster-header">
                        <div class="cluster-title">
                            <button class="detail-close" @click="detailGroupId = null">&times;</button>
                            <span class="detail-name">{{ detailGroupName }}</span>
                        </div>
                    </div>
                    <TreeScroller
                        input-key="cluster-detail"
                        :group-manager="detailGroupManager"
                        :image-size="props.imageSize"
                        :height="props.height - HEADER_PX"
                        :width="detailWidth"
                        :properties="props.properties"
                        :hide-group="true"
                        :hide-if-modal="true"
                    />
                </div>
            </template>
        </SplitLayout>
    </div>
</template>

<style scoped>
.cluster-workspace {
    display: flex;
    flex-direction: column;
    width: 100%;
    min-height: 0;
}

/* While split, the gap between the two white panes reveals this grey backing,
   so the panels read as separated cards. Single view stays seamless. */
.cluster-workspace.split {
    background-color: var(--bg-secondary);
}

.cluster-header {
    flex-shrink: 0;
    height: 32px;
    display: flex;
    align-items: center;
    padding: 0 var(--spacing-sm);
}

.cluster-title {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    font-size: var(--font-size-md, 15px);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
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

/* ── Detail (secondary) pane ──────────────────────────────────────────── */

.cluster-primary-pane {
    display: flex;
    flex-direction: column;
    flex: 1;
    height: 100%;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    background-color: var(--island-surface);
}

/* When split, only the inner (right) corners that face the detail pane round. */
.cluster-primary-pane.split {
    border-top-right-radius: var(--island-radius);
    border-bottom-right-radius: var(--island-radius);
}

.cluster-detail {
    display: flex;
    flex-direction: column;
    flex: 1;
    height: 100%;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    background-color: var(--island-surface);
    /* Detail only exists while split: round the inner (left) corners that face
       the primary pane. */
    border-top-left-radius: var(--island-radius);
    border-bottom-left-radius: var(--island-radius);
}

.detail-close {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border: none;
    background: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 16px;
    line-height: 1;
    margin-right: var(--spacing-xs);
}

.detail-close:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.detail-name {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>
