/**
 * Structural group operations — runtime tree edits that live outside the property-build
 * pipeline: attaching custom/cluster groups, moving instances, renaming, and (Part 2)
 * merge / split / delete.
 *
 * Free functions over a GroupOpsHost so this module never imports the GroupManager class
 * (keeps the import graph a DAG). GroupManager exposes thin facade methods that delegate
 * here, so external callers keep using `manager.addCustomGroups(...)` etc.
 */
import { useColumnStore } from "@/data/columnStore";
import { getTmpId } from "@/utils/utils";
import { GroupOpsHost, Group, GroupType } from "./types";
import { buildGroup } from "./builders";
import { setOrder } from "./sort";

// ── internal tree helpers ───────────────────────────────────────────────────

// Remove a group and its whole subtree from index / valueIndex / imageToGroups / pileIndex.
function detachSubtree(host: GroupOpsHost, g: Group) {
    const ids = useColumnStore().instanceIds()
    const walk = (n: Group) => {
        delete host.result.index[n.id]
        if (n.key?.length) host.result.valueIndex.delete(n.key)
        for (const s of n.slots) host.result.imageToGroups.get(ids[s])?.delete(n.id)
        host.result.pileIndex.delete(n.id)
        n.children.forEach(walk)
    }
    walk(g)
}

// Register a leaf group's instances in the reverse index (instance → group id).
function indexLeaf(host: GroupOpsHost, g: Group) {
    const ids = useColumnStore().instanceIds()
    for (const s of g.slots) {
        const id = ids[s]
        let set = host.result.imageToGroups.get(id)
        if (!set) { set = new Set<number>(); host.result.imageToGroups.set(id, set) }
        set.add(g.id)
    }
}

// A parent's subGroupType is the children's common type, or undefined when mixed (e.g. a
// merged/cluster group sitting beside property groups). Consumers must key per-child chrome
// off each child's own `type`, not this.
export function refreshSubGroupType(parent: Group) {
    if (!parent.children.length) { parent.subGroupType = undefined; return }
    const t = parent.children[0].type
    parent.subGroupType = parent.children.every(c => c.type === t) ? t : undefined
}

// Attach a group under a parent at a given index (wiring + reverse index for leaves).
function attachChildAt(host: GroupOpsHost, parent: Group, group: Group, idx: number) {
    group.parent = parent
    group.depth = parent.depth + 1
    parent.children.splice(idx, 0, group)
    host.regsiterGroup(group)
    if (group.children.length === 0) indexLeaf(host, group)
}

// Splice `newGroups` into `parent.children` at `atIdx`, removing `removeCount` existing
// children there (detached from all indexes). Reindexes parentIdx + subGroupType.
export function spliceChildren(host: GroupOpsHost, parent: Group, atIdx: number, removeCount: number, newGroups: Group[]) {
    const removed = parent.children.splice(atIdx, removeCount, ...newGroups)
    for (const r of removed) detachSubtree(host, r)
    for (const g of newGroups) {
        g.parent = parent
        g.depth = parent.depth + 1
        host.regsiterGroup(g)
        if (g.children.length === 0) indexLeaf(host, g)
    }
    for (let i = 0; i < parent.children.length; i++) parent.children[i].parentIdx = i
    refreshSubGroupType(parent)
}

// Collect the union of every descendant instance slot of a group (dedup preserves order).
function collectSlots(group: Group, out: number[], seen: Set<number>) {
    if (group.children.length === 0) {
        for (const s of group.slots) if (!seen.has(s)) { seen.add(s); out.push(s) }
    } else {
        for (const c of group.children) collectSlots(c, out, seen)
    }
}

