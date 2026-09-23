/**
 * GroupManager
 * Builds a Group tree from an Int32Array of sorted slot indices (pre-sorted by SortManager).
 *
 * Key invariants:
 *  - Group.slots: number[]         — column-store slot indices
 *  - GroupTree.orderedIds           — instance IDs in DFS display order (invalidated by each structural
 *                                     change, rebuilt lazily on read — see GroupResult.ensureOrderedIds)
 *  - GroupValueIndex is persistent  — group IDs are stable across rebuilds (view state preserved)
 *  - imageToGroups: Map<instanceId, Set<leafGroupId>>  — O(1) lookup and delete
 *  - computePropertySubGroup pre-buckets slots before key construction — zero per-slot spread allocations
 *  - Date bucketing uses epoch-ms integer arithmetic — zero Date allocations in scan loop
 */

import { deletedID, GroupScoreList, PropertyIndex, PropertyValue, TagIndex } from "@/data/models";
import { Ref, reactive } from "vue";
import { PropertyType } from "@/data/models";
import { EventEmitter, isTag, objValues } from "@/utils/utils";
import { useDataStore } from "@/data/stores/dataStore";
import { useColumnStore } from "@/data/stores/columnStore";
import { computeSha1Piles } from "./sha1Piles";

// ── group/* modules (extracted concerns) ────────────────────────────────────
import {
    GroupType, GroupState, Group, GroupTree, GroupOption,
    ClusterOpsHost,
} from "./group/types";
import { buildGroup, buildRoot, buildGroupOption, createGroupState } from "./group/builders";
import { sortGroup, setOrder } from "./group/sort";
import { valueParser } from "./group/valueParser";
import { dateBucketKey, dateBucketRange } from "./group/dateBuckets";
import { GroupIterator, ImageIterator, GroupIteratorOptions } from "./group/GroupIterator";
import { GroupResult } from "./group/GroupResult";
import { GroupNavigator } from "./group/GroupNavigator";
import { ClusterManager, ClusterRequest } from "./group/ClusterManager";
import { refreshSubGroupType } from "./group/groupOps";
import { orderSlots, SlotPositions } from "./group/slotOrder";
import type { GroupInspector } from "./group/inspector";
import { grpLog, grpDebugOn, grpSetFocus, few } from '@/utils/debugGroup';

// ── Barrel re-exports — keep `@/core/GroupManager` as the public entry point ─
export { GroupType, GroupSortType } from "./group/types";
export type {
    GroupState, Group, GroupView, ClusterParam, GroupMetaData,
    GroupIndex, GroupTree, GroupOption, SelectedImages,
} from "./group/types";
export { buildGroup, buildGroupOption, createGroupState } from "./group/builders";
export type { ClusterRequest, ClusterRun } from "./group/ClusterManager";
export { GroupIterator, ImageIterator } from "./group/GroupIterator";
export type { GroupIteratorOptions } from "./group/GroupIterator";
export type { GroupInspector } from "./group/inspector";

export class GroupManager implements ClusterOpsHost, GroupInspector {
    state: GroupState
    // The composed tree + iterators + result-change signal now live on GroupResult;
    // the manager is the engine that fills it. GroupResult satisfies GroupTree, so callers
    // that read `manager.result.index` etc. are unaffected.
    result: GroupResult
    // The cluster/custom-group overlay lives here now, not on the manager. GroupManager stays
    // the pure property-tree engine; cluster ops are delegating facades (below).
    clusters: ClusterManager
    // Traversal/view state over the result tree: open/close + selection + shift anchors.
    // The manager keeps thin delegating facades (below) so existing callers are unaffected.
    nav: GroupNavigator

    // Slot→position typed array from the last group() call (faster than plain-object map).
    // _posArr[slot] = display position; replaces ImageOrder = {[slot]: pos}.
    private _posArr: Int32Array
    private _posMaxSlot: number
    // Number of slots in the last group() call — the base position handed to slots that
    // appeared since (so they sort after everything the last full sort ordered).
    private _posCount = 0
    // When true, saveImagesToGroup is a no-op — avoids redundant Map writes during full rebuild.
    private _rebuildingTree = false
    // Leaf groups collected during computePropertySubGroup — avoids Object.values() in post-loop.
    private _leafGroups: Group[] = []
    onStateChange: EventEmitter
    // Scores of the collection's active search (set by CollectionManager). Not reactive state.
    scoreSource: () => GroupScoreList | undefined = () => undefined

    // Result-change signal + legacy event live on GroupResult now; expose delegating getters
    // so existing callers (`manager.version.value`, `manager.onResultChange`) keep working.
    get version(): Ref<number> { return this.result.version }
    get onResultChange(): EventEmitter { return this.result.onResultChange }

    // Selection lives in columnStore, keyed by namespace (note §5, step 2), and is
    // driven by GroupNavigator (this.nav). Delegating getter kept for callers reading
    // `manager.selectionNamespace`.
    get selectionNamespace(): string { return this.nav.selectionNamespace }

    // Alias of `state` under the name the GroupInspector contract uses (CollectionManager
    // already owns `state` for its CollectionState, so the shared surface says `groupState`).
    get groupState(): GroupState { return this.state }

    constructor(state?: GroupState) {
        if (state) {
            this.state = reactive(state)
        } else {
            this.state = reactive(createGroupState())
        }
        this.result = new GroupResult()
        this.clusters = new ClusterManager(this)
        this.nav = new GroupNavigator(this.result)
        this._posArr = new Int32Array(0)
        this._posMaxSlot = 0
        this.onStateChange = new EventEmitter()
    }

