/**
 * GroupManager
 * Builds a Group tree from an Int32Array of sorted slot indices (pre-sorted by SortManager).
 *
 * Key invariants:
 *  - Group.slots: number[]         — column-store slot indices
 *  - GroupTree.orderedIds           — instance IDs in DFS display order (rebuilt after each structural change)
 *  - GroupValueIndex is persistent  — group IDs are stable across rebuilds (view state preserved)
 *  - imageToGroups: Map<instanceId, Set<leafGroupId>>  — O(1) lookup and delete
 *  - computePropertySubGroup pre-buckets slots before key construction — zero per-slot spread allocations
 *  - Date bucketing uses epoch-ms integer arithmetic — zero Date allocations in scan loop
 */

import { deletedID, PropertyIndex, PropertyValue, TagIndex } from "@/data/models";
import { Ref, reactive } from "vue";
import { PropertyType } from "@/data/models";
import { EventEmitter, isTag, objValues } from "@/utils/utils";
import { useDataStore } from "@/data/dataStore";
import { useColumnStore } from "@/data/columnStore";
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
import { ClusterManager } from "./group/ClusterManager";

// ── Barrel re-exports — keep `@/core/GroupManager` as the public entry point ─
export { GroupType, GroupSortType } from "./group/types";
export type {
    GroupState, Group, GroupView, ClusterParam, GroupMetaData,
    GroupIndex, GroupTree, GroupOption, SelectedImages,
} from "./group/types";
export { buildGroup, buildGroupOption, createGroupState } from "./group/builders";
export { GroupIterator, ImageIterator } from "./group/GroupIterator";
export type { GroupIteratorOptions } from "./group/GroupIterator";

export class GroupManager implements ClusterOpsHost {
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
    // When true, saveImagesToGroup is a no-op — avoids redundant Map writes during full rebuild.
    private _rebuildingTree = false
    // Leaf groups collected during computePropertySubGroup — avoids Object.values() in post-loop.
    private _leafGroups: Group[] = []
    onStateChange: EventEmitter

    // Result-change signal + legacy event live on GroupResult now; expose delegating getters
    // so existing callers (`manager.version.value`, `manager.onResultChange`) keep working.
    get version(): Ref<number> { return this.result.version }
    get onResultChange(): EventEmitter { return this.result.onResultChange }

    // Selection lives in columnStore, keyed by namespace (note §5, step 2), and is
    // driven by GroupNavigator (this.nav). Delegating getter kept for callers reading
    // `manager.selectionNamespace`.
    get selectionNamespace(): string { return this.nav.selectionNamespace }

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
        console.time('Group')
        const data = useDataStore()
        this.invalidateIterators()

        // Build slot→position as typed array — O(1) access vs plain-object hash lookup.
        // Single pass to find maxSlot so we can pre-allocate the exact typed array size.
        let maxSlot = 0
        for (let i = 0; i < slots.length; i++) if (slots[i] > maxSlot) maxSlot = slots[i]
        this._posArr = new Int32Array(maxSlot + 1)
        for (let i = 0; i < slots.length; i++) this._posArr[slots[i]] = i
        this._posMaxSlot = maxSlot

        const lastIndex = this.result.index ?? {}
        this.result.root = buildRoot(Array.from(slots))
        this.result.index = {}
        this.result.imageToGroups = new Map()
        this.result.pileIndex = new Map()
        const lastCustom = this.clusters.customGroups ?? {}
        this.clusters.customGroups = {}
        this._leafGroups = []
        this.regsiterGroup(this.result.root)

        // Suppress saveImagesToGroup during tree construction — we do one clean sweep below.
        this._rebuildingTree = true
        if (this.state.groupBy.length > 0) {
            this.computePropertySubGroup(this.result.root, this.state.groupBy, data.properties, data.tags)
        }
        this._rebuildingTree = false

        // Single imageToGroups sweep using tracked leaf groups (avoids Object.values allocation).
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

        // Re-graft the previous custom/cluster groups (fixed-point replay now owned by ClusterManager).
        this.clusters.reapplyAfter(lastCustom)

        this.applySha1Piles()

        for (const id of Object.keys(this.result.index)) {
            const group = this.result.index[id]
            if (lastIndex[id]) group.view = lastIndex[id].view
        }