// Attach `groups` as children of the target group (nesting). The runtime record in
// host.customGroups lets group() replay them after a property-tree rebuild.
export function addCustomGroups(host: GroupOpsHost, targetGroupId: number, groups: Group[], emit?: boolean) {
    host.invalidateIterators()
    if (!attachCustomGroups(host, targetGroupId, groups)) return
    host.applySha1Piles()
    setOrder(host.result.root)
    host.buildOrdinalRanges()
    if (emit) host.emitResult()
}

// Attach without finalising (pile overlay / display order). For batch callers that finalise
// once at the end — notably the post-rebuild replay in ClusterManager.reapplyAfter, which
// otherwise paid a full-tree applySha1Piles + setOrder per re-grafted target.
// Returns whether the target existed.
export function attachCustomGroups(host: GroupOpsHost, targetGroupId: number, groups: Group[]): boolean {
    const parent = host.result.index[targetGroupId]
    if (!parent) return false
    host.customGroups[targetGroupId] = groups
    host.setChildGroup(parent, groups)
    return true
}

// Move instances between two existing groups in-place: pull their slots out of `from` and
// add them to `to`, keeping the reverse index consistent. Mutates the live Group objects
// (also referenced by customGroups), so no separate sync is needed. Runtime-only.
export function moveImagesToGroup(host: GroupOpsHost, fromGroupId: number, toGroupId: number, instanceIds: number[], emit = true) {
    if (fromGroupId === toGroupId) return
    const from = host.result.index[fromGroupId]
    const to = host.result.index[toGroupId]
    if (!from || !to || !instanceIds.length) return

    host.invalidateIterators()
    const col = useColumnStore()

    const slotSet = new Set<number>()
    for (const id of instanceIds) {
        const s = col.slotMap.get(id)
        if (s !== undefined) slotSet.add(s)
    }
    if (!slotSet.size) return

    from.slots = from.slots.filter(s => !slotSet.has(s))
    const existing = new Set(to.slots)
    for (const s of slotSet) if (!existing.has(s)) to.slots.push(s)

    // Reverse index (instance → group id). sha1 children are display-only and map to the
    // parent, so we only move the group membership here.
    for (const id of instanceIds) {
        let set = host.result.imageToGroups.get(id)
        if (!set) { set = new Set<number>(); host.result.imageToGroups.set(id, set) }
        set.delete(fromGroupId)
        set.add(toGroupId)
    }

    // Recompute the sha1 pile overlay for the affected leaves (from/to slot sets changed) —
    // and only those: a drag must not sweep the whole tree.
    host.applySha1Piles([from, to])

    setOrder(host.result.root)
    host.buildOrdinalRanges()
    if (emit) host.emitResult()
}

// Rename a group in-place (runtime-only, e.g. a cluster). Bumps version so views refresh.
export function renameGroup(host: GroupOpsHost, groupId: number, name: string, emit = true) {
    const g = host.result.index[groupId]
    if (!g) return
    g.name = name
    if (emit) host.emitResult()
}

export function delCustomGroups(host: GroupOpsHost, targetGroupId: number, emit?: boolean) {
    delete host.customGroups[targetGroupId]
    // The registry can outlive the tree node (a rebuild may not re-create that group), and
    // removeChildren dereferences its argument — so drop the record and bail rather than throw.
    const parent = host.result.index[targetGroupId]
    if (!parent) return
    host.removeChildren(parent)
    host.applySha1Piles()
    host.buildOrdinalRanges()
    if (emit) host.emitResult()
}

export function clearCustomGroups(host: GroupOpsHost, emit?: boolean) {
    for (const groupId of Object.keys(host.customGroups).map(Number)) {
        delCustomGroups(host, groupId)
    }
    if (emit) host.emitResult()
}

// ── General group operations (Part 2) ───────────────────────────────────────
// NOTE: merge / replace-split / delete are live edits only; they do not yet survive a full
// group() rebuild (that's Phase 2b, the op-log). 'children' split reuses customGroups and
// therefore does survive re-sort like a cluster.

