<script setup lang="ts">
// Cluster view. A workspace over the collection's groups: the ClusterScroller shows one
// representative image per group — the flat collection before clustering, the property groups
// when a tree grouping is active, or cluster cards once clustered — fed the collection's own
// groupManager directly (no clone / no rootedAt). A toolbar picks a target property to badge and
// assign; a right-side inspector can open up to two groups for drag-between editing.
import { onUnmounted, computed, watch, ref } from 'vue'
import ClusterScroller from '@/components/scrollers/cluster/ClusterScroller.vue'
import ActionButton2 from '@/components/actions/ActionButton2.vue'
import SplitLayout from '@/layouts/SplitLayout.vue'
import ClusterDetailPane from '@/components/layoutpanels/ClusterDetailPane.vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import PropertySelection from '@/components/inputs/PropertySelection.vue'
import PropertyIcon from '@/components/properties/PropertyIcon.vue'
import { Group, GroupManager, GroupType } from '@/core/GroupManager'
import { CollectionManager } from '@/core/CollectionManager'
import { TabManager } from '@/core/TabManager'
import { ClusterOptions, Instance, Property, PropertyType } from '@/data/models'
import { isTag } from '@/utils/utils'
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

// ---- Assignment target property ---------------------------------------------
// The property whose value each cluster's badge reflects (and that assignment writes).
// Defaults to the LAST grouping property (so badges line up with the active grouping); the
// picker overrides. `undefined` override = follow grouping. Not persisted yet (cluster_view_goals.md).
const targetOverride = ref<number | null | undefined>(undefined)
const lastGroupProperty = computed<number | null>(() => {
    const gb = props.collection.groupState?.groupBy ?? []
    return gb.length ? gb[gb.length - 1] : null
})
const targetPropertyId = computed<number | null>({
    get: () => targetOverride.value === undefined ? lastGroupProperty.value : targetOverride.value,
    set: (v) => { targetOverride.value = v },
})

// ---- Group selection ---------------------------------------------------------

function isEligible(g: Group): boolean {
    return g.type === GroupType.Cluster && g.slots.length > 0
}

