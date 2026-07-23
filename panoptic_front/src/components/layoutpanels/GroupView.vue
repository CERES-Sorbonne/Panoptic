<script setup lang="ts">
// Group view. A workspace over the collection's groups: the ClusterScroller shows one
// representative image per group — the flat collection before clustering, the property groups
// when a tree grouping is active, or cluster cards once clustered — fed the collection's own
// groupManager directly (no clone / no rootedAt). A right-side inspector can open up to two
// groups for drag-between editing.
import { onUnmounted, computed, watch, ref } from 'vue'
import ClusterScroller from '@/components/scrollers/cluster/ClusterScroller.vue'
import SplitLayout from '@/layouts/SplitLayout.vue'
import ClusterDetailPane from '@/components/layoutpanels/ClusterDetailPane.vue'
import { Group, GroupType } from '@/core/GroupManager'
import { CollectionManager } from '@/core/CollectionManager'
import { TabManager } from '@/core/TabManager'
import { ClusterOptions, Instance, Property } from '@/data/models'
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

const HEADER_PX = 34

// ---- Assignment target = the leaf grouping property (cluster_view_goals.md) -----------------
// The paradigm: assigning IS grouping. The target is ALWAYS the deepest (leaf) group-by property;
// there is no separate free-floating axis. The view requires ≥1 grouping property; with none there
// is no target.
const targetPropertyId = computed<number | null>(() => {
    const gb = props.collection.groupState?.groupBy ?? []
    return gb.length ? gb[gb.length - 1] : null
})

// ---- The empty bucket -----------------------------------------------------------------------
// The undecided pile: the leaf-level property group whose target value is null/undefined. Clustering
// and bulk assignment happen ONLY here (D1). For single-level grouping there is exactly one; for
// nested grouping there is one per parent and we target the first (nested clustering: follow-up).
function isEmptyBucketGroup(g: Group): boolean {
    if (g.type !== GroupType.Property) return false
    const pv = g.meta?.propertyValues?.[0]
    return !!pv && (pv.value === null || pv.value === undefined || pv.value === '')
}

// ---- Clustering ------------------------------------------------------------------------------

// The clusters created by the most recent clustering/split action, highlighted in the scroller
// so a fresh pass stands out. Collect the leaf group ids the action produced.
const highlightIds = ref<number[]>([])
function markHighlight(groups: Group[]) {
    const ids: number[] = []
    const walk = (g: Group) => {
        if (g.children?.length) g.children.forEach(walk)
        else if (g.id != null) ids.push(g.id)
    }
    groups.forEach(walk)
    highlightIds.value = ids
}

// Sub-divide one group (from the per-card button): always nest the new clusters UNDER it
// ('children'), so the sub-clusters inherit the parent's value (a value-group's value, or the
// undecided empty bucket). The version bump reflects it in the cluster view.
function onAddClusters(groupId: number, groups: Group[]) {
    props.collection.split(groupId, groups, 'children', true)
    markHighlight(groups)
}

// Delete one cluster card: its images move to the leftover "Unclustered" bucket.
function onDeleteCluster(groupId: number) {
    props.collection.delete(groupId, true)
}

// ---- Assignment: write the target property's value onto a cluster's instances -----
// Direct write + queue-drain reflow (cluster_view_goals.md D5): the target IS the leaf grouping, so
// writing its value moves the assigned images out of the empty bucket into their value-group. The
// value write reflows the property tree (updateSelection adds them to their value-group); we then
// call ClusterManager.drain to pull the same images out of the cluster/empty bucket — O(delta), no
// regroup, so only the acted-on pile moves and unworked piles stay put.

// Instance descriptors (id + sha1) for a cluster's slots, read from the OWNING collection tree.
function clusterInstances(groupId: number) {
    const g = props.collection.result?.index?.[groupId]
    if (!g) return [] as Instance[]
    const ids = col.instanceIds()
    const sha1s = col.sha1s()
    return (g.slots ?? []).map(slot => ({ id: ids[slot], sha1: sha1s[slot] } as any as Instance))
}