    // Bump the reactive version tick AND emit the legacy event. The version ref
    // is the new result-change contract (UI watches it); onResultChange is kept
    // during the transition for any not-yet-migrated internal listener.
    emitResult() {
        this.result.emitResult()
    }

    // ── Column requirements ────────────────────────────────────────────────

    getRequiredColumns(): number[] {
        return [...this.state.groupBy]
    }

    private async _ensureColumns(): Promise<void> {
        const col = useColumnStore()
        await Promise.all(this.getRequiredColumns().map(id => col.requireFullColumn(id)))
    }

    // ── Public API ─────────────────────────────────────────────────────────

    async group(slots: Int32Array, emit?: boolean): Promise<GroupTree> {
        await this._ensureColumns()
        const data = useDataStore()

        // Build slot→position as typed array — O(1) access vs plain-object hash lookup.
        // Single pass to find maxSlot so we can pre-allocate the exact typed array size.
        // Pre-filled with -1 so "position 0" and "slot absent from this run" stay
        // distinguishable (see slotPos, used by the incremental re-sort).
        let maxSlot = 0
        for (let i = 0; i < slots.length; i++) if (slots[i] > maxSlot) maxSlot = slots[i]
        this._posArr = new Int32Array(maxSlot + 1).fill(-1)
        for (let i = 0; i < slots.length; i++) this._posArr[slots[i]] = i
        this._posMaxSlot = maxSlot
        this._posCount = slots.length

        const lastIndex = this.result.index ?? {}
        this.result.root = buildRoot(Array.from(slots))
        this.result.index = {}
        this.result.imageToGroups = new Map()
        this.result.pileIndex = new Map()
        this._leafGroups = []
        this.regsiterGroup(this.result.root)

        // Suppress saveImagesToGroup during tree construction — we do one clean sweep below.
        this._rebuildingTree = true
        if (this.state.groupBy.length > 0) {
            this.computePropertySubGroup(this.result.root, this.state.groupBy, data.properties, data.tags)
        }
        this._rebuildingTree = false

        // Single imageToGroups sweep using tracked leaf groups (avoids Object.values allocation).
        // These are the leaves of the PROPERTY tree; a bucket that turns out to be clustered
        // stops being a leaf in the resync below, which drops the entries written here for it.
        const ids = useColumnStore().instanceIds()
        const leafGroups = this.state.groupBy.length > 0 ? this._leafGroups : [this.result.root]
        for (const g of leafGroups) {
            for (const s of g.slots) {
                const id = ids[s]
                let set = this.result.imageToGroups.get(id)
                if (!set) { set = new Set<number>(); this.result.imageToGroups.set(id, set) }
                set.add(g.id)
            }
        }

        // Refill the piles from the authored map. The rebuild never touched it, so a pile comes
        // back with the images it owns that this tree holds.
        grpLog('6e \u00b7 full rebuild \u2192 cluster.resyncAll')
        this.clusters.resyncAll()

        this.applySha1Piles()

        for (const id of Object.keys(this.result.index)) {
            const group = this.result.index[id]
            if (lastIndex[id]) group.view = lastIndex[id].view
        }

        setOrder(this.result.root)
        this.buildOrdinalRanges()
        if (emit) this.emitResult()
        return this.result
    }

    // Delegates to GroupResult (owns orderedIds / display order).
    buildOrdinalRanges(): void {
        this.result.buildOrdinalRanges()
    }

    // `joined` collects every group the slots were added to. An image coming back to a clustered
    // bucket is named by no old membership — imageToGroups holds the leaves, and the bucket's
    // leaves are its piles — so this is the caller's only way to learn that the bucket changed.
    // `appendedFrom` records, per group, how long its slot array was before this call appended
    // to it — the boundary the incremental re-order merges at (see orderSlots).
    // `newToTree` names the slots that were in no group at all before this update: with grouping
    // active they are the only ones the root is missing (see the append below).
    private addUpdatedToGroups(slots: Int32Array, joined?: Set<number>, appendedFrom?: Map<number, number>, newToTree?: Set<number>) {
        if (!this.result.root) {
            this.group(slots)
            return
        }

        const data = useDataStore()

        if (this.state.groupBy.length > 0) {
            // Hoist tagWithParents out of the per-slot loop: build once per grouped tag property.
            const tagParentsByProp: { [propId: number]: { [id: number]: Set<number> } } = {}
            for (const propId of this.state.groupBy) {
                const property = data.properties[propId]
                if (!isTag(property?.type) || !property.tags) continue
                const map: { [id: number]: Set<number> } = {}
                for (const tag of objValues(property.tags)) {
                    map[tag.id] = new Set(tag.allParents)
                    map[tag.id].add(tag.id)
                }
                tagParentsByProp[propId] = map
            }
            for (let i = 0; i < slots.length; i++) {
                this.addInstanceToGroups(slots[i], data.properties, data.tags, tagParentsByProp, joined, appendedFrom)
            }
            // addInstanceToGroups only reaches value-key groups (valueIndex never mints 0), so the
            // root gains nothing there. It keeps the slots it already holds — updateSelection
            // exempts the grouped root from the updated-slot filter — so the only ones missing
            // from it are the arrivals that were in no group before: a newly imported instance, or
            // one a lifted filter brought back. Without this they sit in their leaves while root
            // understates the collection, and the next update() — which re-groups from root.slots
            // — drops them for good.
            if (newToTree?.size) {
                const root = this.result.root
                let appended = false
                for (let i = 0; i < slots.length; i++) {
                    if (!newToTree.has(slots[i])) continue
                    if (!appended) {
                        appended = true
                        // Same merge boundary the value groups record, so orderSlots merges the
                        // arrivals in instead of mis-reading the root as unordered.
                        if (appendedFrom && !appendedFrom.has(root.id as number)) {
                            appendedFrom.set(root.id as number, root.slots.length)
                        }
                    }
                    root.slots.push(slots[i])
                }
                if (appended) {
                    root.dirty = true
                    joined?.add(root.id as number)
                }
            }
        } else {
            if (slots.length && appendedFrom && !appendedFrom.has(this.result.root.id as number)) {
                appendedFrom.set(this.result.root.id as number, this.result.root.slots.length)
            }
            for (let i = 0; i < slots.length; i++) {
                this.result.root.slots.push(slots[i])
            }
            this.result.root.dirty = true
            joined?.add(this.result.root.id as number)
        }
        // Slot re-sort, imageToGroups maintenance, and setOrder are done by the caller
        // (updateSelection) over the dirty subset only — no full O(n) sweep here.
    }