// Eligible cluster groups in display order (DFS).
const eligibleGroups = computed(() => {
    props.collection.version.value // reactive dep on the group tree
    const root = props.collection.result?.root
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
    const root = props.collection.result?.root
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
    const rootId = props.collection.result.root?.id
    if (rootId != null) {
        props.collection.addCustomGroups(rootId, groups, true)
    }
}

// How a divide places its new groups: 'replace' swaps the divided leaf for the new groups
// at its own level; 'children' nests them under it.
const splitMode = ref<'replace' | 'children'>('replace')

// Sub-divide one cluster (from the cluster view's per-card button): split on the OWNING
// collection GroupManager so the result also shows in the normal tree. The version bump
// re-clones clusterTreeManager, so the cluster view reflects it too.
function onAddClusters(groupId: number, groups: Group[]) {
    props.collection.split(groupId, groups, splitMode.value, true)
}

// Delete one cluster card: its images move to the leftover "Unclustered" bucket.
function onDeleteCluster(groupId: number) {
    props.collection.delete(groupId, true)
}

// Cluster cards fully selected in the shared selection — mergeable directly on the collection.
const selectedClusterIds = computed(() => {
    const gm = props.collection.groupManager
    const ns = gm.selectionNamespace
    col.selectionTick(ns) // reactive dep on the selection
    const ids: number[] = []
    for (const g of Object.values(gm.result.index) as Group[]) {
        if (g.type !== GroupType.Cluster || !g.slots.length) continue
        if (g.slots.every(s => col.isSelected(s, ns))) ids.push(g.id)
    }
    return ids
})

function mergeSelected() {
    const ids = selectedClusterIds.value
    if (ids.length >= 2) props.collection.merge(ids, true)
}

// Rename on the owning collection GroupManager so the new name also shows in the normal tree;
// the version bump re-clones clusterTreeManager, so the cluster view reflects it too.
function onRenameCluster(groupId: number, name: string) {
    props.collection.renameGroup(groupId, name, true)
}

// ---- Assignment: write the target property's value onto a cluster's instances -----
// Direct write (cluster_view_goals.md D5): assigning a non-parent property doesn't reflow the
// view; the value change flows back through the collection and the badge updates in place.

// Resolve a raw text value to the stored value for the target property's type.
// For tag properties, find an existing tag by name (case-insensitive) or create one.
async function resolveValue(pid: number, raw: string): Promise<any> {
    const prop = data.properties[pid]
    if (!prop) return raw
    if (isTag(prop.type)) {
        const existing = Object.values((prop.tags ?? {}) as Record<number, any>)
            .find((t: any) => String(t.value).toLowerCase() === raw.toLowerCase())
        const tag = existing ?? await data.addTag(pid, raw)
        return [tag.id]   // tag values are stored as id arrays
    }
    if (prop.type === PropertyType.number) { const n = Number(raw); return Number.isNaN(n) ? undefined : n }
    if (prop.type === PropertyType.checkbox) return raw === 'true' || raw === '1'
    return raw
}

// Instance descriptors (id + sha1) for a cluster's slots, read from the OWNING collection tree.
function clusterInstances(groupId: number) {
    const g = props.collection.result?.index?.[groupId]
    if (!g) return [] as Instance[]
    const ids = col.instanceIds()
    const sha1s = col.sha1s()
    return (g.slots ?? []).map(slot => ({ id: ids[slot], sha1: sha1s[slot] } as any as Instance))
}

async function assignCluster(groupId: number, raw: string) {
    if (props.clusterOptions == null || targetPropertyId.value == null) return
    const pid = targetPropertyId.value
    const value = await resolveValue(pid, raw)
    if (value === undefined) return
    const imgs = clusterInstances(groupId)
    if (imgs.length) await data.setPropertyValue(pid, imgs, value)
}

// "Default values" button: give every cluster in the view the target value = its own name.
async function assignDefaults() {
    const gm = props.collection.groupManager
    if (targetPropertyId.value == null) return
    for (const g of Object.values(gm.result.index) as Group[]) {
        if (g.type !== GroupType.Cluster || !g.slots?.length) continue
        const name = g.name ?? ('Cluster ' + g.parentIdx)
        await assignCluster(g.id, name)
    }
}

// ---- Standalone tree fed to ClusterScroller --------------------------------------

// Feed the ClusterScroller the collection's own groupManager directly (no clone / no rootedAt).
// It shows whatever groups exist: the flat root before any clustering, the property groups when a
// tree grouping is active, or cluster cards once clustered. Selection is shared with the tree view.
const viewManager = computed(() => props.collection.groupManager)
const hasImages = computed(() => {
    props.collection.version.value // reactive dep
    return (props.collection.result?.root?.slots?.length ?? 0) > 0
})

// ---- Detail inspector (right side) -------------------------------------------
// Up to two clusters can be inspected at once, stacked vertically. A plain click
// shows a single cluster (replacing whatever is open); a shift-click spawns a
// second one below. Once both slots are full, further shift-clicks replace them
// alternately (top, then bottom, then top…).

const DETAIL_NAMESPACES = ['cluster-detail-0', 'cluster-detail-1']
// Shared vuedraggable group: every visible line in both stacked inspectors joins it, so an
// image can be dragged from one open cluster into the other.
const DRAG_GROUP = 'cluster-inspector'

const detailGroupIds = ref<number[]>([])

// Per-open-pane instance lists (aligned with detailGroupIds), materialised from each
// cluster group's slots. Held as local, mutable state so a drag between the two panes moves
// the image across the arrays. Rebuilt when the opened clusters or the group tree change.
const paneInstances = ref<Instance[][]>([])

function instancesForGroup(gid: number): Instance[] {
    const g = props.collection.result?.index?.[gid]
    if (!g) return []
    const ids = col.instanceIds()
    const sha1s = col.sha1s()
    return (g.slots ?? []).map(slot => ({
        id: ids[slot],
        imageUrl: data.baseImgUrl + 'by_size/' + sha1s[slot],
    }))
}

watch(
    [detailGroupIds, () => props.collection.version.value],
    () => { paneInstances.value = detailGroupIds.value.map(gid => instancesForGroup(gid)) },
    { immediate: true }
)

// On drop into pane `idx`, move the instance between the underlying cluster groups (not just
// the local copies) so the whole group tree reflects the swap. Order-independent: the source
// cluster is whichever OTHER open cluster still owns the dragged slot at drop time (group.slots
// is only mutated by moveImagesToGroup, so it still reflects pre-move membership here). This
// avoids relying on whether vuedraggable fires `add` or `remove` first, and naturally makes an
// intra-pane reorder a no-op (no other open cluster owns the slot).
function onPaneAdd(idx: number, payload: { instance: Instance, index: number }) {
    const arr = paneInstances.value[idx]
    if (arr) arr.splice(Math.max(0, Math.min(payload.index, arr.length)), 0, payload.instance)

    const gm = props.collection.groupManager
    const slot = col.slotMap.get(payload.instance.id)
    const targetGid = detailGroupIds.value[idx]
    if (slot === undefined || targetGid == null) return

    const sourceGid = detailGroupIds.value.find(
        (g, i) => i !== idx && gm.result?.index?.[g]?.slots.includes(slot)
    )
    if (sourceGid != null && sourceGid !== targetGid) {
        // Bumps version → the watch above re-derives paneInstances from the authoritative
        // group.slots, and rebuildTree re-clones the left ClusterScroller.
        gm.moveImagesToGroup(sourceGid, targetGid, [payload.instance.id], true)
    }
}

function onPaneRemove(idx: number, payload: { instance: Instance }) {
    const arr = paneInstances.value[idx]
    if (!arr) return
    const i = arr.findIndex(x => x.id === payload.instance.id)
    if (i >= 0) arr.splice(i, 1)
}
// Which slot the next shift-click replaces once both slots are occupied.
const nextReplace = ref(0)

// Split position of the outer (left/right) split, as a width fraction so the
// ratio survives a resize.
const detailRatio = ref(0.35)
// Split position of the inner (top/bottom) stack, as a height fraction.
const stackRatio = ref(0.5)
const SPLIT_GAP = 10

const isSplit = computed(() => detailGroupIds.value.length > 0)

// One inspector descriptor per open cluster, each with its own instance list and
// selection namespace so the two inspectors select (and drag) independently.
const detailPanes = computed(() =>
    detailGroupIds.value.map((gid, idx) => {
        const g = props.collection.result?.index?.[gid]
        return {
            id: gid,
            instances: paneInstances.value[idx] ?? [],
            name: g ? (g.name ?? ('Cluster ' + g.parentIdx)) : '',
            inputKey: DETAIL_NAMESPACES[idx]
        }
    })
)

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
    if (!isSplit.value) return w - SPLIT_GAP
    return Math.max(0, w - detailWidth.value - SPLIT_GAP)
})

