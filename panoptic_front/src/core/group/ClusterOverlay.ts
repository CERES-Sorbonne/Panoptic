/**
 * ClusterOverlay
 * The authored side of the cluster view: which pile owns which image.
 *
 * One ClusterContainer per clustered grouping leaf holds a dense `slot → node index` map plus
 * the node table that gives the cluster subtree its shape. Sub-clusters live in the same
 * container — depth is carried by the node table's `up` links, not by more containers — so any
 * number of levels and piles fits in one flat array per bucket.
 *
 * A cluster Group's `slots` is DERIVED: resync() refills it from the map after every tree
 * rebuild and after every incremental update. Nothing else writes membership, so a filter, a
 * sort or a reload cannot lose a pile — the images excluded from a build are simply not visited,
 * and the next build that includes them puts them back where their owner says.
 *
 * Only the operations in ClusterManager / groupOps write the map: own() when someone puts images
 * in a pile, release() when they leave the queue for a value, kill() when a pile is dropped. A
 * release is reversible — it remembers the pile, so an image the bucket gets back returns to it
 * instead of the leftover — and resync is the one place that honours the return. The
 * overlay is plain data and is never made reactive — change is signalled by the result version,
 * as for the rest of the tree.
 */
import { useColumnStore } from "@/data/stores/columnStore";
import { getTmpId } from "@/utils/utils";
import { buildGroup } from "./builders";
import { groupSlots, refreshSubGroupType } from "./groupOps";
import { ClusterOpsHost, Group, GroupType } from "./types";
import { grpLog, grpDebugOn, grpFocus, few } from "@/utils/debugGroup";

// One pile in a container. `up` is the node it was split out of, 0 at the top of the container.
// A dead node is never drawn and never rewritten out of the owner array: its images resolve to
// the nearest live ancestor, which is what makes "delete a pile" and "drop a sub-clustering"
// the same operation with different chains.
export interface ClusterNode {
    group: Group
    up: number
    dead: boolean
    // Authored member count — visible plus masked. Maintained by own()/release(), so the
    // masked badge is a subtraction rather than a scan.
    owned: number
    // The node that receives whatever its level does not name (un-clustered remainder).
    leftover: boolean
    // Position among its siblings. Piles keep the order the run produced them in; the
    // leftover always comes last, after the piles it is the remainder of.
    order: number
}

export class ClusterContainer {
    parentId: number
    // slot → node index. 0 means owned by no pile, which routes to the container's leftover.
    owner: Uint32Array
    // slot → the node it was drained from, 0 for none. A drain (the image was given the value
    // the bucket is the absence of) takes it out of its pile but records where it was, so that
    // the same image coming back to the bucket — an undo, a cleared value — returns to that
    // pile instead of the leftover. Cleared as soon as the return is honoured.
    drained: Uint32Array
    // Index 0 is unused so that 0 can mean "unowned".
    table: (ClusterNode | null)[]
    // Slot generation this map was written against (columnStore re-mints slots on reset).
    epoch: number

    constructor(parentId: number, epoch: number) {
        this.parentId = parentId
        this.owner = new Uint32Array(0)
        this.drained = new Uint32Array(0)
        this.table = [null]
        this.epoch = epoch
    }
}

export class ClusterOverlay {
    // Clustered grouping leaf id → its container.
    byGroup = new Map<number, ClusterContainer>()
    // Cluster group id → the node holding it, so an op that knows only a group id finds both.
    private nodeIndex = new Map<number | string, { c: ClusterContainer, idx: number }>()

    constructor(private host: ClusterOpsHost) { }

    // ── Lookup ───────────────────────────────────────────────────────────────

    container(parentId: number): ClusterContainer | undefined {
        return this.byGroup.get(parentId)
    }

    nodeOf(groupId: number | string): { c: ClusterContainer, idx: number } | undefined {
        return this.nodeIndex.get(groupId)
    }