    addInstanceToGroups(slot: number, properties: PropertyIndex, tags: TagIndex, tagParentsByProp: { [propId: number]: { [id: number]: Set<number> } }, joined?: Set<number>, appendedFrom?: Map<number, number>) {
        const col = useColumnStore()
        // The running set of value-keys for this slot, one per level descended so far. (There
        // used to be a parallel `keys` accumulator collecting every level's keys; nothing read
        // it, and its `push(...spread)` risked blowing the stack on a wide tag fan-out.)
        let previousKeys: any[][] = []

        for (const propId of this.state.groupBy) {
            const property = properties[propId]
            const option = this.state.options[property.id]
            let value = col.readSlot(propId, slot)
            value = valueParser[property.type](value)

            // tagWithParents is prebuilt once per batch by the caller — hoisted out of the
            // per-slot loop (previously rebuilt for every slot × property).
            const tagWithParents = tagParentsByProp[propId] ?? {}

            let intervalEnd: Date | undefined
            if (property.type == PropertyType.date) {
                const bucketKey = dateBucketKey(value as Date, option.stepSize, option.stepUnit)
                if (bucketKey !== undefined) {
                    intervalEnd = dateBucketRange(bucketKey, option.stepSize, option.stepUnit).last
                    value = bucketKey
                } else {
                    value = undefined
                }
            }

            let values = Array.isArray(value) ? value : [value]
            if (isTag(property.type) && values[0] !== undefined) {
                // Same registry rule as the full build (computePropertySubGroup): an id the
                // registry does not name is dropped rather than grouped on, and a slot left
                // with nothing falls through to the empty bucket below. The two paths used to
                // disagree here — this one kept the id, the full build silently dropped the
                // whole slot — so an image moved or disappeared on the next regroup.
                const withParents = new Set<any>()
                for (const v of values) {
                    if (!v) continue
                    const parents = tagWithParents[v]
                    if (!parents) continue
                    for (const p of parents) withParents.add(p)
                }
                values = Array.from(withParents)
            }

            // An empty tag list means "no value", so it belongs in the empty bucket — the same
            // key the full build uses for it (computePropertySubGroup). Without this the slot
            // produces no key at all and joins no group.
            if (isTag(property.type) && values.length === 0) {
                // Guarded: this sits in a per-slot loop, so an unguarded call allocates one
                // object per slot even with logging off.
                if (grpDebugOn()) grpLog('6b \u00b7 empty tag list \u2192 empty bucket', { slot, propId, value })
                values = [undefined]
            }

            if (values.length === 0) {
                // Guarded for the same reason as 6b above.
                if (grpDebugOn()) grpLog('6 \u00b7 NO KEY for slot \u2014 it will join no group', {
                    slot, propId, type: property.type, value,
                    isArray: Array.isArray(value),
                    length: Array.isArray(value) ? (value as any[]).length : undefined,
                })
            }

            if (previousKeys.length == 0) {
                previousKeys = values.map(v => [v])
            } else {
                const newKeys: any[][] = []
                for (const prevK of previousKeys) {
                    for (const val of values) newKeys.push([...prevK, val])
                }
                previousKeys = newKeys
            }

            for (const key of previousKeys) {
                const groupId = this.result.valueIndex.get(key)
                if (!this.result.index[groupId]) {
                    const group = buildGroup(groupId, [], GroupType.Property)
                    // Same key the full build records (computePropertySubGroup). Without it the
                    // group carried buildGroup's empty default, and removeChildren's
                    // `if (c.key.length)` then skipped its valueIndex cleanup. Copied because
                    // `key` stays in `previousKeys` as the prefix later levels extend.
                    group.key = [...key]
                    let realValue = key[key.length - 1]
                    if (property.type == PropertyType.date && typeof realValue === 'number') {
                        const range = dateBucketRange(realValue, option.stepSize, option.stepUnit)
                        realValue = range.first
                        intervalEnd = range.last
                    }
                    group.meta.propertyValues = [{ propertyId: property.id, value: realValue, valueEnd: intervalEnd, unit: option.stepUnit } as PropertyValue]
                    this.regsiterGroup(group)
                    if (key.length == 1) {
                        this.addChildGroup(this.result.root, group)
                        this.result.root.dirty = true
                    } else {
                        const parentId = this.result.valueIndex.get(key.slice(0, -1))
                        const parent = this.result.index[parentId]
                        this.addChildGroup(parent, group)
                        parent.dirty = true
                    }
                }
                const group = this.result.index[groupId]
                if (appendedFrom && !appendedFrom.has(groupId)) appendedFrom.set(groupId, group.slots.length)
                group.slots.push(slot)
                group.dirty = true
                joined?.add(groupId)
            }
        }
    }