// From the per-card typed property input (ClusterPropertyInput): the value is already typed
// (tag id array, number, date, …). A defined value assigns it and drains the pile into its
// value-group; an undefined value clears the property (undecide) and the pile stays in place.
async function assignClusterValue(groupId: number, value: any) {
    if (targetPropertyId.value == null) return
    const imgs = clusterInstances(groupId)
    if (!imgs.length) return
    await data.setPropertyValue(targetPropertyId.value, imgs, value)
    if (value !== undefined && value !== null) props.collection.drainCluster(groupId, imgs.map(i => i.id))
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
// The view requires ≥1 grouping property: the leaf grouping IS the assignment target. With no
// grouping there is no target, so we prompt to pick one instead of showing the flat collection.
const hasGrouping = computed(() => (props.collection.groupState?.groupBy?.length ?? 0) > 0)

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

// The destination region's value on the target property, by construction (D4): a value-group holds
// exactly its own value (from the grouping), so dropping there writes that value; a cluster or the
// empty bucket carries no value, so dropping there clears it (undecide). No homogeneity scan.
function groupTargetValue(gid: number): { has: boolean, value?: any } {
    const g = props.collection.result?.index?.[gid]
    if (!g || !isValueGroup(g)) return { has: false }
    const pv = g.meta?.propertyValues?.[0]
    // A tag value-group's key value is a single tag id; the stored form is an id array.
    if (pv && isTag(data.properties?.[pv.propertyId]?.type)) {
        return { has: true, value: pv.value != null ? [pv.value] : undefined }
    }
    return { has: true, value: pv?.value }
}

// A value-group: a real, homogeneous group of the target property with a defined value (as opposed
// to the empty bucket or a cluster, which carry no value).
function isValueGroup(g: Group): boolean {
    return g.type === GroupType.Property && !isEmptyBucketGroup(g)
}

// On drop into pane `idx`, move the instance between the underlying cluster groups (not just
// the local copies) so the whole group tree reflects the swap. Order-independent: the source
// cluster is whichever OTHER open cluster still owns the dragged slot at drop time (group.slots
// is only mutated by moveImagesToGroup, so it still reflects pre-move membership here). This
// avoids relying on whether vuedraggable fires `add` or `remove` first, and naturally makes an
// intra-pane reorder a no-op (no other open cluster owns the slot).
async function onPaneAdd(idx: number, payload: { instance: Instance, index: number }) {
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

        // Apply the target group's value to the moved image so membership and the property agree.
        // A group with no shared value clears the moved image's value.
        if (targetPropertyId.value != null) {
            const pid = targetPropertyId.value
            const sha1s = col.sha1s()
            const img = { id: payload.instance.id, sha1: sha1s[slot] } as any as Instance
            const target = groupTargetValue(targetGid)
            await data.setPropertyValue(pid, img, target.has ? target.value : undefined)
        }
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
                    <div v-if="!hasGrouping" class="cluster-empty">
                        <span class="text-secondary">Group by a property — clustering assigns its values.</span>
                    </div>
                    <ClusterScroller
                        v-else
                        input-key="cluster-view"
                        :group-manager="viewManager"
                        :image-size="props.imageSize"
                        :height="props.height"
                        :width="primaryWidth"
                        :layout-width="totalWidth"
                        :properties="props.properties"
                        :target-property-id="targetPropertyId ?? undefined"
                        :highlight-ids="highlightIds"
                        :opened-ids="detailGroupIds"
                        :hide-if-modal="true"
                        @open-cluster="openDetail"
                        @add-clusters="onAddClusters"
                        @delete-cluster="onDeleteCluster"
                        @assign-cluster-value="assignClusterValue"
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
    /* margin-top: 4px; */
}

/* When split, only the inner (right) corners that face the detail pane round. */
.cluster-primary-pane.split {
    border-top-right-radius: var(--island-radius);
    border-bottom-right-radius: var(--island-radius);
}
</style>