    // The container a group belongs to, whether it is the clustered bucket itself or one of
    // its piles, with the node index to graft under (0 = the top of the container).
    targetOf(groupId: number | string): { c: ClusterContainer, up: number } | undefined {
        const node = this.nodeIndex.get(groupId)
        if (node) return { c: node.c, up: node.idx }
        const c = typeof groupId === 'number' ? this.byGroup.get(groupId) : undefined
        return c ? { c, up: 0 } : undefined
    }

    hasClusters(): boolean {
        for (const c of this.byGroup.values()) if (this.liveNodes(c).length) return true
        return false
    }

    ensureContainer(parentId: number): ClusterContainer {
        const epoch = useColumnStore().slotEpoch()
        let c = this.byGroup.get(parentId)
        if (c && c.epoch !== epoch) { this.dropContainer(parentId); c = undefined }
        if (!c) {
            c = new ClusterContainer(parentId, epoch)
            this.byGroup.set(parentId, c)
        }
        return c
    }

    // ── Writing the map ──────────────────────────────────────────────────────

    // Grow the map with the store. Allocated on the first own(), so a container that owns
    // nothing costs nothing.
    private grow(c: ClusterContainer) {
        const count = useColumnStore().slotCount()
        if (c.owner.length >= count) return
        const next = new Uint32Array(count)
        next.set(c.owner)
        c.owner = next
        const nextDrained = new Uint32Array(count)
        nextDrained.set(c.drained)
        c.drained = nextDrained
    }

    addNode(c: ClusterContainer, group: Group, up: number, leftover = false, order?: number): number {
        const idx = c.table.length
        c.table.push({ group, up, dead: false, owned: 0, leftover, order: order ?? idx })
        this.nodeIndex.set(group.id, { c, idx })
        return idx
    }

    // Where a pile sits among its siblings, so an op that replaces piles can keep the position.
    orderOf(c: ClusterContainer, idx: number): number {
        return c.table[idx]?.order ?? 0
    }

    // Put these slots in a pile. One owner per slot per container, so this also takes them out
    // of whatever pile of the same container held them.
    own(c: ClusterContainer, slots: Iterable<number>, idx: number) {
        this.grow(c)
        for (const s of slots) {
            if (s < 0 || s >= c.owner.length) continue
            const prev = c.owner[s]
            if (prev === idx) continue
            const before = c.table[prev]
            if (before) before.owned--
            c.owner[s] = idx
            // Taking a real owner supersedes any drain record: the slot is a member again,
            // so there is nothing left to restore.
            if (idx && s < c.drained.length) c.drained[s] = 0
            const after = c.table[idx]
            if (after) after.owned++
        }
    }

    // These images left the queue: assigned a value, or dragged into a value-group. They stop
    // being members — the pile does not count them, masked or otherwise — but the pile they
    // left is remembered, so undoing the value write that drained them puts them back where
    // they were rather than in the leftover (restoreDrained, called from resync).
    release(c: ClusterContainer, slots: Iterable<number>) {
        this.grow(c)
        for (const s of slots) {
            if (s < 0 || s >= c.owner.length) continue
            if (c.owner[s]) c.drained[s] = c.owner[s]
        }
        this.own(c, slots, 0)
    }

    // The image is in the bucket again while carrying a drain record: the value that took it
    // out is gone, so it is undecided once more and its pile owns it again. Returns the node
    // that now owns the slot.
    private restoreDrained(c: ClusterContainer, slot: number): number {
        const from = c.drained[slot]
        c.drained[slot] = 0
        if (!from || !c.table[from]) return 0
        this.own(c, [slot], from)
        return from
    }

    // Drop a pile: the node and its whole subtree stop existing. Their images are not rewritten;
    // they resolve to the nearest live ancestor on the next pass — the level's leftover for a
    // deleted pile, the pile itself when a sub-clustering is dropped.
    kill(c: ClusterContainer, idx: number) {
        const kids = this.childrenOf(c)
        const walk = (i: number) => {
            const node = c.table[i]
            if (!node || node.dead) return
            for (const k of kids[i]) walk(k)
            node.dead = true
            this.detachNode(c, node)
        }
        walk(idx)
    }

