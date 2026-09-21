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

// Drop one membership from the reverse index, and the map entry with it when it was the last
// one: an instance in no group leaves no empty Set behind. Readers treat an absent entry and an
// empty one alike ("not in the tree"), so the empty ones were pure growth.
function dropFromIndex(i2g: Map<number, Set<number>>, id: number, groupId: number) {
    const set = i2g.get(id)
    if (!set) return
    set.delete(groupId)
    if (set.size == 0) i2g.delete(id)
}

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
            // A dead pile stops being addressable: nodeOf / targetOf must not hand it back, or
            // an op would own images to a node whose images route to somebody else. The entry
            // goes here rather than in detachNode, which also serves nodes that are merely
            // waiting for their bucket and have to stay resolvable.
            this.nodeIndex.delete(node.group.id)
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

    // A node still in the table and not killed. Ops that resolve a group id to a node check
    // this before writing to it: a dead node accepts ownership but never shows it.
    isLive(c: ClusterContainer, idx: number): boolean {
        const node = c.table[idx]
        return !!node && !node.dead
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
        if (!parent) return
        if (parent.children.length) {
            parent.children = parent.children.filter(child => !mine.has(child.id))
            for (let i = 0; i < parent.children.length; i++) parent.children[i].parentIdx = i
            refreshSubGroupType(parent)
        }
        this.addLeafIndex(parent)
    }

    // The bucket displays its own images again: resync drops its imageToGroups entries at the
    // one point where it stops being a leaf (its piles are grafted), so they have to come back
    // at the one point where it becomes one again. Without this an un-clustered bucket was in
    // the tree while its images named no group at all — and an instance that names no group
    // reads as new to the tree, so the next update appended it to the root a second time.
    private addLeafIndex(group: Group) {
        if (group.children.length) return
        const ids = useColumnStore().instanceIds()
        const i2g = this.host.result.imageToGroups
        for (const s of group.slots) {
            const id = ids[s]
            let set = i2g.get(id)
            if (!set) { set = new Set<number>(); i2g.set(id, set) }
            set.add(group.id as number)
        }
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
        // Asked of the table, not of nodeIndex: a killed node is out of the index but is still
        // a child until the attach below rewrites the list.
        const foreign = parent ? this.hasForeignChildren(c, parent) : false
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
                this.addLeafIndex(parent)
                return true
            }
            return false
        }

        // What the container looked like before the pass, so the pass can report whether it
        // actually changed anything. Taken before the slots are cleared below.
        const before = this.fingerprint(c, parent)

        const col = useColumnStore()
        const ids = col.instanceIds()
        const i2g = this.host.result.imageToGroups

        // Drop the memberships the last pass wrote before refilling, so imageToGroups holds
        // exactly what the piles contain now.
        for (const node of c.table) {
            if (!node) continue
            for (const s of node.group.slots) dropFromIndex(i2g, ids[s], node.group.id)
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
        // imageToGroups names the leaves an instance is drawn in, and the bucket is not one once
        // its piles are grafted. Every path that fills the map writes the bucket while it is a
        // leaf — the rebuild's sweep, the incremental update's, the leaf it was before a
        // structural op clustered it — so the entries are dropped here, at the one point where it
        // stops being one. Piles that end up holding nothing leave the bucket a leaf, and then
        // its entries are the right ones.
        if (parent.children.length) {
            for (const s of parent.slots) dropFromIndex(i2g, ids[s], parent.id)
        }
        if (grpDebugOn()) this.logResync(c, parent, route)
        if (import.meta.env.DEV) this.checkInvariants(c, parent)
        // A pass that produced the same picture is not a change: reporting one here would make
        // every write to any property rebuild both scrollers for the whole dataset, however far
        // the write is from this bucket's piles (cluster_view_goals.md G4).
        return this.fingerprint(c, parent) !== before
    }

    // Everything a pass can alter about what is drawn, folded into one number: for every node
    // of the table — live, dead or detached — its group's slots in order, its wiring (attached
    // to the tree or not, its position under its parent, how many children it has) and the two
    // counts a card reads. The bucket's own child count goes in too, so a pile appearing or
    // disappearing is caught even when no slot moved. Everything else a pass writes is derived
    // from these: imageToGroups follows the slots, pileIndex and result.index follow the
    // attachment, and the owner/drained arrays only ever show up as a slot landing elsewhere or
    // as a different masked count. Two accumulators mixed with different constants make an
    // accidental match between two genuinely different pictures vanishingly unlikely. The cost
    // is one walk over the piles' slots, which together are the bucket's slots once — the same
    // budget as the pass itself, with nothing allocated per slot.
    private fingerprint(c: ClusterContainer, parent: Group): number {
        const index = this.host.result.index
        let h1 = 0x811c9dc5
        let h2 = 0x9e3779b9
        const mix = (v: number) => {
            const x = (v + 1) | 0
            h1 = Math.imul(h1 ^ x, 16777619) >>> 0
            h2 = (Math.imul(h2 + x, 2654435761) ^ (h2 >>> 15)) >>> 0
        }
        mix(c.table.length)
        mix(parent.children.length)
        for (const node of c.table) {
            if (!node) { mix(-1); continue }
            const g = node.group
            mix(g.slots.length)
            for (const s of g.slots) mix(s)
            mix(g.children.length)
            mix(g.parentIdx ?? -1)
            mix(g.depth)
            mix(index[g.id] === g ? 1 : 0)
            mix(g.meta.visibleCount ?? -1)
            mix(g.meta.maskedCount ?? -1)
        }
        return (h1 ^ Math.imul(h2, 31)) >>> 0
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
        // Named for what it holds: the images of this level that no pile covers. Group names are
        // raw strings everywhere in the tree (never run through vue-i18n), so this is a literal.
        group.name = 'No cluster'
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

    // Does the bucket hold children this container did not put there? True when a grouping
    // level was added below it: its children are that level's groups, not our piles. Read from
    // the table so the container's own dead nodes — still listed as children until the pass
    // rewrites the list — do not look foreign.
    private hasForeignChildren(c: ClusterContainer, parent: Group): boolean {
        if (!parent.children.length) return false
        const mine = new Set<number>()
        for (const node of c.table) if (node) mine.add(node.group.id)
        return parent.children.some(child => !mine.has(child.id))
    }

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
        for (const s of node.group.slots) dropFromIndex(result.imageToGroups, ids[s], node.group.id)
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

    // Every group a resync of this container can have rewritten: the bucket itself — it gains
    // or loses its piles, so its leaf status changes — plus every node group in the table, live,
    // dead or detached. Callers use it to scope per-leaf work (the sha1 pile overlay) without
    // re-deriving which leaves moved; including the dead and detached ones is what makes the
    // scoped pass drop their stale entries instead of leaving them behind.
    containerGroups(c: ClusterContainer): Group[] {
        const res: Group[] = []
        const parent = this.host.result.index[c.parentId]
        if (parent) res.push(parent)
        for (const node of c.table) if (node) res.push(node.group)
        return res
    }
}