// Heights of the stacked detail scrollers (pane height minus its own header).
// With a single pane it owns the full height; with two, the bottom takes
// `stackRatio` of the height (matching how SplitLayout sizes the secondary).
const bottomPaneHeight = computed(() => Math.round(props.height * stackRatio.value))
const topScrollerHeight = computed(() => {
    if (detailPanes.value.length < 2) return props.height - HEADER_PX
    return Math.max(0, props.height - SPLIT_GAP - bottomPaneHeight.value) - HEADER_PX
})
const bottomScrollerHeight = computed(() => bottomPaneHeight.value - HEADER_PX)

function openDetail(groupId: number, shift: boolean) {
    const ids = detailGroupIds.value
    if (shift) {
        if (ids.length === 0) {
            detailGroupIds.value = [groupId]
        } else if (ids.length === 1) {
            detailGroupIds.value = [ids[0], groupId] // spawn below
            nextReplace.value = 0                    // next shift replaces the top
        } else {
            const next = [...ids]
            next[nextReplace.value] = groupId
            detailGroupIds.value = next
            nextReplace.value = nextReplace.value === 0 ? 1 : 0
        }
        return
    }
    // Plain click: a single inspector. Clicking the only open cluster closes it.
    if (ids.length === 1 && ids[0] === groupId) {
        detailGroupIds.value = []
    } else {
        detailGroupIds.value = [groupId]
    }
    nextReplace.value = 0
}