    // Drop the level below a node (0 = the whole container): re-clustering replaces the piles
    // that were there, and dropping a sub-clustering gives the pile its images back.
    killChildren(c: ClusterContainer, up: number) {
        for (const k of this.childrenOf(c)[up] ?? []) this.kill(c, k)
    }

    // The node a pile was split out of, 0 at the top of the container.
    upOf(c: ClusterContainer, idx: number): number {
        return c.table[idx]?.up ?? 0
    }

    isLeftover(c: ClusterContainer, idx: number): boolean {
        return c.table[idx]?.leftover === true
    }

    // Forget a bucket's overlay entirely, leaving it an ordinary leaf. The piles are unhooked
    // from the tree as well as from the table: a card left behind would be an orphan, drawn but
    // no longer registered.
    dropContainer(parentId: number) {
        const c = this.byGroup.get(parentId)
        if (!c) return
        const mine = new Set<number | string>()
        for (const node of c.table) {
            if (!node) continue
            mine.add(node.group.id)
            this.nodeIndex.delete(node.group.id)
            this.detachNode(c, node)
        }
        this.byGroup.delete(parentId)

        const parent = this.host.result.index[parentId]
        if (!parent || !parent.children.length) return
        parent.children = parent.children.filter(child => !mine.has(child.id))
        for (let i = 0; i < parent.children.length; i++) parent.children[i].parentIdx = i
        refreshSubGroupType(parent)
    }

    clear() {
        for (const parentId of Array.from(this.byGroup.keys())) this.dropContainer(parentId)
        this.byGroup.clear()
        this.nodeIndex.clear()
    }

    // ── Resync: the only reader of the tree ──────────────────────────────────

    // Refill every pile of every container that still has a bucket in the current tree.
    resyncAll() {
        this.dropStaleEpochs()
        for (const c of Array.from(this.byGroup.values())) this.resync(c)
    }

    // Same, restricted to the buckets an edit touched. A value write can move an instance in
    // several grouping leaves at once (a multi-value tag grouping puts it in several), so the
    // caller passes every group id that changed, not only the one it acted on.
    resyncDirty(groupIds: Set<number>): boolean {
        this.dropStaleEpochs()
        let changed = false
        // A bucket that holds a container but is not in the dirty set is never refilled: the
        // images the update moved into it stay out of the piles until a full rebuild.
        if (grpDebugOn()) {
            grpLog('6c \u00b7 cluster.resyncDirty', {
                dirtyGroups: few(groupIds, 30),
                containers: Array.from(this.byGroup.values()).map(c => {
                    const col = useColumnStore()
                    const bucket = this.host.result.index[c.parentId]
                    return {
                        bucketId: c.parentId,
                        matched: groupIds.has(c.parentId),
                        piles: this.liveNodes(c).length,
                        bucketInTree: !!bucket,
                        // An update that puts an image back in this bucket while the bucket is
                        // not in the dirty set leaves it in bucket.slots but in no pile: the
                        // count goes up and the image is drawn nowhere.
                        focusInBucket: grpFocus().filter(id => {
                            const slot = col.slotMap.get(id)
                            return slot !== undefined && !!bucket?.slots.includes(slot)
                        }),
                    }
                }),
            })
        }
        for (const c of Array.from(this.byGroup.values())) {
            if (!groupIds.has(c.parentId)) continue
            if (this.resync(c)) changed = true
        }
        return changed
    }

    private dropStaleEpochs() {
        const epoch = useColumnStore().slotEpoch()
        for (const c of Array.from(this.byGroup.values())) {
            if (c.epoch !== epoch) this.dropContainer(c.parentId)
        }
    }