    sortGroups(emit?: boolean) {
        if (!this.result.root) return
        for (const group of Object.values(this.result.index) as Group[]) {
            if (group.subGroupType != GroupType.Property) continue
            if (group.children.length == 0) continue
            sortGroup(group, this.state.options[group.children[0].meta.propertyValues[0].propertyId])
        }
        // Re-ordering children IS a display-order change: `order` is what the iterators compare
        // to decide which of two groups comes first, and orderedIds / start / end describe the
        // layout the scrollers draw. Every other path that moves a node does these two; without
        // them a sort-direction change left both describing the previous arrangement.
        setOrder(this.result.root)
        this.buildOrdinalRanges()
        if (emit) this.emitResult()
    }

    // Slot→display-position lookup from the last full sort, handed to orderSlots (which also
    // documents how a slot with no recorded position is placed).
    private slotPositions(): SlotPositions {
        return { posArr: this._posArr, maxSlot: this._posMaxSlot, count: this._posCount }
    }

    private saveImagesToGroup(group: Group) {
        if (this._rebuildingTree) return
        const ids = useColumnStore().instanceIds()
        for (const s of group.slots) {
            const id = ids[s]
            let set = this.result.imageToGroups.get(id)
            if (!set) { set = new Set<number>(); this.result.imageToGroups.set(id, set) }
            set.add(group.id)
        }
    }

    // Apply (or clear) the sha1 display overlay over the current tree. Non-destructive:
    // computes a PileData per final leaf that has duplicate sha1s and stores it in
    // result.pileIndex, leaving group.slots/children untouched. Called as the final step
    // of group()/custom-group mutations so it composes over property + cluster groups.
    // `only` restricts the recompute to the leaves an edit actually touched — a drag between
    // two groups changed two leaves, not the whole tree, and the full sweep is O(all slots).
    // Omit it for a full rebuild (after group() / a structural op that moved many nodes).
    applySha1Piles(only?: Iterable<Group>) {
        if (!this.state.sha1Mode) {
            if (this.result.pileIndex.size) this.result.pileIndex = new Map()
            return
        }
        const col = useColumnStore()
        const sha1s = col.sha1s()
        const ids = col.instanceIds()
        const recompute = (group: Group) => {
            // Detached (no longer the node registered under its id) or no longer a leaf:
            // it must not keep a pile entry.
            if (!group || this.result.index[group.id] !== group || group.children.length > 0) {
                if (group) this.result.pileIndex.delete(group.id)
                return
            }
            const pile = computeSha1Piles(group.slots, sha1s, ids)
            if (pile) this.result.pileIndex.set(group.id, pile)
            else this.result.pileIndex.delete(group.id)
        }
        if (only) {
            for (const group of only) recompute(group)
            return
        }
        this.result.pileIndex = new Map()
        for (const group of Object.values(this.result.index) as Group[]) recompute(group)
    }

    hasResult() {
        return this.result.root != undefined
    }

    clear(emit?: boolean) {
        this.result.clear()
        this.nav.clearSelection()
        this.clusters.clear()
        this._posArr = new Int32Array(0)
        this._posMaxSlot = 0
        if (emit) this.emitResult()
    }

    async emptyRoot(emit?: boolean) {
        this.clear()
        await this.group(new Int32Array(0), emit)
    }

    verifyState(properties: PropertyIndex) {
        const filtered = this.state.groupBy.filter(id => properties[id] && properties[id].id != deletedID)
        this.state.groupBy.length = 0
        filtered.forEach(id => this.state.groupBy.push(id))
        Object.keys(this.state.options)
            .filter(id => !properties[Number(id)] || properties[Number(id)].id == deletedID)
            .forEach(id => delete this.state.options[Number(id)])
        // Every grouped property MUST have an option object: computePropertySubGroup and
        // sortGroup dereference it unconditionally, so a persisted state missing one (or a
        // groupBy written without going through setGroupOption) crashed the whole build.
        for (const id of this.state.groupBy) {
            if (!this.state.options[id]) this.state.options[id] = buildGroupOption(id, properties)
        }
    }

    // Detach a group's children — the WHOLE subtree, not just the direct children: a
    // grandchild left registered in `result.index` is an orphan no longer reachable from the
    // tree, yet still walked by every objValues(index) sweep (updateSelection, applySha1Piles)
    // and still resolvable by getGroupIterator(id).
    removeChildren(group: Group) {
        const detach = (c: Group) => {
            c.children.forEach(detach)
            delete this.result.index[c.id]
            if (c.key.length) this.result.valueIndex.delete(c.key)
            this.result.pileIndex.delete(c.id)
            this.removeImageToGroups(c)
        }
        group.children.forEach(detach)
        group.children.length = 0
        group.subGroupType = undefined
    }

    async update(emit?: boolean): Promise<void> {
        if (!this.result.root) return
        await this.group(new Int32Array(this.result.root.slots), emit)
    }

