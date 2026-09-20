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

// Every image a group shows, including those of its sub-piles. A group that has been split
// carries no slots of its own — its images live in its leaves — so the union is walked for the
// operations that act on a whole card.
export function groupSlots(group: Group): number[] {
    if (!group.children.length) return group.slots
    const res: number[] = []
    const seen = new Set<number>()
    const walk = (g: Group) => {
        if (!g.children.length) { for (const s of g.slots) if (!seen.has(s)) { seen.add(s); res.push(s) } }
        else g.children.forEach(walk)
    }
    walk(group)
    return res
}

// The pile overlay and the display order after a structural edit.
function finalise(host: GroupOpsHost, emit?: boolean) {
    host.applySha1Piles()
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
    if (!applyClusterGroups(host, targetGroupId, groups)) return
    finalise(host, emit)
}

// The same without finalising, for callers that batch several edits.
export function applyClusterGroups(host: GroupOpsHost, targetGroupId: number, groups: Group[]): boolean {
    const target = host.result.index[targetGroupId]
    if (!target || !groups.length) return false
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
    return true
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
    finalise(host, emit)
}

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

    if (target) {
        overlay.own(target.c, slots, target.idx)
        touched.add(target.c.parentId)
    }
    // Leaving a pile for a value-group is a departure from that bucket's queue. A move inside
    // one container is already done by the own() above.
    if (source && (!target || source.c !== target.c)) {
        overlay.release(source.c, slots)
        touched.add(source.c.parentId)
    }
    if (!touched.size) return

    for (const parentId of touched) {
        const c = overlay.container(parentId)
        if (c) overlay.resync(c)
    }
    finalise(host, emit)
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
    finalise(host, emit)
}

// Delete one pile: everything it owns, shown or masked, becomes part of its level's leftover.
// Deleting the leftover itself is a no-op — it already holds what its level does not name.
export function deleteGroup(host: GroupOpsHost, groupId: number, emit = true) {
    const overlay = host.overlay
    const node = overlay.nodeOf(groupId)
    if (!node) return
    if (overlay.isLeftover(node.c, node.idx)) return
    overlay.kill(node.c, node.idx)
    overlay.resync(node.c)
    finalise(host, emit)
}