    // One pass over the bucket's current slots: each lands in the leaf its owner resolves to,
    // in display order, and whatever the map does not name lands in the leftover. Membership,
    // order and the leftover all come out of the same loop.
    resync(c: ClusterContainer): boolean {
        const parent = this.host.result.index[c.parentId]
        const live = this.liveNodes(c)
        // The bucket is not in this tree (filtered away), or it is no longer a leaf of the
        // grouping — a level was added below it, and its children are that level, not ours.
        // The container waits: its piles are unregistered, the map is untouched, and they come
        // back when the bucket does.
        const foreign = parent?.children.some(child => !this.nodeIndex.has(child.id))
        if (!parent || foreign) {
            let detached = false
            for (const idx of live) {
                if (this.host.result.index[c.table[idx]!.group.id]) detached = true
                this.detachNode(c, c.table[idx]!)
            }
            return detached
        }
        if (!live.length) {
            this.dropContainer(c.parentId)
            if (parent.children.length) {
                this.host.removeChildren(parent)
                return true
            }
            return false
        }

        const col = useColumnStore()
        const ids = col.instanceIds()
        const i2g = this.host.result.imageToGroups

        // Drop the memberships the last pass wrote before refilling, so imageToGroups holds
        // exactly what the piles contain now.
        for (const node of c.table) {
            if (!node) continue
            for (const s of node.group.slots) i2g.get(ids[s])?.delete(node.group.id)
            node.group.slots.length = 0
        }

        this.ensureLeftovers(c)
        const route = this.buildRoute(c)

        for (const s of parent.slots) {
            let stored = s < c.owner.length ? c.owner[s] : 0
            // In the bucket again, owned by nobody, but drained from a pile: the value that
            // took it out is gone, so the pile takes it back.
            if (!stored && s < c.drained.length && c.drained[s]) stored = this.restoreDrained(c, s)
            const leaf = c.table[route[stored]]!
            leaf.group.slots.push(s)
            const id = ids[s]
            let set = i2g.get(id)
            if (!set) { set = new Set<number>(); i2g.set(id, set) }
            set.add(leaf.group.id)
        }

        this.attach(c, parent, route)
        if (grpDebugOn()) this.logResync(c, parent, route)
        if (import.meta.env.DEV) this.checkInvariants(c, parent)
        return true
    }

    // Where the update's instances ended up in this bucket's piles. The authored map is what
    // decides: an instance the map still owns returns to its pile, one that was released
    // (drained on a value write) routes to the leftover, whatever the tree does.
    private logResync(c: ClusterContainer, parent: Group, route: Int32Array) {
        const col = useColumnStore()
        grpLog('6d \u00b7 cluster.resync', {
            bucketId: c.parentId, bucketSlots: parent.slots.length,
            piles: this.liveNodes(c).map(i => {
                const node = c.table[i]!
                return {
                    idx: i, id: node.group.id, name: node.group.name,
                    leftover: node.leftover, owned: node.owned, visible: node.group.slots.length,
                }
            }),
            probe: grpFocus().map(id => {
                const slot = col.slotMap.get(id)
                if (slot === undefined) return { id, slot: undefined, note: 'no slot' }
                const inBucket = parent.slots.includes(slot)
                const stored = slot < c.owner.length ? c.owner[slot] : 0
                const leafIdx = route[stored]
                const leaf = c.table[leafIdx]
                return {
                    id, slot, inBucket,
                    // 0 = owned by no pile → routed to the bucket's leftover. This is what a
                    // release leaves behind, and it survives the undo.
                    ownerNode: stored,
                    ownerPile: c.table[stored]?.group.name,
                    routedTo: leaf?.group.name, routedIsLeftover: leaf?.leftover,
                    landedInPile: !!leaf && leaf.group.slots.includes(slot),
                }
            }),
        })
    }