    updateSelection(updated: Set<number>, removed: Set<number>) {
        const col = useColumnStore()

        // ── grouping diagnostics ─────────────────────────────────────────────
        if (grpDebugOn()) {
            const props = useDataStore().properties
            grpLog('4 \u00b7 group.updateSelection in', {
                updated: updated.size, removed: removed.size, groupBy: [...this.state.groupBy],
                probe: few(updated, 5).map(id => {
                    const slot = col.slotMap.get(id)
                    return {
                        id, slot,
                        groupsBefore: [...(this.result.imageToGroups.get(id) ?? [])],
                        values: this.state.groupBy.map(propId => {
                            const raw = slot !== undefined ? col.readSlot(propId, slot) : undefined
                            const parsed = valueParser[props[propId]?.type]?.(raw)
                            return {
                                propId, type: props[propId]?.type, raw,
                                rawIsArray: Array.isArray(raw),
                                rawLength: Array.isArray(raw) ? raw.length : undefined,
                                parsed,
                                emptyArray: Array.isArray(parsed) && parsed.length === 0,
                            }
                        }),
                    }
                }),
            })
        }
        // Pile overlay is recomputed at the end from the updated leaves; clear it up front
        // so the dirty-leaf logic below sees plain leaves (children.length === 0).
        this.result.pileIndex = new Map()

        const oldGroupIds = new Map<number, number[]>()
        for (const id of updated) {
            const set = this.result.imageToGroups.get(id)
            oldGroupIds.set(id, set ? [...set] : [])
        }

        const dirtyGroupIds = new Set<number>()
        // A removal only changes what is drawn if the instance was actually in the tree.
        // FilterManager rejects every dirty instance that fails the filter, including ones
        // that were already filtered out, and dropping those changes nothing.
        let removedFromTree = false
        for (const instanceId of removed) {
            const groups = this.result.imageToGroups.get(instanceId)
            if (!groups?.size) continue
            removedFromTree = true
            groups.forEach(g => dirtyGroupIds.add(g))
        }
        for (const instanceId of updated) {
            this.result.imageToGroups.get(instanceId)?.forEach(g => dirtyGroupIds.add(g))
        }
        // imageToGroups only holds the DEEPEST property level (plus clusters), so with nested
        // grouping the intermediate parents never showed up here: their stale slots were never
        // dropped while addInstanceToGroups re-added the slot at every level, leaving the image
        // counted in both its old and new first-level group. Walk up and mark the whole chain.
        for (const gid of Array.from(dirtyGroupIds)) {
            let parent = this.result.index[gid]?.parent
            while (parent && !dirtyGroupIds.has(parent.id)) {
                dirtyGroupIds.add(parent.id)
                parent = parent.parent
            }
        }
        dirtyGroupIds.add(0)

        if (grpDebugOn()) {
            grpLog('5 \u00b7 dirty groups', few(dirtyGroupIds, 30).map(gid => {
                const g = this.result.index[gid]
                return g
                    ? { id: gid, type: g.type, value: g.meta?.propertyValues?.[0]?.value, slots: g.slots.length }
                    : { id: gid, missingFromIndex: true }
            }))
        }

        const ids = col.instanceIds()
        for (const groupId of dirtyGroupIds) {
            const group = this.result.index[groupId]
            if (!group) continue
            if (group.type == GroupType.Cluster) continue
            group.dirty = true
            // Root holds every present slot; when grouping is active it is not a leaf, so
            // addUpdatedToGroups only re-adds the slots that are new to the tree. A value change
            // doesn't remove the image (it just moves between leaves), so root must KEEP updated
            // slots — only drop removed ones. Otherwise root drains to 0 and the whole tree is
            // deleted.
            const isGroupedRoot = group.id === 0 && this.state.groupBy.length > 0
            // With nothing removed the grouped root keeps every slot, so the filter is a copy of
            // the whole collection — skip it and leave the array alone.
            if (isGroupedRoot && removed.size == 0) continue
            group.slots = group.slots.filter(s => {
                const id = ids[s]
                if (removed.has(id)) return false
                return isGroupedRoot ? true : !updated.has(id)
            })
        }

        const updatedSlots: number[] = []
        // The slots that were in no group before this update. Every instance the tree holds is
        // in some leaf, so an empty membership means the instance is not in the tree yet: it was
        // just imported, or a lifted filter brought it back. That is exactly the set the grouped
        // root is missing, and testing it costs nothing — oldGroupIds was read above for every
        // updated id (root.slots is the whole collection, so no per-slot scan of it is possible).
        const newToTree = new Set<number>()
        for (const id of updated) {
            const s = col.slotMap.get(id)
            if (s === undefined) continue
            updatedSlots.push(s)
            if (!oldGroupIds.get(id)?.length) newToTree.add(s)
        }
        const joinedGroupIds = new Set<number>()
        // Where each group's appended slots start, so the re-order below merges instead of
        // re-sorting. A group missing from the map gained nothing and is still in order.
        const appendedFrom = new Map<number, number>()
        this.addUpdatedToGroups(new Int32Array(updatedSlots), joinedGroupIds, appendedFrom, newToTree)

        for (const group of objValues(this.result.index)) {
            // NEVER unregister the root (id 0): result.root keeps pointing at it, so dropping
            // it from the index left hasResult() true while every iterator resolved to
            // undefined, and no later updateSelection could repopulate it.
            // Cluster groups are skipped: their slots are refilled by the resync below, so an
            // empty one here is only a pile waiting for its bucket, not a group to drop.
            if (group.type == GroupType.Cluster) continue
            if (group.id !== 0 && group.slots.length == 0) delete this.result.index[group.id]
            const oldLen = group.children.length
            group.children = group.children.filter(g => g.type == GroupType.Cluster || g.slots.length > 0)
            if (group.children.length < oldLen) {
                // GroupIterator addresses siblings by parentIdx, so the positions have to follow
                // the array whenever a child is dropped.
                for (let i = 0; i < group.children.length; i++) group.children[i].parentIdx = i
                group.dirty = true
            }
        }

        // Incrementally maintain imageToGroups instead of rebuilding the whole map (O(n)).
        // Drop the changed instances' non-cluster (property-leaf) memberships; cluster
        // memberships are static (clusters don't depend on property values) so they are kept.
        // Dirty leaves below re-add the up-to-date memberships.
        const dropMembership = (id: number) => {
            const set = this.result.imageToGroups.get(id)
            if (!set) return
            for (const gid of set) {
                const g = this.result.index[gid]
                if (!g || g.type != GroupType.Cluster) set.delete(gid)
            }
            if (set.size == 0) this.result.imageToGroups.delete(id)
        }
        for (const id of removed) dropMembership(id)
        for (const id of updated) dropMembership(id)

        const positions = this.slotPositions()
        for (const group of objValues(this.result.index)) {
            if (!group.dirty) continue
            if (group.subGroupType == GroupType.Property) {
                const propChild = group.children.find(c => c.meta.propertyValues?.[0])
                if (propChild) {
                    const option = this.state.options[propChild.meta.propertyValues[0].propertyId]
                    sortGroup(group, option)
                }
            }
            if (group.type != GroupType.Cluster) {
                // The filter above is order preserving and addUpdatedToGroups only appends, so
                // the slots are an ordered prefix plus a short tail: merge the tail in rather
                // than re-sorting the array. The grouped root gains nothing here (its updated
                // slots are kept, not re-added) so it is left untouched.
                const cut = appendedFrom.get(group.id as number)
                orderSlots(group.slots, cut === undefined ? group.slots.length : cut, positions)
            }
            // Re-add reverse-index entries for dirty leaves only (property leaves, or root when
            // ungrouped). sha1 sub-groups were removed at the top of updateSelection, so
            // children.length === 0 reliably identifies a leaf here. A clustered bucket has its
            // piles and is skipped; one whose piles are currently detached is a leaf and is
            // written, and the resync that grafts them back drops the entries again.
            if (group.children.length == 0 && group.type != GroupType.Cluster) {
                this.saveImagesToGroup(group)
            }
            group.dirty = false
        }

        // Refill the piles of every bucket this edit touched. `dirtyGroupIds` holds the groups
        // the changed instances were in; their current groups are added too, because a value
        // write can move an instance INTO a bucket as well as out of one — and with a
        // multi-value tag grouping it can move in several at once. Done before ordering so the
        // display reflects final membership.
        for (const id of updated) {
            this.result.imageToGroups.get(id)?.forEach(g => dirtyGroupIds.add(g))
        }
        // imageToGroups names leaves, and a clustered bucket is not one: its children are the
        // piles (ClusterOverlay.resync drops the bucket's entries when it grafts them). So an
        // image coming back to such a bucket — a cleared value, an undo, a bucket returning from
        // behind a filter — is named by no old membership and would never mark it dirty: the slot
        // would land in bucket.slots, raising its count, while the piles were left untouched and
        // the image was drawn nowhere. The groups the slots actually joined close that gap.
        for (const gid of joinedGroupIds) dirtyGroupIds.add(gid)
        // The instances this update is about, so the overlay can report where they landed.
        grpSetFocus(updated)
        const clusterChanged = this.clusters.resyncDirty(dirtyGroupIds)

        setOrder(this.result.root)
        this.applySha1Piles()
        this.buildOrdinalRanges()

        // Any instance dropped from the tree counts, however few: `removed` and `updated` are
        // disjoint (FilterManager splits the re-filtered slots into valid/reject), so the
        // membership-diff loop below only walks `updated` and can never observe a removal.
        // The old `removed.size > 1` therefore left a single removed instance unemitted and
        // the scrollers kept drawing it until an unrelated change bumped the version.
        let structureChanged = removedFromTree || clusterChanged
        if (!structureChanged) {
            for (const id of updated) {
                const before = oldGroupIds.get(id) ?? []
                const afterSet = this.result.imageToGroups.get(id)
                if (before.length !== (afterSet?.size ?? 0) || before.some(g => !afterSet?.has(g))) {
                    structureChanged = true
                    break
                }
            }
        }
        if (grpDebugOn()) {
            grpLog('7 \u00b7 group.updateSelection out', {
                structureChanged, emitted: structureChanged,
                probe: few(updated, 5).map(id => {
                    const slot = col.slotMap.get(id)
                    const stillHolding = few(dirtyGroupIds, 60)
                        .filter(gid => slot !== undefined && this.result.index[gid]?.slots.includes(slot))
                    return {
                        id, slot,
                        groupsBefore: oldGroupIds.get(id) ?? [],
                        groupsAfter: [...(this.result.imageToGroups.get(id) ?? [])],
                        groupsStillHoldingTheSlot: stillHolding,
                    }
                }),
            })
        }
        if (structureChanged) this.emitResult()
        return this.result
    }

