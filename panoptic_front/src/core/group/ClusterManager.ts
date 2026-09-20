/**
 * ClusterManager
 * Owns the cluster view's overlay: the authored membership (ClusterOverlay) and every
 * structural cluster op (cluster / sub-cluster / move / merge / delete / rename). Extracted
 * out of GroupManager so the engine stays a pure property-tree builder.
 *
 * It also owns the clustering ACTION end to end (`cluster()`): resolving the target group's
 * images, running the action function, and grafting the result. A caller — a button in a
 * virtualized scroller line — only names the group and the function; it never awaits, never
 * holds the result, and may unmount at any point without the clusters being lost. Pending
 * state lives here too (`runs`, keyed by target group) so a remounted button renders the run
 * it did not start.
 *
 * It is the GroupOpsHost passed to group/groupOps.ts: it owns the overlay and delegates the
 * low-level tree-mutation primitives (setChildGroup / regsiterGroup / buildOrdinalRanges / …)
 * back to the tree layer via a ClusterOpsHost (the GroupManager). Typed against the interface,
 * not the class, so there is no import cycle.
 *
 * Piles are grafted as real Group nodes into the property tree, which is what keeps rendering,
 * scrolling, iteration and selection free of any per-frame derivation (cluster_view_goals.md).
 * What they contain is derived from the map: `resyncAll` after a rebuild, `resyncDirty` after an
 * incremental update, and a resync inside each structural op.
 */
import { ClusterOpsHost, GroupOpsHost, Group, GroupTree, GroupType } from "./types";
import * as groupOps from "./groupOps";
import { ClusterOverlay } from "./ClusterOverlay";
import { setOrder } from "./sort";
import { EventEmitter } from "@/utils/utils";
import { useColumnStore } from "@/data/stores/columnStore";
import { useActionStore } from "@/data/stores/actionStore";
import { ActionContext, ParamDescription } from "@/data/models";
import { reactive } from "vue";
import { grpLog } from "@/utils/debugGroup";

// What a caller has to provide to cluster a group: the function to run and its parameters.
// NOT the images — the target group defines the set, and the manager resolves it (below).
export interface ClusterRequest {
    funcId: string
    inputs: ParamDescription[]
    // Action hook the function was picked under ('group', 'execute', …). Only used to remember it
    // as that hook's default; the grafting is the same whatever produced the groups.
    hook?: string
}

// One in-flight (or last failed) clustering run, keyed by the group being clustered.
export interface ClusterRun {
    token: number
    funcId: string
    running: boolean
    error?: string
}

export class ClusterManager implements GroupOpsHost {
    // Authored cluster membership: one container per clustered grouping leaf. The single
    // source of truth for the overlay — every Group.slots below a bucket derives from it.
    overlay: ClusterOverlay

    // The current empty bucket being clustered (the leaf target's undecided pile). Owned here so
    // the view no longer scans the index for it. Set when clustering; cleared on a groupBy change.
    emptyBucketId: number | null = null

    // groupId → its clustering run. Reactive so a button can render its own spinner from state it
    // does NOT own: unmount/remount a scroller line and the pending state is still there.
    runs: Record<number, ClusterRun> = reactive({})

    // Fired after a run's groups have been grafted: { targetGroupId, groups }. For view-local
    // reactions that are meaningless when nobody is watching (highlighting the new cards).
    onCluster = new EventEmitter()

    private nextToken = 1

    constructor(private host: ClusterOpsHost) {
        this.overlay = new ClusterOverlay(host)
    }

    // ── Clustering ────────────────────────────────────────────────────────────
    // THE entry point for "cluster this group". Owns the whole operation — resolve the images,
    // run the action, graft the result — so a caller's only responsibility is naming the target
    // group and the function. In particular the await lives HERE, on an object with the tab's
    // lifetime, not in the component that clicked: the clusters land whether or not the button
    // (a virtualized scroller line) is still mounted when the backend answers.
    async cluster(targetGroupId: number, req: ClusterRequest) {
        const target = this.host.result?.index?.[targetGroupId]
        if (!target) return

        const token = this.nextToken++

        // Clustering divides a leaf of the GROUPING: an existing cluster level below the target
        // is replaced, but a group already divided by a property cannot be clustered. Fail here
        // rather than after a pointless round trip to the backend.
        if ((target.children ?? []).some(c => c.type !== GroupType.Cluster)) {
            this.runs[targetGroupId] = { token, funcId: req.funcId, running: false, error: 'not-a-leaf' }
            return
        }

        this.runs[targetGroupId] = { token, funcId: req.funcId, running: true }

        try {
            // The group IS the set: its visible images, read here, never passed in. A pile that
            // was itself sub-clustered carries no slots of its own, so the union of its leaves
            // is what gets clustered.
            const ids = useColumnStore().instanceIds()
            const instanceIds = this.overlay.visibleSlots(target).map(slot => ids[slot])
            const ctx: ActionContext = { instanceIds }
            const { groups } = await useActionStore().executeAction(req.funcId, req.hook ?? 'group', ctx, req.inputs)

            // Superseded by a later run on the same group → its result is the current one.
            if (this.runs[targetGroupId]?.token !== token) return
            // The tree may have been rebuilt while we waited, so re-read the target rather than
            // trusting the Group captured above; if it is gone, the result is stale — drop it.
            if (!this.host.result?.index?.[targetGroupId]) {
                this.runs[targetGroupId] = { token, funcId: req.funcId, running: false, error: 'group-gone' }
                return
            }
            if (!groups?.length) {
                this.runs[targetGroupId] = { token, funcId: req.funcId, running: false, error: 'no-groups' }
                return
            }

            this.applyClusters(targetGroupId, groups)
            delete this.runs[targetGroupId]
            this.onCluster.emit({ targetGroupId, groups })
        } catch (e) {
            console.error(e)
            if (this.runs[targetGroupId]?.token === token) {
                this.runs[targetGroupId] = { token, funcId: req.funcId, running: false, error: String(e) }
            }
        }
    }

