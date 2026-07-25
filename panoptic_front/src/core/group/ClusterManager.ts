/**
 * ClusterManager
 * Owns the custom/cluster overlay on top of a property tree: the `customGroups` registry
 * and every structural cluster op (add / move / split / merge / delete / rename). Extracted
 * out of GroupManager so the engine stays a pure property-tree builder.
 *
 * It also owns the clustering ACTION end to end (`cluster()`): resolving the target group's
 * images, running the action function, and grafting the result. A caller — a button in a
 * virtualized scroller line — only names the group and the function; it never awaits, never
 * holds the result, and may unmount at any point without the clusters being lost. Pending
 * state lives here too (`runs`, keyed by target group) so a remounted button renders the run
 * it did not start.
 *
 * It is the GroupOpsHost passed to group/groupOps.ts: it owns `customGroups` and delegates the
 * low-level tree-mutation primitives (setChildGroup / regsiterGroup / buildOrdinalRanges / …)
 * back to the tree layer via a ClusterOpsHost (the GroupManager). Typed against the interface,
 * not the class, so there is no import cycle.
 *
 * Clusters are grafted as real Group nodes into the property tree and replayed after each rebuild
 * (reapplyAfter). This is the chosen design (see cluster_view_goals.md): render/scroll/iterators read
 * the tree directly with no per-frame derivation, and only structural cluster edits and target-value
 * changes touch membership — clusterEmptyBucket / drain / reconcile keep those O(delta).
 */