    setGroupOption(propertyId: number, option?: GroupOption) {
        const data = useDataStore()
        if (!this.state.options[propertyId]) {
            this.state.options[propertyId] = buildGroupOption(propertyId, data.properties)
        }
        if (option) Object.assign(this.state.options[propertyId], option)
        if (!this.state.groupBy.includes(propertyId)) {
            this.state.groupBy.push(propertyId)
            // Appended, so it is the new leaf: the clusters move down into each bucket's "no
            // value" child on the rebuild instead of being cleared (cluster_view_goals.md).
            this.clusters.deferDescent()
        }
        this.onStateChange.emit()
    }

    delGroupOption(propertyId: number) {
        const index = this.state.groupBy.indexOf(propertyId)
        if (index < 0) return
        this.state.groupBy.splice(index, 1)
        this.clusters.clear()
        this.onStateChange.emit()
    }

    // ── Structural cluster ops — thin facades delegating to ClusterManager, so external
    // callers keep using `manager.split(...)` etc. until they migrate to `collection`/`clusters`.
    addCustomGroups(targetGroupId: number, groups: Group[], emit?: boolean) {
        this.clusters.addCustomGroups(targetGroupId, groups, emit)
    }

    moveImagesToGroup(fromGroupId: number, toGroupId: number, instanceIds: number[], emit = true) {
        this.clusters.moveImagesToGroup(fromGroupId, toGroupId, instanceIds, emit)
    }