function closeDetail(idx: number) {
    detailGroupIds.value = detailGroupIds.value.filter((_, i) => i !== idx)
    nextReplace.value = 0
}

onUnmounted(() => {
    DETAIL_NAMESPACES.forEach(ns => col.disposeNamespace(ns))
})
</script>

<template>
    <div class="cluster-workspace" :class="{ split: isSplit }" :style="{ height: props.height + 'px' }">
        <div v-if="!hasImages" class="cluster-primary-pane">
            <div class="cluster-empty">
                <span class="text-secondary">{{ $t('main.cluster.empty') }}</span>
            </div>
        </div>

        <SplitLayout
            v-else
            direction="row"
            :secondary-ratio="detailRatio"
            @update:secondary-ratio="detailRatio = $event"
            :gap="SPLIT_GAP"
            resizable
            :min-secondary="150"
            :hide-secondary="!isSplit"
        >
            <template #primary>
                <div class="cluster-primary-pane" :class="{ split: isSplit }">
                    <div class="cluster-toolbar" :style="{ height: HEADER_PX + 'px' }">
                        <ActionButton2 action="group" :images="getAllImages" @groups="addClusters" :no-border="true">
                            <div class="toolbar-btn"><i class="bi bi-diagram-2 me-1" />Cluster</div>
                        </ActionButton2>
                        <div class="split-mode">
                            <span class="split-mode-label">Divide:</span>
                            <div class="split-mode-btn" :class="{ active: splitMode === 'replace' }"
                                @click="splitMode = 'replace'">replace</div>
                            <div class="split-mode-btn" :class="{ active: splitMode === 'children' }"
                                @click="splitMode = 'children'">children</div>
                        </div>
                        <div class="toolbar-btn" :class="{ disabled: selectedClusterIds.length < 2 }"
                            @click="mergeSelected">
                            <i class="bi bi-union me-1" />Merge
                            <span v-if="selectedClusterIds.length" class="toolbar-count">{{ selectedClusterIds.length }}</span>
                        </div>
                        <div class="target-pick">
                            <span class="split-mode-label">Assign:</span>
                            <select class="target-select" :value="targetPropertyId ?? ''"
                                @change="targetPropertyId = ($event.target as HTMLSelectElement).value === '' ? null : Number(($event.target as HTMLSelectElement).value)">
                                <option value="">—</option>
                                <option v-for="p in props.properties" :key="p.id" :value="p.id">{{ p.name }}</option>
                            </select>
                            <div v-if="targetPropertyId != null" class="toolbar-btn" @click="assignDefaults"
                                title="Give every cluster its name as the value">
                                <i class="bi bi-magic me-1" />Default values
                            </div>
                        </div>
                    </div>
                    <ClusterScroller
                        input-key="cluster-view"
                        :group-manager="viewManager"
                        :image-size="props.imageSize"
                        :height="props.height - HEADER_PX"
                        :width="primaryWidth"
                        :properties="props.properties"
                        :target-property-id="targetPropertyId ?? undefined"
                        :opened-ids="detailGroupIds"
                        :hide-if-modal="true"
                        @open-cluster="openDetail"
                        @add-clusters="onAddClusters"
                        @rename-cluster="onRenameCluster"
                        @delete-cluster="onDeleteCluster"
                        @assign-cluster="assignCluster"
                    />
                </div>
            </template>
            <template #secondary>
                <!-- Right side: one cluster inspector, or two stacked with a
                     draggable horizontal divider. -->
                <ClusterDetailPane
                    v-if="detailPanes.length === 1"
                    :input-key="detailPanes[0].inputKey"
                    :instances="detailPanes[0].instances"
                    :drag-group="DRAG_GROUP"
                    :name="detailPanes[0].name"
                    :image-size="props.imageSize"
                    :width="detailWidth"
                    :height="topScrollerHeight"
                    :properties="props.properties"
                    position="solo"
                    @close="closeDetail(0)"
                    @instance-added="p => onPaneAdd(0, p)"
                    @instance-removed="p => onPaneRemove(0, p)"
                />
                <SplitLayout
                    v-else-if="detailPanes.length === 2"
                    direction="column"
                    :secondary-ratio="stackRatio"
                    @update:secondary-ratio="stackRatio = $event"
                    :gap="SPLIT_GAP"
                    resizable
                    :min-primary="120"
                    :min-secondary="120"
                >
                    <template #primary>
                        <ClusterDetailPane
                            :input-key="detailPanes[0].inputKey"
                            :instances="detailPanes[0].instances"
                            :drag-group="DRAG_GROUP"
                            :name="detailPanes[0].name"
                            :image-size="props.imageSize"
                            :width="detailWidth"
                            :height="topScrollerHeight"
                            :properties="props.properties"
                            position="top"
                            @close="closeDetail(0)"
                            @instance-added="p => onPaneAdd(0, p)"
                            @instance-removed="p => onPaneRemove(0, p)"
                        />
                    </template>
                    <template #secondary>
                        <ClusterDetailPane
                            :input-key="detailPanes[1].inputKey"
                            :instances="detailPanes[1].instances"
                            :drag-group="DRAG_GROUP"
                            :name="detailPanes[1].name"
                            :image-size="props.imageSize"
                            :width="detailWidth"
                            :height="bottomScrollerHeight"
                            :properties="props.properties"
                            position="bottom"
                            @close="closeDetail(1)"
                            @instance-added="p => onPaneAdd(1, p)"
                            @instance-removed="p => onPaneRemove(1, p)"
                        />
                    </template>
                </SplitLayout>
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

