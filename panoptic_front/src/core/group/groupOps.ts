/**
 * Structural group operations — runtime tree edits that live outside the property-build
 * pipeline: clustering a group, moving instances between piles, renaming, merging and deleting.
 *
 * Every cluster operation is a write to the authored map (ClusterOverlay) followed by a resync,
 * which refills the piles from it. None of them edits a Group's slots directly: membership is
 * data, and the tree is a picture of it.
 *
 * Free functions over a GroupOpsHost so this module never imports the GroupManager class
 * (keeps the import graph a DAG). GroupManager exposes thin facade methods that delegate
 * here, so external callers keep using `manager.addCustomGroups(...)` etc.
 */
import { useColumnStore } from "@/data/stores/columnStore";
import { getTmpId } from "@/utils/utils";
import { GroupOpsHost, Group, GroupType } from "./types";
import type { ClusterContainer } from "./ClusterOverlay";
import { buildGroup } from "./builders";
import { setOrder } from "./sort";

// ── internal helpers ────────────────────────────────────────────────────────

// A parent's subGroupType is the children's common type, or undefined when mixed (e.g. a
// merged/cluster group sitting beside property groups). Consumers must key per-child chrome
// off each child's own `type`, not this.
export function refreshSubGroupType(parent: Group) {
    if (!parent.children.length) { parent.subGroupType = undefined; return }
    const t = parent.children[0].type
    parent.subGroupType = parent.children.every(c => c.type === t) ? t : undefined
}

// Every image a group shows, including those of its sub-piles. Lives in ./groupSlots so the
// selection surface can use it without importing this module; re-exported here for the callers
// that already reach it through groupOps.
export { groupSlots } from "./groupSlots";

// The pile overlay and the display order after a structural edit.
// `touched` names the groups the edit can have changed the membership or leaf status of — the
// resynced containers' groups, which `ClusterOverlay.containerGroups` reports. Passing it keeps
// the sha1 pass off the whole tree; omitting it rebuilds the overlay from zero, which is what an
// edit that drops every container needs.
function finalise(host: GroupOpsHost, emit?: boolean, touched?: Iterable<Group>) {
    host.applySha1Piles(touched)
    setOrder(host.result.root)
    host.buildOrdinalRanges()
    if (emit) host.emitResult()
}

function slotsOf(instanceIds: number[]): number[] {
    const col = useColumnStore()
    const slots: number[] = []
    for (const id of instanceIds) {
        const s = col.slotMap.get(id)
        if (s !== undefined) slots.push(s)
    }
    return slots
}

// ── Clustering ──────────────────────────────────────────────────────────────

// Divide `targetGroupId` into `groups`: a grouping leaf opens a container, a pile adds a level
// to the one it belongs to. The incoming groups carry the membership the clustering produced;
// it moves into the map and their slots become derived.
export function addCustomGroups(host: GroupOpsHost, targetGroupId: number, groups: Group[], emit?: boolean) {
    const c = applyClusterGroups(host, targetGroupId, groups)
    if (!c) return
    finalise(host, emit, host.overlay.containerGroups(c))
}

// The same without finalising, for callers that batch several edits. Returns the container it
// resynced, so a caller that finalises can scope the work to its groups.
export function applyClusterGroups(host: GroupOpsHost, targetGroupId: number, groups: Group[]): ClusterContainer | undefined {
    const target = host.result.index[targetGroupId]
    if (!target || !groups.length) return undefined
    const overlay = host.overlay

    const node = overlay.nodeOf(targetGroupId)
    const c = node ? node.c : overlay.ensureContainer(targetGroupId)
    const up = node ? node.idx : 0

    // Clustering a level again replaces it: the previous piles stop existing and their images
    // are re-owned by whatever the new run names.
    overlay.killChildren(c, up)

    for (const group of groups) {
        const slots = group.slots
        group.slots = []
        group.type = GroupType.Cluster
        const idx = overlay.addNode(c, group, up)
        overlay.own(c, slots, idx)
    }
    // Whatever the run did not name keeps the owner it had, which routes to this level's
    // leftover — the pile that holds the remainder.
    overlay.addLeftover(c, up)
    overlay.resync(c)
    return c
}

// Divide a LEAF group into `groups`: the new piles are nested UNDER the leaf, so they inherit
// its value.
export function split(host: GroupOpsHost, groupId: number, groups: Group[], emit = true) {
    const g = host.result.index[groupId]
    if (!g || g.children.length > 0 || !groups.length) return   // leaf-only
    addCustomGroups(host, groupId, groups, emit)
}

// Drop the piles below a group: a clustered bucket becomes an ordinary leaf again, a
// sub-clustered pile gets its images back.
export function delCustomGroups(host: GroupOpsHost, targetGroupId: number, emit?: boolean) {
    const overlay = host.overlay
    const node = overlay.nodeOf(targetGroupId)
    const c = node ? node.c : overlay.container(targetGroupId)
    if (!c) return
    overlay.killChildren(c, node ? node.idx : 0)
    overlay.resync(c)
    finalise(host, emit, overlay.containerGroups(c))
}