    renameGroup(groupId: number, name: string, emit = true) {
        this.clusters.renameGroup(groupId, name, emit)
    }

    delCustomGroups(targetGroupId: number, emit?: boolean) {
        this.clusters.delCustomGroups(targetGroupId, emit)
    }

    clearCustomGroups(emit?: boolean) {
        this.clusters.clearCustomGroups(emit)
    }

    // Cluster a group: the whole operation (run the action + graft the result) belongs to the
    // ClusterManager — callers only name the target.
    cluster(targetGroupId: number, req: ClusterRequest) {
        return this.clusters.cluster(targetGroupId, req)
    }

    isClustering(groupId: number) {
        return this.clusters.isClustering(groupId)
    }

    // Why the last clustering run on this group failed, for the button that started it.
    clusterError(groupId: number) {
        return this.clusters.clusterError(groupId)
    }

    split(groupId: number, groups: Group[], emit = true) {
        this.clusters.split(groupId, groups, emit)
    }

    merge(groupIds: number[], emit = true) {
        this.clusters.merge(groupIds, emit)
    }

    deletePile(groupId: number, emit = true) {
        this.clusters.deletePile(groupId, emit)
    }

    setSha1Mode(value: boolean, emit?: boolean) {
        if (this.state.sha1Mode == value) return
        this.state.sha1Mode = value
        this.applySha1Piles()
        this.buildOrdinalRanges()
        this.onStateChange.emit()
        if (emit) this.emitResult()
    }

    // ── Open/close — thin facades delegating to GroupNavigator ───────────────
    toggleGroup(groupId, emit?: boolean) {
        this.nav.toggleGroup(groupId, emit)
    }

    openGroup(groupId, emit?: boolean) {
        this.nav.openGroup(groupId, emit)
    }

    closeGroup(groupId, emit?: boolean) {
        this.nav.closeGroup(groupId, emit)
    }


    getGroupIterator(groupId?: number, options?: GroupIteratorOptions) {
        return this.result.getGroupIterator(groupId, options)
    }

    getImageIterator(groupId?: number, imageIdx?: number, options?: GroupIteratorOptions) {
        return this.result.getImageIterator(groupId, imageIdx, options)
    }

    findImageIterator(groupId: number, imageId: number) {
        return this.result.findImageIterator(groupId, imageId)
    }

    setChildGroup(parent: Group, groups: Group[]) {
        this.removeChildren(parent)
        for (const group of groups) {
            group.parentIdx = parent.children.length
            group.parent = parent
            group.depth = parent.depth + 1
            parent.children.push(group)
            this.regsiterGroup(group)
            this.saveImagesToGroup(group)
        }
        // Same rule as groupOps: undefined when the children disagree. Taking children[0].type
        // could label a mixed level "Property", and sortGroups then dereferenced
        // meta.propertyValues[0] on a Cluster child.
        refreshSubGroupType(parent)
    }

    private addChildGroup(parent: Group, group: Group) {
        group.parentIdx = parent.children.length
        group.parent = parent
        group.depth = parent.depth + 1
        parent.children.push(group)
        this.regsiterGroup(group)
        this.saveImagesToGroup(group)
        refreshSubGroupType(parent)
        this.removeImageToGroups(parent)
    }

    regsiterGroup(group: Group) {
        this.result.index[group.id] = group
        // Every group gets the active search's scores, so each image can show its own
        // (Image.vue reads group.scores). A group with scores of its own (a cluster) keeps them.
        if (!group.scores) {
            const scores = this.scoreSource()
            if (scores) group.scores = scores
        }
    }

