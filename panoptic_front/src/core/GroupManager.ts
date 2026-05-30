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

import { deletedID, DateUnit, DateUnitFactor, FolderIndex, GroupScoreList, PropertyID, PropertyIndex, PropertyValue, Score, ScoreList, TagIndex } from "@/data/models";
import { Ref, reactive, shallowRef, triggerRef } from "vue";
import { SortDirection, SortOption, sortParser } from "./SortManager";
import { PropertyType } from "@/data/models";
import { EventEmitter, isTag, objValues } from "@/utils/utils";
import { useDataStore } from "@/data/dataStore";
import { useColumnStore } from "@/data/columnStore";

export enum GroupType {
    All = 'all',
    Selection = 'selection',
    Property = 'property',
    Cluster = 'cluster',
    Sha1 = 'sha1'
}

export interface GroupState {
    groupBy: number[],
    options: { [groupId: number]: GroupOption },
    sha1Mode: boolean
}

export interface Group {
    id: number
    key: any[]
    name?: string
    slots: number[]
    type: GroupType
    subGroupType?: GroupType
    dirty?: boolean

    parent?: Group
    parentIdx?: number
    children: Group[]
    depth: number
    order: number

    // Offsets into GroupTree.orderedIds — set by buildOrdinalRanges() after each rebuild.
    start: number
    end: number

    score?: Score
    scores?: GroupScoreList

    view: GroupView
    meta: GroupMetaData
    isSha1Group?: boolean
}

export interface GroupView {
    selected: boolean
    closed: boolean
}

export interface GroupMetaData {
    propertyValues?: PropertyValue[]
    score?: number
}

export interface GroupIndex { [key: string]: Group }

export interface GroupTree {
    root: Group
    index: GroupIndex
    imageToGroups: Map<number, Set<number>>  // instanceId → Set<leafGroupId>
    valueIndex: GroupValueIndex               // persistent across rebuilds — stable group IDs
    orderedIds: Int32Array                    // instance IDs in DFS display order
    cacheStale: boolean
}

export enum GroupSortType {
    Size,
    Property
}

export interface GroupOption extends SortOption {
    type?: GroupSortType
    stepSize?: number
    stepUnit?: DateUnit
}

export type SelectedImages = { [imageId: number]: boolean }

export function buildGroup(id: string | number, slots: number[], type: GroupType = GroupType.All): Group {
    return {
        id,
        key: [],
        slots,
        type,
        children: [],
        depth: 0,
        order: -1,
        start: 0,
        end: 0,
        meta: { propertyValues: [] },
        view: { closed: false, selected: false }
    } as Group
}

function buildRoot(slots: number[]): Group {
    return buildGroup(0, slots)
}

export function buildGroupOption(propertyId: number, properties: PropertyIndex): GroupOption {
    const res: GroupOption = { direction: SortDirection.Ascending, type: GroupSortType.Property }
    const property = properties[propertyId]
    if (property.type == PropertyType.date) res.stepUnit = DateUnit.Day
    return res
}

const valueParser: { [type in PropertyType]?: any } = {
    [PropertyType.checkbox]: (x?: boolean) => { if (!x) return false; return true },
    [PropertyType.color]:    (x?: number)  => { if (isNaN(x)) return undefined; return x },
    [PropertyType.date]:     (x?: Date)    => { if (!x) return undefined; return x },
    [PropertyType.number]:   (x?: number)  => { if (x == undefined) return undefined; return x },
    [PropertyType.path]:     (x?: string)  => { if (!x) return undefined; return x },
    [PropertyType.string]:   (x?: string)  => { if (!x) return undefined; return x },
    [PropertyType.url]:      (x?: string)  => { if (!x) return undefined; return x },
    [PropertyType._ahash]:   (x: string)   => x,
    [PropertyType._sha1]:    (x: string)   => x,
    [PropertyType._folders]: (x: number)   => x,
    [PropertyType._id]:      (x: number)   => x,
    [PropertyType._height]:  (x: number)   => x,
    [PropertyType._width]:   (x: number)   => x,
    [PropertyType.tag]:      (x: number[]) => { if (Array.isArray(x)) return x; return undefined },
    [PropertyType.multi_tags]:(x: number[])=> { if (Array.isArray(x)) return x; return undefined },
}