// Every container goes, so every bucket in the tree becomes a leaf again: a full rebuild of the
// pile overlay is the correct scope here, not a list of leaves.
export function clearCustomGroups(host: GroupOpsHost, emit?: boolean) {
    const overlay = host.overlay
    for (const parentId of Array.from(overlay.byGroup.keys())) overlay.dropContainer(parentId)
    finalise(host, emit)
}

// ── Membership edits ────────────────────────────────────────────────────────

// Move instances between two groups. Dropping into a pile makes that pile their owner;
// dropping into a value-group releases them from the pile they came from, because the value
// write that follows is what takes them out of the queue.
export function moveImagesToGroup(host: GroupOpsHost, fromGroupId: number, toGroupId: number, instanceIds: number[], emit = true) {
    if (fromGroupId === toGroupId) return
    const from = host.result.index[fromGroupId]
    const to = host.result.index[toGroupId]
    if (!from || !to || !instanceIds.length) return

    const overlay = host.overlay
    const slots = slotsOf(instanceIds)
    if (!slots.length) return

    const target = overlay.nodeOf(toGroupId)
    const source = overlay.nodeOf(fromGroupId)
    const touched = new Set<number>()

    // A dead pile is not a destination: its images resolve to whatever inherited them, so the
    // move would silently land somewhere the user did not pick. Refuse the whole move rather
    // than take the images out of where they are.
    if (target && !overlay.isLive(target.c, target.idx)) return

    if (target) {
        overlay.own(target.c, slots, target.idx)
        touched.add(target.c.parentId)
    }
    // Leaving a pile for a value-group is a departure from that bucket's queue. A move inside
    // one container is already done by the own() above. A dead source owns nothing any more,
    // so there is no queue to leave.
    if (source && overlay.isLive(source.c, source.idx) && (!target || source.c !== target.c)) {
        overlay.release(source.c, slots)
        touched.add(source.c.parentId)
    }
    if (!touched.size) return

    // The leaves that changed are the resynced containers' groups, not the two the caller named:
    // the resync refills every pile of a container from the authored map. `from` and `to` are in
    // the set too, for the case where one of them is an ordinary group rather than a pile.
    const leaves = new Set<Group>([from, to])
    for (const parentId of touched) {
        const c = overlay.container(parentId)
        if (!c) continue
        overlay.resync(c)
        for (const g of overlay.containerGroups(c)) leaves.add(g)
    }
    finalise(host, emit, leaves)
}

// Rename a group in-place (runtime-only, e.g. a cluster). Bumps version so views refresh.
export function renameGroup(host: GroupOpsHost, groupId: number, name: string, emit = true) {
    const g = host.result.index[groupId]
    if (!g) return
    g.name = name
    if (emit) host.emitResult()
}

// Merge piles of one bucket into a single one, placed where the first of them was. The masked
// members follow, because the map does not distinguish them from the visible ones.
export function merge(host: GroupOpsHost, groupIds: number[], emit = true) {
    const overlay = host.overlay
    const nodes = groupIds.map(id => overlay.nodeOf(id)).filter(Boolean) as { c: ClusterContainer, idx: number }[]
    if (nodes.length < 2) return
    // Every id has to name a pile that still exists: merging a dead one would give the merged
    // pile images it no longer owns, and drop the ids that named nothing without saying so.
    if (nodes.length !== groupIds.length) return
    if (nodes.some(n => !overlay.isLive(n.c, n.idx))) return
    const c = nodes[0].c
    if (nodes.some(n => n.c !== c)) return          // piles of different buckets do not merge
    const up = overlay.upOf(c, nodes[0].idx)
    if (nodes.some(n => overlay.upOf(c, n.idx) !== up)) return

    const merged = buildGroup(getTmpId(), [], GroupType.Cluster)
    merged.name = 'Merged'
    // The merge takes the place of the first pile it replaces.
    const order = Math.min(...nodes.map(n => overlay.orderOf(c, n.idx)))
    const idx = overlay.addNode(c, merged, up, false, order)
    for (const n of nodes) overlay.own(c, overlay.ownedSlots(c, n.idx), idx)
    for (const n of nodes) overlay.kill(c, n.idx)

    overlay.resync(c)
    finalise(host, emit, overlay.containerGroups(c))
}

// Delete one pile: everything it owns, shown or masked, becomes part of its level's leftover.
// Deleting the leftover itself is a no-op — it already holds what its level does not name.
export function deletePile(host: GroupOpsHost, groupId: number, emit = true) {
    const overlay = host.overlay
    const node = overlay.nodeOf(groupId)
    if (!node) return
    if (overlay.isLeftover(node.c, node.idx)) return
    overlay.kill(node.c, node.idx)
    overlay.resync(node.c)
    finalise(host, emit, overlay.containerGroups(node.c))
}