    // The five rules the structure is meant to guarantee, checked after a pass. Development
    // only: each one walks the bucket once more, which is exactly what the pass avoids doing.
    private checkInvariants(c: ClusterContainer, parent: Group) {
        const fail = (rule: string, detail: string) =>
            console.error(`[ClusterOverlay] ${rule} broken on bucket ${c.parentId}: ${detail}`)

        // I1 — every image of the bucket lands in exactly one leaf.
        let routed = 0
        const seen = new Set<number>()
        const walk = (g: Group) => {
            if (!g.children.length) {
                routed += g.slots.length
                for (const s of g.slots) {
                    if (seen.has(s)) fail('I1', `slot ${s} is in two leaves`)
                    seen.add(s)
                }
            } else g.children.forEach(walk)
        }
        parent.children.forEach(walk)
        if (routed !== parent.slots.length) {
            fail('I1', `routed ${routed} of ${parent.slots.length} slots`)
        }

        // I2 — ownership is relative to this bucket: every owner value names a real node, and
        // nothing the bucket holds is owned by a node of another container.
        for (let s = 0; s < c.owner.length; s++) {
            const v = c.owner[s]
            if (v && !c.table[v]) { fail('I2', `slot ${s} owned by unknown node ${v}`); break }
        }

        // I3 — the authored totals and the owner array agree. A pass writes the map only to
        // honour a return (restoreDrained), which goes through own() and so moves both.
        const owned = c.table.reduce((sum, n) => sum + (n ? n.owned : 0), 0)
        let counted = 0
        for (let s = 0; s < c.owner.length; s++) if (c.owner[s]) counted++
        if (owned !== counted) fail('I3', `authored total ${owned} but ${counted} slots are owned`)

        // I4 — the map still describes the store's current slots.
        if (c.epoch !== useColumnStore().slotEpoch()) fail('I4', 'epoch mismatch survived the pass')

        // I5 — a leaf's slots follow the bucket's display order.
        const pos = new Map<number, number>()
        for (let i = 0; i < parent.slots.length; i++) pos.set(parent.slots[i], i)
        const ordered = (g: Group) => {
            if (!g.children.length) {
                for (let i = 1; i < g.slots.length; i++) {
                    if ((pos.get(g.slots[i]) ?? -1) <= (pos.get(g.slots[i - 1]) ?? -1)) {
                        fail('I5', `group ${g.id} is out of display order`)
                        return
                    }
                }
            } else g.children.forEach(ordered)
        }
        parent.children.forEach(ordered)
    }

    // Stored value → the leaf node that receives it. Resolving the dead chain and descending
    // through sub-clustered levels once per table entry keeps the per-slot work to one read.
    private buildRoute(c: ClusterContainer): Int32Array {
        const kids = this.childrenOf(c)
        const route = new Int32Array(c.table.length)
        for (let v = 0; v < c.table.length; v++) {
            let i = v
            while (i && (!c.table[i] || c.table[i]!.dead)) i = c.table[i]?.up ?? 0
            route[v] = this.leafFrom(c, kids, i)
        }
        return route
    }

    // From a resolved node down to the leaf that holds images: the container's leftover for 0,
    // then the leftover child of every level that has been sub-clustered.
    private leafFrom(c: ClusterContainer, kids: number[][], i: number): number {
        let current = i
        for (let guard = 0; guard <= c.table.length; guard++) {
            const children = current === 0 ? kids[0] : kids[current]
            if (!children.length) return current
            const leftover = children.find(k => c.table[k]!.leftover)
            if (leftover === undefined) return current
            current = leftover
        }
        return current
    }

    // Every level that has been split needs a leftover child, so routing always ends on a leaf.
    private ensureLeftovers(c: ClusterContainer) {
        const kids = this.childrenOf(c)
        const need: number[] = []
        for (let i = 0; i < c.table.length; i++) {
            if (i > 0 && (!c.table[i] || c.table[i]!.dead)) continue
            if (!kids[i].length) continue
            if (kids[i].some(k => c.table[k]!.leftover)) continue
            need.push(i)
        }
        for (const up of need) this.addLeftover(c, up)
    }

    addLeftover(c: ClusterContainer, up: number): number {
        const group = buildGroup(getTmpId(), [], GroupType.Cluster)
        group.name = 'New'
        group.isLeftover = true
        return this.addNode(c, group, up, true)
    }