// ── Date bucket arithmetic ─────────────────────────────────────────────────
// Replaces closestDate() — zero Date allocations in the scan loop.
// Bucket key is a plain integer; display Date is computed once per unique key.

function dateBucketKey(date: Date | undefined, stepSize: number, unit: DateUnit): number | undefined {
    if (!date) return undefined
    if (!stepSize) stepSize = 1
    if (!unit) unit = DateUnit.Day
    if (unit === DateUnit.Year) {
        return Math.floor(date.getUTCFullYear() / stepSize)
    }
    if (unit === DateUnit.Month) {
        const totalMonths = date.getUTCFullYear() * 12 + date.getUTCMonth()
        return Math.floor(totalMonths / stepSize)
    }
    // Second, Minute, Hour, Day, Week — DateUnitFactor is in seconds
    const stepMs = stepSize * DateUnitFactor[unit] * 1000
    return Math.floor(date.getTime() / stepMs)
}

function dateBucketRange(key: number, stepSize: number, unit: DateUnit): { first: Date, last: Date } {
    if (!stepSize) stepSize = 1
    if (unit === DateUnit.Year) {
        const year = key * stepSize
        return {
            first: new Date(Date.UTC(year, 0, 1)),
            last:  new Date(Date.UTC(year + stepSize, 0, 1))
        }
    }
    if (unit === DateUnit.Month) {
        const startMonth = key * stepSize
        const endMonth   = startMonth + stepSize
        return {
            first: new Date(Date.UTC(Math.floor(startMonth / 12), startMonth % 12, 1)),
            last:  new Date(Date.UTC(Math.floor(endMonth   / 12), endMonth   % 12, 1))
        }
    }
    // Sub-day: epoch-ms arithmetic
    const stepMs = stepSize * DateUnitFactor[unit] * 1000
    return { first: new Date(key * stepMs), last: new Date(key * stepMs + stepMs - 1) }
}

// ── Group sort helpers ──────────────────────────────────────────────────────

function sortGroup(group: Group, option: GroupOption) {
    const data = useDataStore()
    if (group.children.length == 0) return
    if (option.type == GroupSortType.Property) {
        sortGroupByProperty(group, option.direction, data.properties, data.folders)
    } else {
        sortGroupBySize(group, option.direction)
    }
    for (let i = 0; i < group.children.length; i++) {
        group.children[i].parentIdx = i
    }
}

function sortGroupByProperty(group: Group, direction: number, properties: PropertyIndex, folders: FolderIndex) {
    const sortable: { [id: number]: any[] } = {}
    for (const child of group.children) {
        const values = []
        for (const propValue of child.meta.propertyValues) {
            const prop = properties[propValue.propertyId]
            const type = isTag(prop.type) ? PropertyType.tag : prop.type
            let value = propValue.value
            if (isTag(type) && value != undefined) value = prop.tags[value].value
            value = sortParser[type](value, folders)
            values.push(value)
        }
        sortable[child.id] = values
    }
    group.children.sort((ca, cb) => {
        const a = sortable[ca.id]
        const b = sortable[cb.id]
        for (let i = 0; i < a.length; i++) {
            if (a[i] == b[i]) continue
            if (a[i] < b[i]) return -1 * direction
            return 1 * direction
        }
        return 0
    })
}

function sortGroupBySize(group: Group, direction: number) {
    group.children.sort((a, b) => (a.slots.length - b.slots.length) * direction)
}

function setOrder(group: Group) {
    let i = 0
    const recursive = (g: Group) => {
        g.order = i++
        g.children.forEach(c => recursive(c))
    }
    recursive(group)
}

export function createGroupState(): GroupState {
    return { groupBy: [], options: {}, sha1Mode: false }
}

class GroupValueIndex {
    index: Map<any, any>
    private idCounter: number

    constructor() {
        this.index = new Map()
        this.idCounter = 1
    }

    get(valueKey: any[]) {
        let idx = this.index
        for (const value of valueKey) {
            if (!idx.has(value)) idx.set(value, new Map())
            idx = idx.get(value)
        }
        if (!idx.has(null)) {
            idx.set(null, this.idCounter++)
        }
        return idx.get(null)
    }