import { ClusterOpsHost, GroupOpsHost, Group, GroupTree, GroupType } from "./types";
import * as groupOps from "./groupOps";
import { buildGroup } from "./builders";
import { setOrder } from "./sort";
import { EventEmitter, getTmpId } from "@/utils/utils";
import { useColumnStore } from "@/data/columnStore";
import { useActionStore } from "@/data/actionStore";
import { ActionContext, ParamDescription } from "@/data/models";
import { reactive } from "vue";

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
    // parentGroupId → grafted groups. The single source of truth for the overlay.
    customGroups: { [parentGroupId: number]: Group[] } = {}

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

    constructor(private host: ClusterOpsHost) {}

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

        // Clustering divides a LEAF: an existing cluster level is replaced (below), but a group
        // already divided by a property cannot be clustered — graft it and groupOps.split would
        // bail. Fail here rather than after a pointless round trip to the backend.
        if ((target.children ?? []).some(c => c.type !== GroupType.Cluster)) {
            this.runs[targetGroupId] = { token, funcId: req.funcId, running: false, error: 'not-a-leaf' }
            return
        }

        this.runs[targetGroupId] = { token, funcId: req.funcId, running: true }

        try {
            // The group IS the set: slots → instance ids, read here, never passed in.
            const ids = useColumnStore().instanceIds()
            const instanceIds = (target.slots ?? []).map(slot => ids[slot])
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
        // Re-clustering replaces: `split` is leaf-only (groupOps.split bails on a group that
        // already has children), so an existing cluster level has to be dropped first — the new
        // run then takes its place instead of the action silently doing nothing.
        const target = this.host.result.index[targetGroupId]
        if ((target?.children ?? []).some(c => c.type === GroupType.Cluster)) {
            this.delCustomGroups(targetGroupId, false)
        }
        this.split(targetGroupId, groups, true)
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

    // Divide a leaf group into `groups`, nested under it.
    split(groupId: number, groups: Group[], emit = true) {
        groupOps.split(this, groupId, groups, emit)
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
    //
    // Each re-grafted group's slots are intersected with the CURRENT slots of its target parent.
    // This is the queue-drain mechanism (cluster_view_goals.md D5): when a cluster is assigned a
    // value, its images leave the empty bucket on the next rebuild, so intersecting the cluster's
    // membership against the empty bucket's now-smaller slot set drops the drained images out of
    // the cluster automatically. Clusters that become empty are not re-grafted.
    reapplyAfter(lastCustom: { [parentGroupId: number]: Group[] }) {
        let insert = true
        const toInsert = new Set(Object.keys(lastCustom).map(Number))
        while (insert) {
            insert = false
            for (const target of Array.from(toInsert)) {
                const parent = this.host.result.index[target]
                if (parent) {
                    toInsert.delete(target)
                    insert = true
                    // Leaf-only: setChildGroup REPLACES the parent's children, so replaying a
                    // cluster onto a group that now has property sub-groups (a grouping level
                    // added since) would silently delete that level. Nested replay is
                    // unaffected — a cluster's own children are grafted after it, when it is
                    // still a leaf.
                    if (parent.children.length > 0) continue
                    const parentSlots = new Set<number>(parent.slots)
                    const reconciled = lastCustom[target]
                        .map(g => {
                            g.slots = g.slots.filter(s => parentSlots.has(s))
                            return g
                        })
                        .filter(g => g.slots.length > 0 || g.isLeftover)
                    // Attach only: group() finalises the pile overlay + display order once,
                    // right after this replay.
                    if (reconciled.length) groupOps.attachCustomGroups(this, target, reconciled)
                }
            }
        }
    }

    clear() {
        this.customGroups = {}
        this.emptyBucketId = null
        // In-flight runs target group ids that no longer mean anything; bumping the token makes
        // their results stale (the token check in cluster() drops them).
        for (const key of Object.keys(this.runs)) delete this.runs[key]
        this.nextToken++
    }

    // ── Empty-bucket clustering + queue-drain (cluster_view_goals.md) ────────────
    // The cluster view's two ClusterManager-owned operations. Both are O(delta): rendering stays
    // free (real grafted Group nodes), only edits touch membership.

    // Cluster the empty bucket: graft `groups` under it AND materialise a real leftover ("New")
    // group for any image no cluster covered — the images that were in the parent but not part of
    // any cluster (e.g. new images that appeared after the sub-clustering) — so the remainder is
    // always a visible, routable group, never lost. The leftover is a real Group node, not a
    // per-render derivation.
    clusterEmptyBucket(bucketId: number, groups: Group[], emit = true) {
        const bucket = this.host.result.index[bucketId]
        if (!bucket) return
        this.emptyBucketId = bucketId

        const covered = new Set<number>()
        for (const g of groups) for (const s of g.slots) covered.add(s)
        const remainder = bucket.slots.filter(s => !covered.has(s))

        const all = [...groups]
        if (remainder.length) {
            const leftover = buildGroup(getTmpId(), remainder, GroupType.Cluster)
            leftover.name = 'New'
            leftover.isLeftover = true
            all.push(leftover)
        }
        this.addCustomGroups(bucketId, all, emit)
    }

    // Queue-drain (D5): the given instances just received the target value, so they leave the
    // undecided pile for their value-group. Remove them from the drained group (a cluster, or the
    // empty bucket itself when it has no clusters) and from the empty bucket's slots; the property
    // tree's incremental update (updateSelection) adds them to their value-group. O(delta) — no
    // regroup. Unworked piles and other value-groups are untouched.
    drain(groupId: number, instanceIds: number[], emit = true) {
        const group = this.host.result.index[groupId]
        if (!group || !instanceIds.length) return
        const col = useColumnStore()

        const slotSet = new Set<number>()
        for (const id of instanceIds) {
            const s = col.slotMap.get(id)
            if (s !== undefined) slotSet.add(s)
        }
        if (!slotSet.size) return

        group.slots = group.slots.filter(s => !slotSet.has(s))
        // A cluster's parent is the empty bucket — pull the drained slots out of it too. When the
        // drained group IS the empty bucket (no clusters yet), its own slots were just pruned and
        // root must keep the images (they're still present), so we don't touch the parent.
        if (group.type === GroupType.Cluster && group.parent) {
            group.parent.slots = group.parent.slots.filter(s => !slotSet.has(s))
        }
        // Drop the drained group's membership; the value-group membership is (re)added by
        // updateSelection when the value write reflows the property tree.
        for (const id of instanceIds) this.host.result.imageToGroups.get(id)?.delete(groupId)

        // A fully-drained cluster disappears (queue emptied). Never remove the empty bucket itself.
        if (group.slots.length === 0 && group.type === GroupType.Cluster && group.parent) {
            const parent = group.parent
            const idx = parent.children.indexOf(group)
            if (idx >= 0) parent.children.splice(idx, 1)
            for (let i = 0; i < parent.children.length; i++) parent.children[i].parentIdx = i
            delete this.host.result.index[groupId]
            const list = this.customGroups[parent.id]
            if (list) this.customGroups[parent.id] = list.filter(g => g.id !== groupId)
        }

        // Only the drained group and the bucket it came from changed.
        this.host.applySha1Piles(group.parent ? [group, group.parent] : [group])
        setOrder(this.host.result.root)
        this.host.buildOrdinalRanges()
        if (emit) this.host.emitResult()
    }

    // Reconcile the cluster overlay against the property tree after an updateSelection reflow.
    // updateSelection maintains each group's `slots` (adds new/updated images to their value-group,
    // drops departed ones) but deliberately leaves cluster children alone — so this reconciles the
    // sub-cluster partition against its parent's now-current membership. For every sub-clustered
    // parent (a group with cluster children), taking `parent.slots` as the source of truth:
    //   • a slot no longer in the parent (image removed, or its grouping value changed) is pulled
    //     out of whatever cluster child still holds it;
    //   • a slot in the parent that no cluster child covers is "new" to the group (an image that
    //     arrived after the sub-clustering) → collected into the "New" leftover pile so it stays
    //     visible and routable.
    // Runs only when a cluster overlay exists; O(clustered slots). Returns whether anything changed.
    reconcile(): boolean {
        if (Object.keys(this.customGroups).length === 0) return false
        const index = this.host.result.index
        const i2g = this.host.result.imageToGroups
        const ids = useColumnStore().instanceIds()
        let changed = false

        for (const parent of Object.values(index) as Group[]) {
            const clusterChildren = parent.children.filter(c => c.type === GroupType.Cluster)
            if (!clusterChildren.length) continue

            const parentSlots = new Set(parent.slots)
            const covered = new Set<number>()

            // (1) Drop slots that have left the parent from any cluster child still holding them.
            for (const c of clusterChildren) {
                if (c.slots.some(s => !parentSlots.has(s))) {
                    for (const s of c.slots) if (!parentSlots.has(s)) i2g.get(ids[s])?.delete(c.id)
                    c.slots = c.slots.filter(s => parentSlots.has(s))
                    changed = true
                }
                for (const s of c.slots) covered.add(s)
            }

            // (2) Collect parent slots that no cluster child covers into the "New" leftover pile.
            const uncovered = parent.slots.filter(s => !covered.has(s))
            if (uncovered.length) {
                const leftover = this.ensureLeftover(parent)
                const have = new Set(leftover.slots)
                for (const s of uncovered) {
                    if (have.has(s)) continue
                    leftover.slots.push(s)
                    let set = i2g.get(ids[s]); if (!set) { set = new Set<number>(); i2g.set(ids[s], set) }
                    set.add(leftover.id)
                    // Keep the parent membership so a later value change re-filters parent.slots.
                    set.add(parent.id)
                    changed = true
                }
            }

            // (3) A cluster child emptied by (1) disappears; the parent itself never does.
            for (const c of clusterChildren) {
                if (c.slots.length === 0) { this.detachCluster(parent, c); changed = true }
            }
        }
        return changed
    }

    private detachCluster(parent: Group, cluster: Group) {
        const idx = parent.children.indexOf(cluster)
        if (idx >= 0) parent.children.splice(idx, 1)
        for (let i = 0; i < parent.children.length; i++) parent.children[i].parentIdx = i
        delete this.host.result.index[cluster.id]
        const list = this.customGroups[parent.id]
        if (list) this.customGroups[parent.id] = list.filter(g => g.id !== cluster.id)
    }

    private ensureLeftover(bucket: Group): Group {
        const existing = bucket.children.find(c => c.type === GroupType.Cluster && c.isLeftover)
        if (existing) return existing
        const leftover = buildGroup(getTmpId(), [], GroupType.Cluster)
        leftover.name = 'New'
        leftover.isLeftover = true
        leftover.parent = bucket
        leftover.depth = bucket.depth + 1
        bucket.children.push(leftover)
        leftover.parentIdx = bucket.children.length - 1
        this.host.regsiterGroup(leftover)
        const list = this.customGroups[bucket.id] ?? []
        if (!list.includes(leftover)) { list.push(leftover); this.customGroups[bucket.id] = list }
        return leftover
    }
}