    private computePropertySubGroup(group: Group, groupBy: number[], properties: PropertyIndex, tags: TagIndex) {
        const col = useColumnStore()
        const property = properties[groupBy[0]]
        const option = this.state.options[property.id]
        const isDateType = property.type === PropertyType.date
        const isTagType = isTag(property.type)

        // Direct buffer access: avoids readSlot() function call + switch dispatch per slot.
        const rawBuf = col.getRawBuffer(property.id)
        // Cache parser outside the loop — avoids per-slot hash lookup on valueParser object
        const parser = !isDateType && !isTagType ? valueParser[property.type] : null

        // Build tagWithParents once per property (hoisted outside slot loop)
        const tagWithParents: { [id: number]: Set<number> } = {}
        if (isTagType && property.tags) {
            for (const tag of objValues(property.tags)) {
                tagWithParents[tag.id] = new Set(tag.allParents)
                tagWithParents[tag.id].add(tag.id)
            }
        }

        group.subGroupType = GroupType.Property

        // Pre-bucket: Map<keyValue, slot[]>.
        // Single Map.get per slot (no separate has + get).
        // No [value] array allocation per slot for non-tag case.
        const buckets = new Map<any, number[]>()
        const bucketMeta = new Map<any, { displayVal: any, intervalEnd?: Date }>()

        for (const s of group.slots) {
            if (isDateType) {
                const raw = rawBuf?.[s] as Date | number | null
                const bk = raw ? dateBucketKey(raw instanceof Date ? raw : new Date(raw as number), option.stepSize, option.stepUnit) : undefined
                if (bk !== undefined && !bucketMeta.has(bk)) {
                    const range = dateBucketRange(bk, option.stepSize, option.stepUnit)
                    bucketMeta.set(bk, { displayVal: range.first, intervalEnd: range.last })
                }
                let arr = buckets.get(bk); if (!arr) { arr = []; buckets.set(bk, arr) }; arr.push(s)
            } else if (isTagType) {
                const tagIds = rawBuf?.[s] as number[] | null
                if (!Array.isArray(tagIds) || !tagIds.length) {
                    let arr = buckets.get(undefined); if (!arr) { arr = []; buckets.set(undefined, arr) }; arr.push(s)
                    continue
                }
                // Dedup expanded parents within this slot without allocating a Set: while
                // slot s is being processed, any bucket we push s into has s as its last
                // element until we move on, so a last-element check collapses the duplicate
                // parents shared across the slot's tags.
                let placed = false
                for (const v of tagIds) {
                    if (!v) continue
                    // An id the property's tag registry does not name is never a group of its
                    // own: a tag delete tombstones the tag while the session's column still
                    // holds the id, and a bucket keyed on it is a group for a tag that no longer
                    // exists — it has no label to draw and sortGroupByProperty threw on it,
                    // passing the raw id to the tag sort parser.
                    const parents = tagWithParents[v]
                    if (!parents) continue
                    for (const p of parents) {
                        let arr = buckets.get(p); if (!arr) { arr = []; buckets.set(p, arr) }
                        if (arr.length === 0 || arr[arr.length - 1] !== s) arr.push(s)
                        placed = true
                    }
                }
                // Every id on the slot was unregistered, so it has no value to group by and
                // belongs in the empty bucket — where a slot with no tags at all goes. Skipping
                // the ids alone left the slot in NO bucket: it vanished from the tree on the
                // next full regroup while the incremental path still showed it.
                if (!placed) {
                    let arr = buckets.get(undefined); if (!arr) { arr = []; buckets.set(undefined, arr) }; arr.push(s)
                }
            } else {
                // Direct buffer read avoids readSlot switch dispatch; cached parser handles type normalization.
                // Bool columns use 255 as null marker in the Uint8Array — normalize before parser.
                let raw = rawBuf?.[s]
                if (property.type === PropertyType.checkbox && raw === 255) raw = null
                const kv = parser!(raw)
                let arr = buckets.get(kv); if (!arr) { arr = []; buckets.set(kv, arr) }; arr.push(s)
            }
        }

        // Build groups from buckets — one group.key.concat per unique bucket value, not per slot.
        const subGroups: Group[] = []
        for (const [kv, slots] of buckets) {
            const key = group.key.concat([kv])
            const groupId = this.result.valueIndex.get(key)
            if (!this.result.index[groupId]) {
                const meta = bucketMeta.get(kv)
                const displayVal = meta !== undefined ? meta.displayVal : kv
                const intervalEnd = meta?.intervalEnd
                const newGroup = buildGroup(groupId, [], GroupType.Property)
                newGroup.meta.propertyValues = [{ propertyId: property.id, value: displayVal, valueEnd: intervalEnd, unit: option.stepUnit } as PropertyValue]
                newGroup.key = key
                this.regsiterGroup(newGroup)
                subGroups.push(newGroup)
            }
            const target = this.result.index[groupId]
            for (const s of slots) target.slots.push(s)
        }

        this.setChildGroup(group, subGroups)
        if (groupBy.length > 1) {
            for (const c of subGroups) {
                this.computePropertySubGroup(c, groupBy.slice(1), properties, tags)
            }
        } else {
            // Deepest level: these are the true leaf groups. Track for imageToGroups sweep.
            for (const g of subGroups) this._leafGroups.push(g)
        }
        sortGroup(group, option)
    }

    private removeImageToGroups(group: Group) {
        const ids = useColumnStore().instanceIds()
        for (const s of group.slots) {
            const id = ids[s]
            const set = this.result.imageToGroups.get(id)
            if (!set) continue
            set.delete(group.id)
            // An instance in no group leaves no entry behind: readers treat an absent entry
            // and an empty Set alike ("not in the tree"), and keeping the empty one grew the
            // map by one dead entry per instance that ever left the tree.
            if (set.size == 0) this.result.imageToGroups.delete(id)
        }
    }

    // ── Selection — thin facades delegating to GroupNavigator ────────────────

    setSelectionNamespace(ns: string) { this.nav.setSelectionNamespace(ns) }
    clearSelection() { this.nav.clearSelection() }
    clearLastSelected() { this.nav.clearLastSelected() }

    selectImageIterator(iterator: ImageIterator, shift = false) { this.nav.selectImageIterator(iterator, shift) }
    unselectImageIterator(iterator: ImageIterator) { this.nav.unselectImageIterator(iterator) }
    toggleImageIterator(iterator: ImageIterator, shift = false) { this.nav.toggleImageIterator(iterator, shift) }
    toggleAll() { this.nav.toggleAll() }

    unselectImage(imageId: number) { this.nav.unselectImage(imageId) }
    selectImage(imageId: number)   { this.nav.selectImage(imageId) }
    selectImages(imageIds: number[]) { this.nav.selectImages(imageIds) }
    unselectImages(imageIds: number[]) { this.nav.unselectImages(imageIds) }

    isGroupSelected(group: Group) { return this.nav.isGroupSelected(group) }

    selectGroup(group: Group) { this.nav.selectGroup(group) }
    unselectGroup(group: Group) { this.nav.unselectGroup(group) }
    selectGroupIterator(iterator: GroupIterator, shift = false) { this.nav.selectGroupIterator(iterator, shift) }
    unselectGroupIterator(iterator: GroupIterator) { this.nav.unselectGroupIterator(iterator) }
    toggleGroupIterator(iterator: GroupIterator, shift = false) { this.nav.toggleGroupIterator(iterator, shift) }
}