    delete(valueKey: any[]) {
        let idx = this.index
        for (const value of valueKey) {
            if (!idx.has(value)) return
            idx = idx.get(value)
        }
        idx.delete(null)
    }
}

export class GroupManager {
    state: GroupState
    result: GroupTree

    // Slot→position typed array from the last group() call (faster than plain-object map).
    // _posArr[slot] = display position; replaces ImageOrder = {[slot]: pos}.
    private _posArr: Int32Array
    private _posMaxSlot: number
    // When true, saveImagesToGroup is a no-op — avoids redundant Map writes during full rebuild.
    private _rebuildingTree = false
    // Leaf groups collected during computePropertySubGroup — avoids Object.values() in post-loop.
    private _leafGroups: Group[] = []
    customGroups: { [parentgroupId: number]: Group[] }
    onResultChange: EventEmitter
    onStateChange: EventEmitter

    selectedImages: Ref<SelectedImages>
    private selection: { lastImage: ImageIterator, lastGroup: GroupIterator }
    private iterators: GroupIterator[]

    constructor(state?: GroupState, selectedImages?: Ref<SelectedImages>) {
        this.state = reactive(createGroupState())
        if (state) Object.assign(this.state, state)
        this.result = {
            root: undefined,
            index: {},
            imageToGroups: new Map(),
            valueIndex: new GroupValueIndex(),
            orderedIds: new Int32Array(0),
            cacheStale: false
        }
        this._posArr = new Int32Array(0)
        this._posMaxSlot = 0
        this.customGroups = {}
        this.onResultChange = new EventEmitter()
        this.onStateChange = new EventEmitter()
        this.selectedImages = selectedImages ?? shallowRef<SelectedImages>({})
        this.selection = { lastImage: undefined, lastGroup: undefined }
        this.iterators = []
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
        const lastCustom = this.customGroups ?? {}
        this.customGroups = {}
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

        let insert = true
        const toInsert = new Set(Object.keys(lastCustom).map(Number))
        while (insert) {
            insert = false
            for (const target of Array.from(toInsert)) {
                if (this.result.index[target]) {
                    this.addCustomGroups(target, lastCustom[target])
                    toInsert.delete(target)
                    insert = true
                }
            }
        }

        if (this.state.sha1Mode) this.groupLeafsBySha1()

        for (const id of Object.keys(this.result.index)) {
            const group = this.result.index[id]
            if (lastIndex[id]) group.view = lastIndex[id].view
        }

        setOrder(this.result.root)
        this.buildOrdinalRanges()
        console.timeEnd('Group')
        if (emit) this.onResultChange.emit(this.result)
        return this.result
    }

