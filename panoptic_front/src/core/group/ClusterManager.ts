/**
 * ClusterManager
 * Owns the custom/cluster overlay on top of a property tree: the `customGroups` registry
 * and every structural cluster op (add / move / split / merge / delete / rename). Extracted
 * out of GroupManager so the engine stays a pure property-tree builder.
 *
 * It is the GroupOpsHost passed to group/groupOps.ts: it owns `customGroups` and delegates the
 * low-level tree-mutation primitives (setChildGroup / regsiterGroup / buildOrdinalRanges / …)
 * back to the tree layer via a ClusterOpsHost (the GroupManager). Typed against the interface,
 * not the class, so there is no import cycle.
 *
 * NOTE: this is a behaviour-preserving relocation. Clusters are still grafted into the tree and
 * replayed after each rebuild (reapplyAfter); the non-destructive Set overlay + derive, and
 * stripping the cluster branches from updateSelection, are the next step (cluster_view_goals.md).
 */
import { ClusterOpsHost, GroupOpsHost, Group, GroupTree } from "./types";
import * as groupOps from "./groupOps";
import {
    ClusterOverlay, ClusterMember, DerivedLine, BadgeState,
    derive as deriveOverlay, badgeState,
} from "./clusterOverlay";

export class ClusterManager implements GroupOpsHost {
    // parentGroupId → grafted groups. The single source of truth for the overlay.
    customGroups: { [parentGroupId: number]: Group[] } = {}

    constructor(private host: ClusterOpsHost) {}

    // ── GroupOpsHost: delegate the tree-mutation primitives to the tree layer ──
    get result(): GroupTree { return this.host.result }
    setChildGroup(parent: Group, groups: Group[]) { this.host.setChildGroup(parent, groups) }
    removeChildren(group: Group) { this.host.removeChildren(group) }
    regsiterGroup(group: Group) { this.host.regsiterGroup(group) }
    buildOrdinalRanges() { this.host.buildOrdinalRanges() }
    applySha1Piles() { this.host.applySha1Piles() }
    invalidateIterators() { this.host.invalidateIterators() }
    emitResult() { this.host.emitResult() }

    // ── Structural cluster / custom-group operations ──────────────────────────
    addCustomGroups(targetGroupId: number, groups: Group[], emit?: boolean) {
        groupOps.addCustomGroups(this, targetGroupId, groups, emit)
    }

    moveImagesToGroup(fromGroupId: number, toGroupId: number, instanceIds: number[], emit = true) {
        groupOps.moveImagesToGroup(this, fromGroupId, toGroupId, instanceIds, emit)
    }

    renameGroup(groupId: number, name: string, emit = true) {
        groupOps.renameGroup(this, groupId, name, emit)
    }

    delCustomGroups(targetGroupId: number, emit?: boolean) {
        groupOps.delCustomGroups(this, targetGroupId, emit)
    }

    clearCustomGroups(emit?: boolean) {
        groupOps.clearCustomGroups(this, emit)
    }

    // Divide a leaf group into `groups` — 'replace' (new siblings) or 'children' (nested).
    split(groupId: number, groups: Group[], mode: 'replace' | 'children' = 'replace', emit = true) {
        groupOps.split(this, groupId, groups, mode, emit)
    }

    // Merge any groups into one Cluster group at the first group's position.
    merge(groupIds: number[], emit = true) {
        groupOps.merge(this, groupIds, emit)
    }

    // Delete one group; its images move to a leftover "Unclustered" bucket.
    delete(groupId: number, emit = true) {
        groupOps.deleteGroup(this, groupId, emit)
    }

    // Re-graft the previous custom groups after a property-tree rebuild — the fixed-point
    // replay group() used to run inline. `group()` resets the registry, builds the property
    // tree, then hands the saved snapshot back here.
    reapplyAfter(lastCustom: { [parentGroupId: number]: Group[] }) {
        let insert = true
        const toInsert = new Set(Object.keys(lastCustom).map(Number))
        while (insert) {
            insert = false
            for (const target of Array.from(toInsert)) {
                if (this.host.result.index[target]) {
                    this.addCustomGroups(target, lastCustom[target])
                    toInsert.delete(target)
                    insert = true
                }
            }
        }
    }

    clear() {
        this.customGroups = {}
    }

    // ── Overlay bridge (cluster_view_goals.md) ──────────────────────────────────
    // The reworked cluster view renders from a derived overlay rather than the grafted tree.
    // Until the full switch, build the overlay on demand from the current cluster children of a
    // parent, so the view can adopt `derive`/badges incrementally without changing storage.

    // A ClusterMember per leaf cluster under `parentId` (a divided cluster expands into its leaves).
    overlayForParent(parentId: number): ClusterOverlay {
        const parent = this.host.result.index[parentId]
        const clusters: ClusterMember[] = []
        const slotToCluster = new Map<number, number>()
        const collect = (g: Group) => {
            for (const child of g.children) {
                if (child.children.length > 0) { collect(child); continue }
                const slots = new Set<number>(child.slots)
                clusters.push({ id: Number(child.id), name: child.name, slots, isLeftover: child.isLeftover })
                for (const s of child.slots) slotToCluster.set(s, Number(child.id))
            }
        }
        if (parent) collect(parent)
        return { parentId, clusters, slotToCluster }
    }

    // Derived lines (per-cluster + leftover) over the parent's already-filtered/sorted slots.
    deriveLines(parentId: number, parentSlots: ArrayLike<number>): DerivedLine[] {
        return deriveOverlay(parentSlots, this.overlayForParent(parentId))
    }

    // Homogeneity of a set of slots on the target property. `read(slot)` returns the raw value;
    // pass `canon` for tag-type (set-valued) targets. Pure delegate — no store access here.
    badgeFor(slots: Iterable<number>, read: (slot: number) => unknown, canon?: (v: unknown) => unknown): BadgeState {
        return badgeState(slots, read, canon)
    }
}