/* ── Primary (cluster list) pane ──────────────────────────────────────── */

.cluster-primary-pane {
    display: flex;
    flex-direction: column;
    flex: 1;
    height: 100%;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    background-color: var(--island-surface);
    margin-top: 4px;
}

.cluster-toolbar {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: 0 var(--spacing-sm);
    border-bottom: 1px solid var(--border-color);
    font-size: 12px;
}

.split-mode {
    display: flex;
    align-items: center;
    gap: 4px;
}

.target-pick {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: auto;
}

.target-select {
    font-size: 12px;
    padding: 1px 4px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    background: var(--island-surface, #fff);
    color: var(--text-primary);
    max-width: 140px;
}

.split-mode-label {
    color: var(--text-secondary);
}

.split-mode-btn {
    padding: 1px 8px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
    color: var(--text-secondary);
}

.split-mode-btn.active {
    background-color: var(--primary, #4f46e5);
    color: #fff;
    border-color: var(--primary, #4f46e5);
}

.toolbar-btn {
    display: inline-flex;
    align-items: center;
    padding: 1px 8px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
    color: var(--text-secondary);
}

.toolbar-btn.disabled {
    opacity: 0.45;
    pointer-events: none;
}

.toolbar-count {
    margin-left: 5px;
    background: var(--primary, #4f46e5);
    color: #fff;
    border-radius: 8px;
    padding: 0 5px;
    font-size: 10px;
}

/* When split, only the inner (right) corners that face the detail pane round. */
.cluster-primary-pane.split {
    border-top-right-radius: var(--island-radius);
    border-bottom-right-radius: var(--island-radius);
}
</style>