    // Build start/end offsets for all groups and fill orderedIds (instance IDs in DFS display order).
    // Single DFS pass: root.slots.length is the pre-known total, so we pre-allocate and fill in one sweep.
    buildOrdinalRanges(): void {
        if (!this.result.root) return
        const ids = useColumnStore().instanceIds()
        const orderedIds = new Int32Array(this.result.root.slots.length)
        let pos = 0

        const dfs = (group: Group): void => {
            group.start = pos
            if (group.children.length === 0) {
                for (const s of group.slots) orderedIds[pos++] = ids[s]
            } else if (group.subGroupType === GroupType.Sha1) {
                for (const child of group.children) {
                    child.start = pos
                    for (const s of child.slots) orderedIds[pos++] = ids[s]
                    child.end = pos
                }
            } else {
                for (const child of group.children) dfs(child)
            }
            group.end = pos
        }
        dfs(this.result.root)

        this.result.orderedIds = orderedIds
        this.result.cacheStale = false
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
                    for (const p of tagWithParents[v]) withParents.add(p)
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
        if (emit) this.onResultChange.emit(this.result)
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

    private groupLeafsBySha1() {
        this.removeSha1Groups()
        for (const group of Object.values(this.result.index) as Group[]) {
            if (group.children.length > 0) continue
            this.groupBySha1(group)
        }
    }

    removeSha1Groups() {
        this.invalidateIterators()
        for (const group of Object.values(this.result.index) as Group[]) {
            if (group.subGroupType != GroupType.Sha1) continue
            this.removeChildren(group)
        }
    }

    hasResult() {
        return this.result.root != undefined
    }

    clear(emit?: boolean) {
        this.invalidateIterators()
        this.result.imageToGroups = new Map()
        this.result.index = {}
        this.result.root = undefined
        this.result.valueIndex = new GroupValueIndex()
        this.result.orderedIds = new Int32Array(0)
        this.result.cacheStale = false
        this.clearLastSelected()
        this.clearSelection()
        this.customGroups = {}
        this._posArr = new Int32Array(0)
        this._posMaxSlot = 0
        if (emit) this.onResultChange.emit(this.result)
    }

    emptyRoot(emit?: boolean) {
        this.clear()
        this.group(new Int32Array(0), emit)
    }

    setAsRoot(group: Group, emit?: boolean) {
        this.emptyRoot()
        const copy = { ...group }
        copy.slots = [...group.slots]
        delete copy.id
        Object.assign(this.result.root, copy)
        if (this.state.sha1Mode) this.groupBySha1(this.result.root)
        this.buildOrdinalRanges()
        if (emit) this.onResultChange.emit(this.result)
    }

    verifyState(properties: PropertyIndex) {
        this.state.groupBy = this.state.groupBy.filter(id => properties[id] && properties[id].id != deletedID)
        Object.keys(this.state.options)
            .filter(id => !properties[Number(id)] || properties[Number(id)].id == deletedID)
            .forEach(id => delete this.state.options[Number(id)])
    }

    registerIterator(it: GroupIterator) {
        this.iterators.push(it)
    }

    private invalidateIterators() {
        for (const it of this.iterators) it.isValid = false
        this.iterators = []
    }

    private removeChildren(group: Group) {
        group.children.forEach(c => {
            delete this.result.index[c.id]
            if (c.key.length) this.result.valueIndex.delete(c.key)
            this.removeImageToGroups(c)
        })
        group.children.length = 0
        group.subGroupType = undefined
    }

    private groupBySha1(group: Group) {
        if (group.children) group.children.length = 0
        const col = useColumnStore()
        const sha1PropId = col.systemProps.SHA1
        const order: string[] = []
        const groups: { [sha1: string]: Group } = {}

        for (const s of group.slots) {
            const sha1: string = sha1PropId !== null ? col.readSlot(sha1PropId, s) : undefined
            if (!sha1) continue
            if (!groups[sha1]) {
                const key = [...group.key, sha1]
                const groupId = this.result.valueIndex.get(key)
                groups[sha1] = buildGroup(groupId, [s], GroupType.Sha1)
                groups[sha1].key = key
                groups[sha1].meta.propertyValues.push({ propertyId: PropertyID.sha1, value: sha1 })
                order.push(sha1)
            } else {
                groups[sha1].slots.push(s)
            }
        }

        const children = order.map(sha1 => groups[sha1])
        children.forEach(c => this.regsiterGroup(c))
        this.setChildGroup(group, children)
    }

    async update(emit?: boolean): Promise<void> {
        this.invalidateIterators()
        if (!this.result.root) return
        await this.group(new Int32Array(this.result.root.slots), emit)
    }

    updateSelection(updated: Set<number>, removed: Set<number>) {
        const col = useColumnStore()
        this.invalidateIterators()
        this.removeSha1Groups()

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
            group.slots = group.slots.filter(s => {
                const id = ids[s]
                return !removed.has(id) && !updated.has(id)
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
                const option = this.state.options[group.children[0].meta.propertyValues[0].propertyId]
                sortGroup(group, option)
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

        setOrder(this.result.root)
        if (this.state.sha1Mode) this.groupLeafsBySha1()
        this.buildOrdinalRanges()

        let structureChanged = removed.size > 1
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
        if (structureChanged) this.onResultChange.emit(this.result)
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
            this.customGroups = {}
        }
        this.onStateChange.emit()
    }

    delGroupOption(propertyId: number) {
        const index = this.state.groupBy.indexOf(propertyId)
        if (index < 0) return
        this.state.groupBy.splice(index, 1)
        this.customGroups = {}
        this.onStateChange.emit()
    }

    addCustomGroups(targetGroupId: number, groups: Group[], emit?: boolean) {
        this.invalidateIterators()
        const parent = this.result.index[targetGroupId]
        if (!parent) return
        this.customGroups[targetGroupId] = groups
        this.setChildGroup(parent, groups)
        if (parent.subGroupType == GroupType.Cluster && this.state.sha1Mode) {
            groups.forEach(g => this.groupBySha1(g))
        }
        setOrder(this.result.root)
        this.buildOrdinalRanges()
        if (emit) this.onResultChange.emit(this.result)
    }

    delCustomGroups(targetGroupId: number, emit?: boolean) {
        delete this.customGroups[targetGroupId]
        this.removeChildren(this.result.index[targetGroupId])
        if (this.state.sha1Mode) this.groupBySha1(this.result.index[targetGroupId])
        this.buildOrdinalRanges()
        if (emit) this.onResultChange.emit(this.result)
    }

    clearCustomGroups(emit?: boolean) {
        for (const groupId of Object.keys(this.customGroups).map(Number)) {
            this.delCustomGroups(groupId)
        }
        if (emit) this.onResultChange.emit(this.result)
    }

    setSha1Mode(value: boolean, emit?: boolean) {
        if (this.state.sha1Mode == value) return
        this.invalidateIterators()
        this.state.sha1Mode = value
        if (value) this.groupLeafsBySha1()
        else this.removeSha1Groups()
        this.buildOrdinalRanges()
        this.onStateChange.emit()
        if (emit) this.onResultChange.emit(this.result)
    }

    toggleGroup(groupId, emit?: boolean) {
        this.result.index[groupId].view.closed = !this.result.index[groupId].view.closed
        if (emit) this.onResultChange.emit(this.result)
    }

    openGroup(groupId, emit?: boolean) {
        this.result.index[groupId].view.closed = false
        if (emit) this.onResultChange.emit(this.result)
    }

    closeGroup(groupId, emit?: boolean) {
        this.result.index[groupId].view.closed = true
        if (emit) this.onResultChange.emit(this.result)
    }

    getGroupIterator(groupId?: number, options?: GroupIteratorOptions) {
        return new GroupIterator(this, groupId, options)
    }

    getImageIterator(groupId?: number, imageIdx?: number, options?: GroupIteratorOptions) {
        return new ImageIterator(this, groupId, imageIdx, options)
    }

    findImageIterator(groupId: number, imageId: number) {
        const col = useColumnStore()
        const group = this.result.index[groupId]
        const targetSlot = col.slotMap.get(imageId)
        let idx = 0
        if (group.subGroupType == GroupType.Sha1) {
            const sha1PropId = col.systemProps.SHA1
            const targetSha1 = targetSlot !== undefined && sha1PropId !== null
                ? col.readSlot(sha1PropId, targetSlot) : undefined
            idx = group.children.findIndex(g => {
                const firstSlot = g.slots[0]
                return firstSlot !== undefined && sha1PropId !== null
                    && col.readSlot(sha1PropId, firstSlot) === targetSha1
            })
        } else {
            idx = targetSlot !== undefined ? group.slots.indexOf(targetSlot) : -1
        }
        return this.getImageIterator(groupId, idx)
    }

    private setChildGroup(parent: Group, groups: Group[]) {
        this.removeChildren(parent)
        for (const group of groups) {
            group.parentIdx = parent.children.length
            group.parent = parent
            group.depth = parent.depth + 1
            parent.children.push(group)
            this.regsiterGroup(group)
            if (group.type != GroupType.Sha1) this.saveImagesToGroup(group)
        }
        parent.subGroupType = parent.children.length ? groups[0].type : undefined
    }

    private addChildGroup(parent: Group, group: Group) {
        group.parentIdx = parent.children.length
        group.parent = parent
        group.depth = parent.depth + 1
        parent.children.push(group)
        this.regsiterGroup(group)
        if (group.type != GroupType.Sha1) this.saveImagesToGroup(group)
        parent.subGroupType = parent.children.length ? group.type : undefined
        this.removeImageToGroups(parent)
        if (parent.subGroupType == GroupType.Sha1) this.saveImagesToGroup(parent)
    }

    private regsiterGroup(group: Group) {
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
                if (!raw) continue
                const bk = dateBucketKey(raw instanceof Date ? raw : new Date(raw as number), option.stepSize, option.stepUnit)
                if (bk === undefined) continue
                if (!bucketMeta.has(bk)) {
                    const range = dateBucketRange(bk, option.stepSize, option.stepUnit)
                    bucketMeta.set(bk, { displayVal: range.first, intervalEnd: range.last })
                }
                let arr = buckets.get(bk); if (!arr) { arr = []; buckets.set(bk, arr) }; arr.push(s)
            } else if (isTagType) {
                const tagIds = rawBuf?.[s] as number[] | null
                if (!Array.isArray(tagIds) || !tagIds.length) continue
                // Dedup expanded parents within this slot without allocating a Set: while
                // slot s is being processed, any bucket we push s into has s as its last
                // element until we move on, so a last-element check collapses the duplicate
                // parents shared across the slot's tags.
                for (const v of tagIds) {
                    if (!v) continue
                    const parents = tagWithParents[v]
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

    // ── Selection ──────────────────────────────────────────────────────────

    clearSelection() {
        if (this.result.root) this.unselectGroup(this.result.root)
        this.selectedImages.value = {}
        this.clearLastSelected()
    }

    selectImageIterator(iterator: ImageIterator, shift = false) {
        if (shift) this._shiftSelect(iterator)
        const ids = useColumnStore().instanceIds()
        this.selectImages(iterator.slots.map(s => ids[s]))
        this.clearLastSelected()
        this.selection.lastImage = iterator.clone()
    }

    unselectImageIterator(iterator: ImageIterator) {
        const ids = useColumnStore().instanceIds()
        this.unselectImages(iterator.slots.map(s => ids[s]))
        this.clearLastSelected()
    }

    toggleImageIterator(iterator: ImageIterator, shift = false) {
        const ids = useColumnStore().instanceIds()
        const selected = iterator.slots.every(s => this.selectedImages.value[ids[s]])
        if (selected) this.unselectImageIterator(iterator)
        else this.selectImageIterator(iterator, shift)
    }

    toggleAll() {
        const iterator = this.getGroupIterator()
        this.toggleGroupIterator(iterator)
    }

    private _shiftSelect(iterator: ImageIterator) {
        if (this.selection.lastImage == undefined) return false
        const ids = useColumnStore().instanceIds()
        const start = this.selection.lastImage.isImageBefore(iterator) ? this.selection.lastImage : iterator
        const end   = start == iterator ? this.selection.lastImage : iterator

        const selected: number[] = []
        let it = start.clone()
        while (it) {
            if (end.isImageBefore(it)) break
            if (it.sha1Group) {
                for (const s of it.sha1Group.slots) selected.push(ids[s])
            } else {
                selected.push(ids[it.slot])
            }
            it = it.nextImages()
        }
        if (selected.length) { this.selectImages(selected); return true }
        return false
    }

    private _shiftGroup(iterator: GroupIterator) {
        if (this.selection.lastGroup == undefined) return false
        const ids = useColumnStore().instanceIds()
        const start = this.selection.lastGroup.isGroupBefore(iterator) ? this.selection.lastGroup : iterator
        const end   = start == iterator ? this.selection.lastGroup : iterator

        const selected: number[] = []
        let it = start.clone()
        while (it) {
            if (end.isGroupBefore(it)) break
            for (const s of it.group.slots) selected.push(ids[s])
            it = it.nextGroup()
        }
        if (selected.length) { this.selectImages(selected); return true }
        return false
    }

    clearLastSelected() {
        this.selection.lastGroup = undefined
        this.selection.lastImage = undefined
    }

    unselectImage(imageId: number) { this.unselectImages([imageId]) }
    selectImage(imageId: number)   { this.selectImages([imageId]) }

    selectImages(imageIds: number[]) {
        imageIds.forEach(id => this.selectedImages.value[id] = true)
        triggerRef(this.selectedImages)
    }

    unselectImages(imageIds: number[]) {
        imageIds.forEach(id => delete this.selectedImages.value[id])
        triggerRef(this.selectedImages)
    }

    propagateUnselect(group: Group) {
        group.view.selected = false
        if (!group.parent) return
        this.propagateUnselect(group.parent)
    }

    propagateSelect(group: Group) {
        const ids = useColumnStore().instanceIds()
        if (group.children.length == 0 || group.subGroupType == GroupType.Sha1) {
            group.view.selected = group.slots.every(s => this.selectedImages.value[ids[s]])
        } else {
            group.view.selected = group.children.every(g => g.view.selected)
        }
        if (!group.parent) return
        this.propagateSelect(group.parent)
    }

    selectGroup(group: Group) {
        const ids = useColumnStore().instanceIds()
        this.selectImages(group.slots.map(s => ids[s]))
    }

    unselectGroup(group: Group) {
        const ids = useColumnStore().instanceIds()
        this.unselectImages(group.slots.map(s => ids[s]))
    }

    selectGroupIterator(iterator: GroupIterator, shift = false) {
        if (shift) this._shiftGroup(iterator)
        this.selectGroup(iterator.group)
        this.clearLastSelected()
        this.selection.lastGroup = iterator.clone()
    }

    unselectGroupIterator(iterator: GroupIterator) {
        this.unselectGroup(iterator.group)
        this.clearLastSelected()
    }

    toggleGroupIterator(iterator: GroupIterator, shift = false) {
        const ids = useColumnStore().instanceIds()
        const selected = !iterator.group.slots.some(s => !this.selectedImages.value[ids[s]])
        if (selected) this.unselectGroupIterator(iterator)
        else this.selectGroupIterator(iterator, shift)
    }
}

export interface GroupIteratorOptions {
    ignoreClosed?: boolean
    onlyPropertyGroups?: boolean
    register?: boolean
}

export class GroupIterator {
    isValid: boolean
    readonly group: Group

    protected manager: GroupManager
    groupId: number
    options: GroupIteratorOptions

    constructor(manager: GroupManager, groupId?: number, options?: GroupIteratorOptions) {
        this.isValid = true
        this.manager = manager
        if (options?.register) this.manager.registerIterator(this)
        this.groupId = groupId ?? 0
        this.options = options ?? {}
        this.group = this.getGroup()
        this.isValid = this.group !== undefined
    }

    clone(options?: GroupIteratorOptions): GroupIterator {
        return new GroupIterator(this.manager, this.groupId, options ?? this.options)
    }

    private getGroup(): Group {
        return this.manager.result.index[this.groupId]
    }

    nextGroup(): GroupIterator {
        let current = this.group
        if (!current.view.closed && current.children.length > 0 && current.subGroupType != GroupType.Sha1) {
            return new GroupIterator(this.manager, current.children[0].id)
        }
        let parent = current.parent
        while (parent != undefined) {
            const next = parent.children[current.parentIdx + 1]
            if (next) return new GroupIterator(this.manager, next.id)
            current = parent
            parent = current.parent
        }
        return undefined
    }

    prevGroup(): GroupIterator {
        const current = this.group
        const prevSibling = current.parent?.children[current.parentIdx - 1]
        if (prevSibling) {
            if (prevSibling.children.length > 0 && (!prevSibling.view.closed || this.options.ignoreClosed)) {
                let lastChild = prevSibling.children[prevSibling.children.length - 1]
                while (lastChild.children.length > 0 && (!lastChild.view.closed || this.options.ignoreClosed)) {
                    lastChild = lastChild.children[lastChild.children.length - 1]
                }
                return new GroupIterator(this.manager, lastChild.id)
            } else {
                return new GroupIterator(this.manager, prevSibling.id)
            }
        }
        const parent = current.parent
        if (parent && parent.parent) return new GroupIterator(this.manager, parent.id)
        return undefined
    }

    isGroupBefore(it: GroupIterator): boolean { return this.group.order < it.group.order }
    isGroupEqual(it: GroupIterator): boolean  { return this.group.order == it.group.order }
}

export class ImageIterator extends GroupIterator {
    // Slot index of the current image (or first slot of the sha1 pile).
    readonly slot: number
    // All slots at this position (one entry normally, many if sha1 pile).
    readonly slots: number[]
    readonly sha1Group: Group
    declare readonly group: Group

    imageIdx: number

    constructor(manager: GroupManager, groupId?: number, imageIdx?: number, options?: GroupIteratorOptions) {
        super(manager, groupId, options)
        this.imageIdx = imageIdx ?? 0

        if (this.isValid && this.shouldSkipGroup(this.group)) {
            const next = this.nextGroup()
            if (next) {
                this.groupId = next.groupId
                Object.defineProperty(this, 'group', { value: next.group, writable: false })
                this.imageIdx = 0
            } else {
                this.isValid = false
            }
        }

        if (this.isValid) {
            this.slots = this.getSlots()
            this.slot = this.slots[0]
            this.sha1Group = this.getSha1Group()
        }
    }

    private shouldSkipGroup(group: Group): boolean {
        if (group.children.length === 0) return false
        if (group.subGroupType === GroupType.Sha1) return false
        return true
    }

    static fromGroupIterator(it: GroupIterator, options?: GroupIteratorOptions) {
        const imageIt = new ImageIterator(it['manager'], it.group.id, 0, options)
        if (!imageIt.isValid) return undefined
        return imageIt
    }

    private getSlots(): number[] {
        if (this.group.subGroupType == GroupType.Sha1) {
            return this.group.children[this.imageIdx].slots
        }
        return [this.group.slots[this.imageIdx]]
    }

    private getSha1Group() {
        return this.group.children[this.imageIdx]
    }

    nextGroup(): ImageIterator {
        let next = super.nextGroup()
        while (next) {
            const group = next.group
            const shouldIterate = (!group.view.closed || this.options.ignoreClosed)
                && !this.shouldSkipGroup(group)
            if (shouldIterate) {
                const lastIndex = group.subGroupType == GroupType.Sha1
                    ? group.children.length - 1
                    : group.slots.length - 1
                return new ImageIterator(this.manager, next.group.id, lastIndex, this.options)
            }
            next = next.nextGroup()
        }
        return undefined
    }

    prevGroup(): ImageIterator {
        let prev = super.prevGroup()
        while (prev) {
            const group = prev.group
            const shouldIterate = (!group.view.closed || this.options.ignoreClosed)
                && !this.shouldSkipGroup(group)
            if (shouldIterate) {
                return new ImageIterator(this.manager, prev.group.id, 0, this.options)
            }
            prev = prev.prevGroup()
        }
        return undefined
    }

    nextImages(): ImageIterator {
        let current = this.clone()
        let nextIdx = current.imageIdx + 1
        while (current) {
            const group = current.group
            if (group.subGroupType == GroupType.Sha1) {
                if (group.children[nextIdx]) {
                    return new ImageIterator(this.manager, current.groupId, nextIdx, this.options)
                }
            } else {
                if (group.slots[nextIdx] !== undefined) {
                    return new ImageIterator(this.manager, current.groupId, nextIdx, this.options)
                }
            }
            current = current.nextGroup()
            nextIdx = 0
        }
    }

    prevImages(): ImageIterator {
        let current = this.clone()
        let prevIdx = current.imageIdx - 1
        while (current) {
            const group = current.group
            if (group.subGroupType == GroupType.Sha1) {
                if (group.children[prevIdx]) {
                    return new ImageIterator(this.manager, current.groupId, prevIdx, this.options)
                }
            } else {
                if (group.slots[prevIdx] !== undefined) {
                    return new ImageIterator(this.manager, current.groupId, prevIdx, this.options)
                }
            }
            current = current.prevGroup()
            if (current) {
                prevIdx = group.subGroupType == GroupType.Sha1
                    ? current.group.children.length - 1
                    : current.group.slots.length - 1
            }
        }
        return undefined
    }

    isImageBefore(it: ImageIterator) {
        if (this.isGroupEqual(it)) return this.imageIdx < it.imageIdx
        return this.isGroupBefore(it)
    }

    isImageEqual(it: ImageIterator) {
        return this.isGroupEqual(it) && this.imageIdx == it.imageIdx
    }

    clone(options?: GroupIteratorOptions): ImageIterator {
        return new ImageIterator(this.manager, this.groupId, this.imageIdx, options ?? this.options)
    }

    // Returns the global display position for this image within orderedIds.
    // For sha1 groups: returns the start offset of the sha1 pile.
    // For regular groups: returns group.start + imageIdx.
    getImageOrder(): number {
        const group = this.manager.result.index[this.groupId]
        if (!group) return 0
        if (group.subGroupType === GroupType.Sha1) {
            return group.children[this.imageIdx]?.start ?? 0
        }
        return group.start + this.imageIdx
    }
}