    // Graft the piles that have something to show. A pile whose images are all masked stays in
    // the table — it owns them and returns when they do — but is not attached, so no empty card
    // appears and no orphan sits in the index.
    private attach(c: ClusterContainer, parent: Group, route: Int32Array) {
        const kids = this.childrenOf(c)

        // Authored totals land on the leaf that currently receives them, so a dead pile's
        // members are counted by whoever inherited them.
        const authored = new Int32Array(c.table.length)
        for (let v = 1; v < c.table.length; v++) {
            const node = c.table[v]
            if (node) authored[route[v]] += node.owned
        }

        const visible = new Int32Array(c.table.length)
        const masked = new Int32Array(c.table.length)
        const count = (i: number) => {
            if (kids[i].length) {
                for (const k of kids[i]) {
                    count(k)
                    visible[i] += visible[k]
                    masked[i] += masked[k]
                }
            } else if (i > 0) {
                visible[i] = c.table[i]!.group.slots.length
                masked[i] = Math.max(0, authored[i] - visible[i])
            }
        }
        count(0)

        const wire = (group: Group, i: number) => {
            const children: Group[] = []
            for (const k of kids[i]) {
                if (visible[k] > 0) children.push(c.table[k]!.group)
                else this.detachSubtree(c, kids, k)
            }
            for (let idx = 0; idx < children.length; idx++) {
                const child = children[idx]
                child.parent = group
                child.parentIdx = idx
                child.depth = group.depth + 1
                this.host.regsiterGroup(child)
            }
            group.children = children
            refreshSubGroupType(group)
            for (const k of kids[i]) {
                if (visible[k] <= 0) continue
                const node = c.table[k]!
                // What a card reads: the images it shows, and beside them what it owns and
                // cannot currently show.
                node.group.meta.visibleCount = visible[k]
                node.group.meta.maskedCount = masked[k] > 0 ? masked[k] : undefined
                wire(node.group, k)
            }
        }
        wire(parent, 0)
    }

    // ── Table helpers ────────────────────────────────────────────────────────

    private liveNodes(c: ClusterContainer): number[] {
        const res: number[] = []
        for (let i = 1; i < c.table.length; i++) if (c.table[i] && !c.table[i]!.dead) res.push(i)
        return res
    }

    // Live children per node, index 0 holding the top level of the container.
    private childrenOf(c: ClusterContainer): number[][] {
        const kids: number[][] = []
        for (let i = 0; i < c.table.length; i++) kids.push([])
        for (let i = 1; i < c.table.length; i++) {
            const node = c.table[i]
            if (!node || node.dead) continue
            kids[node.up].push(i)
        }
        for (const list of kids) {
            list.sort((a, b) => {
                const na = c.table[a]!, nb = c.table[b]!
                if (na.leftover !== nb.leftover) return na.leftover ? 1 : -1
                return na.order - nb.order
            })
        }
        return kids
    }

    private detachSubtree(c: ClusterContainer, kids: number[][], i: number) {
        for (const k of kids[i]) this.detachSubtree(c, kids, k)
        this.detachNode(c, c.table[i]!)
    }

    // Take a node's group out of the tree structures, leaving the node (and its owned images)
    // in the table.
    private detachNode(c: ClusterContainer, node: ClusterNode) {
        const result = this.host.result
        const ids = useColumnStore().instanceIds()
        for (const s of node.group.slots) result.imageToGroups.get(ids[s])?.delete(node.group.id)
        node.group.slots.length = 0
        node.group.children = []
        node.group.meta.maskedCount = undefined
        node.group.meta.visibleCount = undefined
        if (result.index[node.group.id] === node.group) delete result.index[node.group.id]
        result.pileIndex.delete(node.group.id as number)
    }

    // ── Membership reads ─────────────────────────────────────────────────────

    // Every slot a node owns, including the ones the current build does not show. Used by the
    // operations that act on a whole pile (delete, merge) so masked members follow.
    ownedSlots(c: ClusterContainer, idx: number): number[] {
        const subtree = new Set<number>([idx])
        const kids = this.childrenOf(c)
        const walk = (i: number) => { for (const k of kids[i]) { subtree.add(k); walk(k) } }
        walk(idx)
        const res: number[] = []
        for (let s = 0; s < c.owner.length; s++) if (subtree.has(c.owner[s])) res.push(s)
        return res
    }

    // The visible images of a node, including those of its sub-piles.
    visibleSlots(group: Group): number[] {
        return groupSlots(group)
    }
}