        setOrder(this.result.root)
        this.buildOrdinalRanges()
        console.timeEnd('Group')
        if (emit) this.emitResult()
        return this.result
    }

    // Delegates to GroupResult (owns orderedIds / display order).
    buildOrdinalRanges(): void {
        this.result.buildOrdinalRanges()
    }

    private addUpdatedToGroups(slots: Int32Array) {
        if (!this.result.root) {
            this.group(slots)
            return
        }

        const data = useDataStore()
        this.invalidateIterators()

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
                this.addInstanceToGroups(slots[i], data.properties, data.tags, tagParentsByProp)
            }
        } else {
            for (let i = 0; i < slots.length; i++) {
                this.result.root.slots.push(slots[i])
            }
            this.result.root.dirty = true
        }
        // Slot re-sort, imageToGroups maintenance, and setOrder are done by the caller
        // (updateSelection) over the dirty subset only — no full O(n) sweep here.
    }

    addInstanceToGroups(slot: number, properties: PropertyIndex, tags: TagIndex, tagParentsByProp: { [propId: number]: { [id: number]: Set<number> } }) {
        const col = useColumnStore()
        const keys = []
        let previousKeys = []

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
                const withParents = new Set<any>()
                for (const v of values) {
                    if (!v) continue
                    const parents = tagWithParents[v] ?? [v]
                    for (const p of parents) withParents.add(p)
                }
                values = Array.from(withParents)
            }

            if (previousKeys.length == 0) {
                keys.push(...values.map(v => [v]))
                previousKeys = values.map(v => [v])
            } else {
                const newKeys = []
                for (const prevK of previousKeys) {
                    for (const val of values) newKeys.push([...prevK, val])
                }
                keys.push(...newKeys)
                previousKeys = newKeys
            }

            for (const key of previousKeys) {
                const groupId = this.result.valueIndex.get(key)
                if (!this.result.index[groupId]) {
                    const group = buildGroup(groupId, [], GroupType.Property)
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
                group.slots.push(slot)
                group.dirty = true
            }
        }
    }

    sortGroups(emit?: boolean) {
        this.invalidateIterators()
        for (const group of Object.values(this.result.index) as Group[]) {
            if (group.subGroupType != GroupType.Property) continue
            if (group.children.length == 0) continue
            sortGroup(group, this.state.options[group.children[0].meta.propertyValues[0].propertyId])
        }
        if (emit) this.emitResult()
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
    applySha1Piles() {
        this.invalidateIterators()
        this.result.pileIndex = new Map()
        if (!this.state.sha1Mode) return
        const col = useColumnStore()
        const sha1s = col.sha1s()
        const ids = col.instanceIds()
        for (const group of Object.values(this.result.index) as Group[]) {
            if (group.children.length > 0) continue
            const pile = computeSha1Piles(group.slots, sha1s, ids)
            if (pile) this.result.pileIndex.set(group.id, pile)
        }
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

    async setAsRoot(group: Group, emit?: boolean) {
        await this.emptyRoot()
        const copy = { ...group }
        copy.slots = [...group.slots]
        delete copy.id
        Object.assign(this.result.root, copy)
        this.applySha1Piles()
        this.buildOrdinalRanges()
        if (emit) this.emitResult()
    }

    verifyState(properties: PropertyIndex) {
        const filtered = this.state.groupBy.filter(id => properties[id] && properties[id].id != deletedID)
        this.state.groupBy.length = 0
        filtered.forEach(id => this.state.groupBy.push(id))
        Object.keys(this.state.options)
            .filter(id => !properties[Number(id)] || properties[Number(id)].id == deletedID)
            .forEach(id => delete this.state.options[Number(id)])
    }

    invalidateIterators() {
        this.result.invalidateIterators()
    }

    removeChildren(group: Group) {
        group.children.forEach(c => {
            delete this.result.index[c.id]
            if (c.key.length) this.result.valueIndex.delete(c.key)
            this.removeImageToGroups(c)
        })
        group.children.length = 0
        group.subGroupType = undefined
    }

    async update(emit?: boolean): Promise<void> {
        this.invalidateIterators()
        if (!this.result.root) return
        await this.group(new Int32Array(this.result.root.slots), emit)
    }

    updateSelection(updated: Set<number>, removed: Set<number>) {
        const col = useColumnStore()
        this.invalidateIterators()
        // Pile overlay is recomputed at the end from the updated leaves; clear it up front
        // so the dirty-leaf logic below sees plain leaves (children.length === 0).
        this.result.pileIndex = new Map()

        const oldGroupIds = new Map<number, number[]>()
        for (const id of updated) {
            const set = this.result.imageToGroups.get(id)
            oldGroupIds.set(id, set ? [...set] : [])
        }

        const dirtyGroupIds = new Set<number>()
        for (const instanceId of removed) {
            this.result.imageToGroups.get(instanceId)?.forEach(g => dirtyGroupIds.add(g))
        }
        for (const instanceId of updated) {
            this.result.imageToGroups.get(instanceId)?.forEach(g => dirtyGroupIds.add(g))
        }
        dirtyGroupIds.add(0)

        const ids = col.instanceIds()
        for (const groupId of dirtyGroupIds) {
            const group = this.result.index[groupId]
            if (!group) continue
            if (group.type == GroupType.Cluster) continue
            group.dirty = true
            // Root holds every present slot; when grouping is active it is not a leaf, so
            // addUpdatedToGroups won't re-add value-updated slots to it. A value change doesn't
            // remove the image (it just moves between leaves), so root must KEEP updated slots —
            // only drop removed ones. Otherwise root drains to 0 and the whole tree is deleted.
            const isGroupedRoot = group.id === 0 && this.state.groupBy.length > 0
            group.slots = group.slots.filter(s => {
                const id = ids[s]
                if (removed.has(id)) return false
                return isGroupedRoot ? true : !updated.has(id)
            })
        }

        const updatedSlots: number[] = []
        for (const id of updated) {
            const s = col.slotMap.get(id)
            if (s !== undefined) updatedSlots.push(s)
        }
        this.addUpdatedToGroups(new Int32Array(updatedSlots))

        for (const group of objValues(this.result.index)) {
            if (group.slots.length == 0) delete this.result.index[group.id]
            const oldLen = group.children.length
            group.children = group.children.filter(g => g.slots.length > 0)
            if (group.children.length < oldLen) group.dirty = true
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
                group.slots.sort((a, b) => (a <= this._posMaxSlot ? this._posArr[a] : 0) - (b <= this._posMaxSlot ? this._posArr[b] : 0))
            }
            // Re-add reverse-index entries for dirty leaves only (property leaves, or root when
            // ungrouped). sha1 sub-groups were removed at the top of updateSelection, so
            // children.length === 0 reliably identifies a leaf here.
            if (group.children.length == 0 && group.type != GroupType.Cluster) {
                this.saveImagesToGroup(group)
            }
            group.dirty = false
        }

        // Reconcile the cluster overlay against the refreshed property tree: images that left a
        // sub-clustered group are pulled from their cluster, and images newly in the group join
        // its "New" leftover pile. Done before ordering so the display reflects final membership.
        const clusterChanged = this.clusters.reconcile()

        setOrder(this.result.root)
        this.applySha1Piles()
        this.buildOrdinalRanges()

        let structureChanged = removed.size > 1 || clusterChanged
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
            this.clusters.clear()
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

    split(groupId: number, groups: Group[], mode: 'replace' | 'children' = 'replace', emit = true) {
        this.clusters.split(groupId, groups, mode, emit)
    }

    merge(groupIds: number[], emit = true) {
        this.clusters.merge(groupIds, emit)
    }

    delete(groupId: number, emit = true) {
        this.clusters.delete(groupId, emit)
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
        parent.subGroupType = parent.children.length ? groups[0].type : undefined
    }

    private addChildGroup(parent: Group, group: Group) {
        group.parentIdx = parent.children.length
        group.parent = parent
        group.depth = parent.depth + 1
        parent.children.push(group)
        this.regsiterGroup(group)
        this.saveImagesToGroup(group)
        parent.subGroupType = parent.children.length ? group.type : undefined
        this.removeImageToGroups(parent)
    }

    regsiterGroup(group: Group) {
        this.result.index[group.id] = group
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
        let hasTagMeta = false
        if (isTagType && property.tags) {
            for (const tag of objValues(property.tags)) {
                tagWithParents[tag.id] = new Set(tag.allParents)
                tagWithParents[tag.id].add(tag.id)
            }
            hasTagMeta = Object.keys(tagWithParents).length > 0
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
                for (const v of tagIds) {
                    if (!v) continue
                    const parents = hasTagMeta ? tagWithParents[v] : [v]
                    if (!parents) continue
                    for (const p of parents) {
                        let arr = buckets.get(p); if (!arr) { arr = []; buckets.set(p, arr) }
                        if (arr.length === 0 || arr[arr.length - 1] !== s) arr.push(s)
                    }
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
            this.result.imageToGroups.get(ids[s])?.delete(group.id)
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

    propagateUnselect(group: Group) { this.nav.propagateUnselect(group) }
    propagateSelect(group: Group) { this.nav.propagateSelect(group) }

    selectGroup(group: Group) { this.nav.selectGroup(group) }
    unselectGroup(group: Group) { this.nav.unselectGroup(group) }
    selectGroupIterator(iterator: GroupIterator, shift = false) { this.nav.selectGroupIterator(iterator, shift) }
    unselectGroupIterator(iterator: GroupIterator) { this.nav.unselectGroupIterator(iterator) }
    toggleGroupIterator(iterator: GroupIterator, shift = false) { this.nav.toggleGroupIterator(iterator, shift) }
}