// Divide a LEAF group into `groups` (from a cluster function or a property division).
// 'children' nests them under the leaf; 'replace' swaps the leaf for them at its own level.
export function split(host: GroupOpsHost, groupId: number, groups: Group[], mode: 'replace' | 'children', emit = true) {
    const g = host.result.index[groupId]
    if (!g || g.children.length > 0 || !groups.length) return   // leaf-only

    if (mode === 'children' || !g.parent) {
        addCustomGroups(host, groupId, groups, emit)
        return
    }

    host.invalidateIterators()
    spliceChildren(host, g.parent, g.parentIdx, 1, groups)
    host.applySha1Piles()
    setOrder(host.result.root)
    host.buildOrdinalRanges()
    if (emit) host.emitResult()
}

// Merge any groups (possibly under different parents) into one Cluster group placed where
// the first (min display-order) group was; all sources are removed.
export function merge(host: GroupOpsHost, groupIds: number[], emit = true) {
    const groups = groupIds.map(id => host.result.index[id]).filter(Boolean) as Group[]
    if (groups.length < 2) return
    const anchor = groups.reduce((a, b) => (a.order <= b.order ? a : b))
    const anchorParent = anchor.parent
    if (!anchorParent) return   // cannot merge the root
    const anchorOrder = anchor.order

    host.invalidateIterators()

    const slots: number[] = []
    const seen = new Set<number>()
    for (const g of groups) collectSlots(g, slots, seen)

    const merged = buildGroup(getTmpId(), slots, GroupType.Cluster)
    merged.name = 'Merged'

    // Remove every source from its parent first (indices shift as we go).
    for (const g of groups) {
        const p = g.parent
        if (!p) continue
        const idx = p.children.indexOf(g)
        if (idx >= 0) p.children.splice(idx, 1)
        detachSubtree(host, g)
    }
    // Reindex + subGroupType for every parent that lost a child.
    const parents = new Set(groups.map(g => g.parent).filter(Boolean) as Group[])
    for (const p of parents) {
        for (let i = 0; i < p.children.length; i++) p.children[i].parentIdx = i
        refreshSubGroupType(p)
    }

    const insertIdx = anchorParent.children.filter(c => c.order < anchorOrder).length
    attachChildAt(host, anchorParent, merged, insertIdx)
    for (let i = 0; i < anchorParent.children.length; i++) anchorParent.children[i].parentIdx = i
    refreshSubGroupType(anchorParent)

    host.applySha1Piles()
    setOrder(host.result.root)
    host.buildOrdinalRanges()
    if (emit) host.emitResult()
}

// Delete one group; its images move into a leftover "Unclustered" bucket under the same
// parent (created on demand). Deleting the leftover bucket itself just drops it.
export function deleteGroup(host: GroupOpsHost, groupId: number, emit = true) {
    const g = host.result.index[groupId]
    const parent = g?.parent
    if (!g || !parent) return

    host.invalidateIterators()

    if (!g.isLeftover) {
        let leftover = parent.children.find(c => c.isLeftover)
        if (!leftover) {
            leftover = buildGroup(getTmpId(), [], GroupType.Cluster)
            leftover.name = 'Unclustered'
            leftover.isLeftover = true
            attachChildAt(host, parent, leftover, parent.children.length)
        }
        const moved: number[] = []
        const seen = new Set<number>()
        collectSlots(g, moved, seen)
        const existing = new Set(leftover.slots)
        for (const s of moved) if (!existing.has(s)) leftover.slots.push(s)
        indexLeaf(host, leftover)
    }

    const idx = parent.children.indexOf(g)
    if (idx >= 0) parent.children.splice(idx, 1)
    detachSubtree(host, g)
    for (let i = 0; i < parent.children.length; i++) parent.children[i].parentIdx = i
    refreshSubGroupType(parent)

    host.applySha1Piles()
    setOrder(host.result.root)
    host.buildOrdinalRanges()
    if (emit) host.emitResult()
}