    isClustering(groupId: number) { return this.runs[groupId]?.running === true }

    // Graft a run's groups under their target — the single grafting policy, previously duplicated
    // in each view's `addClusters` handler.
    private applyClusters(targetGroupId: number, groups: Group[]) {
        this.addCustomGroups(targetGroupId, groups, true)
        // A collapsed group stands in for its subtree, so clustering it would otherwise produce no
        // visible change: force it open so the new sub-clusters replace its card right away.
        this.host.openGroup(targetGroupId, true)
    }

    // ── GroupOpsHost: delegate the tree-mutation primitives to the tree layer ──
    get result(): GroupTree { return this.host.result }
    setChildGroup(parent: Group, groups: Group[]) { this.host.setChildGroup(parent, groups) }
    removeChildren(group: Group) { this.host.removeChildren(group) }
    regsiterGroup(group: Group) { this.host.regsiterGroup(group) }
    buildOrdinalRanges() { this.host.buildOrdinalRanges() }
    applySha1Piles(only?: Iterable<Group>) { this.host.applySha1Piles(only) }
    emitResult() { this.host.emitResult() }
    openGroup(groupId: number, emit?: boolean) { this.host.openGroup(groupId, emit) }

    // ── Structural cluster operations ─────────────────────────────────────────
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

    // Divide a leaf group into `groups`, nested under it.
    split(groupId: number, groups: Group[], emit = true) {
        groupOps.split(this, groupId, groups, emit)
    }

    // Merge piles of one bucket into one, at the first pile's position.
    merge(groupIds: number[], emit = true) {
        groupOps.merge(this, groupIds, emit)
    }

    // Delete one pile; everything it owns joins its level's leftover.
    delete(groupId: number, emit = true) {
        groupOps.deleteGroup(this, groupId, emit)
    }

    // Refill every pile after the property tree has been rebuilt from zero. The map is
    // untouched by the rebuild, so a pile comes back with the images it owns that the new
    // tree holds — including the ones a lifted filter just brought back.
    resyncAll() {
        this.overlay.resyncAll()
    }

    // Refill the piles of the buckets an edit touched. A value write can move an instance in
    // several grouping leaves at once (a multi-value tag grouping puts it in several), so the
    // caller passes every group id that changed, not only the one it acted on.
    resyncDirty(groupIds: Set<number>): boolean {
        return this.overlay.resyncDirty(groupIds)
    }

    clear() {
        this.overlay.clear()
        this.emptyBucketId = null
        // In-flight runs target group ids that no longer mean anything; bumping the token makes
        // their results stale (the token check in cluster() drops them).
        for (const key of Object.keys(this.runs)) delete this.runs[key]
        this.nextToken++
    }

    // ── Empty-bucket clustering + queue-drain (cluster_view_goals.md) ────────────

    // Cluster the empty bucket: the piles take the images the run names, and the level's
    // leftover holds the rest, so the remainder is always a visible, routable group.
    clusterEmptyBucket(bucketId: number, groups: Group[], emit = true) {
        const bucket = this.host.result.index[bucketId]
        if (!bucket) return
        this.emptyBucketId = bucketId
        this.addCustomGroups(bucketId, groups, emit)
    }

    // Queue-drain (D5): the given instances just received the target value, so they leave the
    // undecided pile for their value-group. Releasing them from the map is what makes the
    // departure stick — the property tree's own update takes them out of the bucket, and the
    // resync then drops them from the pile they were in. The release records that pile, so
    // undoing the value write brings them back to it rather than to the leftover.
    drain(groupId: number, instanceIds: number[], emit = true) {
        const group = this.host.result.index[groupId]
        if (!group || !instanceIds.length) return
        const target = this.overlay.targetOf(groupId)
        if (!target) return

        const col = useColumnStore()
        const slots: number[] = []
        for (const id of instanceIds) {
            const s = col.slotMap.get(id)
            if (s !== undefined) slots.push(s)
        }
        if (!slots.length) return

        grpLog('5b \u00b7 cluster.drain \u2192 release', {
            fromGroupId: groupId, bucketId: target.c.parentId,
            instances: instanceIds.slice(0, 20), slots: slots.slice(0, 20),
            ownerBefore: slots.slice(0, 20).map(s => {
                const idx = s < target.c.owner.length ? target.c.owner[s] : 0
                const node = target.c.table[idx]
                return { slot: s, nodeIdx: idx, pile: node?.group.name, leftover: node?.leftover }
            }),
        })
        this.overlay.release(target.c, slots)
        this.overlay.resync(target.c)

        this.host.applySha1Piles()
        setOrder(this.host.result.root)
        this.host.buildOrdinalRanges()
        if (emit) this.host.emitResult()
    }
}
