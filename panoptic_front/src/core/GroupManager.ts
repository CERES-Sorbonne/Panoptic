/**
 * GroupManager
 * Builds a Group tree from an Int32Array of column-store slot indices.
 * Group.slots: number[] is the primitive — no Instance objects allocated.
 * ImageOrder is keyed by slot (matching SortManager output).
 */

import { deletedID, DateUnit, DateUnitFactor, FolderIndex, GroupScoreList, PropertyID, PropertyIndex, PropertyValue, Score, ScoreList, TagIndex } from "@/data/models";
import { Ref, reactive, shallowRef, toRefs, triggerRef } from "vue";
import { ImageOrder, SortDirection, SortOption, sortParser } from "./SortManager";
import { PropertyType } from "@/data/models";
import { deepCopy, EventEmitter, isTag, objValues } from "@/utils/utils";
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
    imageToGroups: { [instanceId: number]: number[] }
    valueIndex: GroupValueIndex
    imageIteratorOrder: { [groupId: number]: { [imgIdx: number]: number } }
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

function closestDate(date: Date, stepSize: number, unit: DateUnit) {
    if (!stepSize) stepSize = 1
    if (!unit) unit = DateUnit.Day
    if (date == undefined) return
    date = new Date(date)
    let step = stepSize * DateUnitFactor[unit]
    if (unit == DateUnit.Second || unit == DateUnit.Minute || unit == DateUnit.Hour || unit == DateUnit.Day || unit == DateUnit.Week) {
        step *= 1000
        let ratio = Math.floor(date.getTime() / step)
        return { first: new Date(ratio * step), last: new Date(ratio * step + step - 1) }
    }
    if (unit == DateUnit.Year) {
        let ratio = Math.floor(date.getUTCFullYear() / step)
        let first = new Date(ratio * step, 0, 1)
        first = new Date(first.getTime() - first.getTimezoneOffset() * 60 * 1000)
        let last = new Date(ratio * step + step, 0, 1)
        last = new Date(last.getTime() - last.getTimezoneOffset() * 60 * 1000)
        return { first, last }
    }
    if (unit == DateUnit.Month) {
        let dateIndex = date.getUTCFullYear() * 12 + date.getUTCMonth()
        let ratio = Math.floor(dateIndex / step) * step
        let year = Math.floor(ratio / 12)
        let month = ratio % 12
        let first = new Date(year, month, 1)
        first = new Date(first.getTime() - first.getTimezoneOffset() * 60 * 1000)
        ratio = Math.floor(dateIndex / step) * step + step
        year = Math.floor(ratio / 12)
        month = ratio % 12
        let last = new Date(year, month, 1)
        last = new Date(last.getTime() - last.getTimezoneOffset() * 60 * 1000)
        return { first, last }
    }
    return { first: date, last: date }
}

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
    for (let child of group.children) {
        const values = []
        for (let propValue of child.meta.propertyValues) {
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
        let a = sortable[ca.id]
        let b = sortable[cb.id]
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

// ImageOrder is keyed by slot (from SortManager).
function sortGroupSlots(group: Group, order: ImageOrder) {
    group.slots.sort((a, b) => (order[a] ?? 0) - (order[b] ?? 0))
}

function setOrder(group: Group) {
    let i = 0
    const idx = () => i++
    const recursive = (group: Group) => {
        group.order = idx()
        group.children.forEach(c => recursive(c))
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
        for (let value of valueKey) {
            if (!idx.has(value)) idx.set(value, new Map())
            idx = idx.get(value)
        }
        if (!idx.has(null)) {
            const id = this.idCounter
            idx.set(null, id)
            this.idCounter += 1
        }
        return idx.get(null)
    }

    delete(valueKey: any[]) {
        let idx = this.index
        for (let value of valueKey) {
            if (!idx.has(value)) return
            idx = idx.get(value)
        }
        idx.delete(null)
    }
}

export class GroupManager {
    state: GroupState
    result: GroupTree

    lastOrder: ImageOrder
    customGroups: { [parentgroupId: number]: Group[] }
    onResultChange: EventEmitter
    onStateChange: EventEmitter

    selectedImages: Ref<SelectedImages>
    private selection: { lastImage: ImageIterator, lastGroup: GroupIterator }
    private iterators: GroupIterator[]

    constructor(state?: GroupState, selectedImages?: Ref<SelectedImages>) {
        this.state = reactive(createGroupState())
        if (state) Object.assign(this.state, state)
        this.result = { root: undefined, index: {}, imageToGroups: {}, valueIndex: new GroupValueIndex(), imageIteratorOrder: {} }
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

    addUpdatedToGroups(slots: Int32Array, order?: ImageOrder, emit?: boolean) {
        if (!this.result.root) {
            this.group(slots, order)
            return
        }
        console.time('Group Update')
        const data = useDataStore()
        this.invalidateIterators()

        if (this.state.groupBy.length > 0) {
            for (let i = 0; i < slots.length; i++) {
                this.addInstanceToGroups(slots[i], data.properties, data.tags)
            }
        } else {
            for (let i = 0; i < slots.length; i++) {
                this.result.root.slots.push(slots[i])
            }
        }

        if (order) {
            for (let group of objValues(this.result.index)) {
                if (group.type != GroupType.Cluster) sortGroupSlots(group, order)
            }
        }

        this.result.imageToGroups = {}
        for (let group of Object.values(this.result.index)) {
            if (group.children.length > 0 && group.subGroupType != GroupType.Sha1) continue
            this.saveImagesToGroup(group)
        }

        setOrder(this.result.root)
        console.timeEnd('Group Update')
        if (emit) this.onResultChange.emit(this.result)
        return this.result
    }

    addInstanceToGroups(slot: number, properties: PropertyIndex, tags: TagIndex) {
        const col = useColumnStore()
        const keys = []
        let previousKeys = []

        for (let propId of this.state.groupBy) {
            const property = properties[propId]
            const option = this.state.options[property.id]
            let value = col.readSlot(propId, slot)
            value = valueParser[property.type](value)

            const tagWithParents: { [id: number]: Set<number> } = {}
            if (isTag(property.type) && property.tags) {
                for (let tag of objValues(property.tags)) {
                    tagWithParents[tag.id] = new Set(tag.allParents)
                    tagWithParents[tag.id].add(tag.id)
                }
            }

            let intervalEnd = undefined
            if (property.type == PropertyType.date) {
                const res = closestDate(value, option.stepSize, option.stepUnit)
                if (res) { value = res.first.toISOString(); intervalEnd = res.last }
            }

            let values = Array.isArray(value) ? value : [value]
            if (isTag(property.type) && values[0] !== undefined) {
                const withParents = new Set<any>()
                for (let v of values) {
                    if (!v) continue
                    for (let p of tagWithParents[v]) withParents.add(p)
                }
                values = Array.from(withParents)
            }

            if (previousKeys.length == 0) {
                keys.push(...values.map(v => [v]))
                previousKeys = values.map(v => [v])
            } else {
                let newKeys = []
                for (let prevK of previousKeys) {
                    for (let val of values) newKeys.push([...prevK, val])
                }
                keys.push(...newKeys)
                previousKeys = newKeys
            }

            for (let key of previousKeys) {
                const groupId = this.result.valueIndex.get(key)
                if (!this.result.index[groupId]) {
                    const group = buildGroup(groupId, [], GroupType.Property)
                    let realValue = key[key.length - 1]
                    if (property.type == PropertyType.date) realValue = new Date(realValue)
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

    async group(slots: Int32Array, order?: ImageOrder, emit?: boolean, time?: boolean): Promise<GroupTree> {
        console.log('[GM.group] called slots=', slots.length, 'emit=', emit)
        await this._ensureColumns()
        time = true
        if (time) console.time('Group')
        const data = useDataStore()
        this.invalidateIterators()
        this.lastOrder = order
        const lastIndex = this.result.index ?? {}
        this.result.root = buildRoot(Array.from(slots))
        this.result.index = {}
        this.result.imageToGroups = {}
        const lastCustom = this.customGroups ?? {}
        this.customGroups = {}
        this.regsiterGroup(this.result.root)

        if (this.state.groupBy.length > 0) {
            this.computePropertySubGroup(this.result.root, this.state.groupBy, data.properties, data.tags)
        }

        if (order) {
            for (let group of objValues(this.result.index)) {
                sortGroupSlots(group, order)
            }
        }

        for (let group of Object.values(this.result.index)) {
            if (group.children.length > 0 && group.subGroupType != GroupType.Sha1) continue
            this.saveImagesToGroup(group)
        }

        let insert = true
        let toInsert = new Set(Object.keys(lastCustom).map(Number))
        while (insert) {
            insert = false
            for (let target of Array.from(toInsert)) {
                if (this.result.index[target]) {
                    this.addCustomGroups(target, lastCustom[target])
                    toInsert.delete(target)
                    insert = true
                }
            }
        }

        if (this.state.sha1Mode) this.groupLeafsBySha1()

        Object.keys(this.result.index).map(id => {
            const group = this.result.index[id]
            if (lastIndex[id]) group.view = lastIndex[id].view
        })

        setOrder(this.result.root)
        if (time) console.timeEnd('Group')
        console.log('[GM.group] done root.slots=', this.result.root?.slots?.length, 'groups=', Object.keys(this.result.index).length, 'emit=', emit)
        if (emit) this.onResultChange.emit(this.result)
        this.computeImageOrder()
    console.log(this.result)
        return this.result
    }

    computeImageOrder() {
        let it = this.getImageIterator()
        let count = 0
        while (it && it.isValid) {
            if (!this.result.imageIteratorOrder[it.groupId]) {
                this.result.imageIteratorOrder[it.groupId] = {}
            }
            this.result.imageIteratorOrder[it.groupId][it.imageIdx] = count += 1
            it = it.nextImages()
        }
    }

    sortGroups(emit?: boolean) {
        this.invalidateIterators()
        for (let group of Object.values(this.result.index) as Group[]) {
            if (group.subGroupType != GroupType.Property) continue
            if (group.children.length == 0) continue
            sortGroup(group, this.state.options[group.children[0].meta.propertyValues[0].propertyId])
        }
        if (emit) this.onResultChange.emit(this.result)
    }

    private saveImagesToGroup(group: Group) {
        const col = useColumnStore()
        for (const s of group.slots) {
            const id = col.instanceIds[s]
            if (!this.result.imageToGroups[id]) this.result.imageToGroups[id] = []
            this.result.imageToGroups[id].push(group.id)
        }
    }

    private groupLeafsBySha1() {
        this.removeSha1Groups()
        for (let group of Object.values(this.result.index) as Group[]) {
            if (group.children.length > 0) continue
            this.groupBySha1(group)
        }
    }

    removeSha1Groups() {
        this.invalidateIterators()
        for (let group of Object.values(this.result.index) as Group[]) {
            if (group.subGroupType != GroupType.Sha1) continue
            this.removeChildren(group)
        }
    }

    hasResult() {
        return this.result.root != undefined
    }

    clear(emit?: boolean) {
        this.invalidateIterators()
        this.result.imageToGroups = {}
        this.result.index = {}
        this.result.root = undefined
        this.result.valueIndex = new GroupValueIndex()
        this.clearLastSelected()
        this.clearSelection()
        this.customGroups = {}
        this.lastOrder = {}
        this.result.imageIteratorOrder = {}
        if (emit) this.onResultChange.emit(this.result)
    }

    emptyRoot(emit?: boolean) {
        this.clear()
        this.group(new Int32Array(0), undefined, emit)
    }

    setAsRoot(group: Group, emit?: boolean) {
        this.emptyRoot()
        let copy = { ...group }
        copy.slots = [...group.slots]
        delete copy.id
        Object.assign(this.result.root, copy)
        if (this.state.sha1Mode) this.groupBySha1(this.result.root)
        this.computeImageOrder()
        if (emit) this.onResultChange.emit(this.result)
    }

    verifyState(properties: PropertyIndex) {
        this.state.groupBy = this.state.groupBy.filter(id => properties[id] && properties[id].id != deletedID)
        Object.keys(this.state.options).filter(id => !properties[id] || properties[id].id == deletedID).forEach(id => delete this.state.options[id])
    }

    registerIterator(it: GroupIterator) {
        this.iterators.push(it)
    }

    private invalidateIterators() {
        for (let it of this.iterators) it.isValid = false
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
        let order: string[] = []
        let groups: { [sha1: string]: Group } = {}

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
        await this.group(new Int32Array(this.result.root.slots), this.lastOrder, emit, true)
        console.log('update group', this.result)
    }

    updateSelection(updated: Set<number>, removed: Set<number>) {
        const col = useColumnStore()
        this.invalidateIterators()
        this.removeSha1Groups()

        const oldGroupIds: { [id: number]: number[] } = {}
        for (let id of updated) {
            oldGroupIds[id] = [...(this.result.imageToGroups[id] ?? [])]
        }

        let groups = new Set<number>()
        for (let instanceId of removed) {
            this.result.imageToGroups[instanceId]?.forEach(g => groups.add(g))
        }
        for (let instanceId of updated) {
            this.result.imageToGroups[instanceId]?.forEach(g => groups.add(g))
        }
        groups.add(0)

        for (let groupId of groups) {
            const group = this.result.index[groupId]
            if (!group) continue
            if (group.type == GroupType.Cluster) continue
            group.dirty = true
            group.slots = group.slots.filter(s => {
                const id = col.instanceIds[s]
                return !removed.has(id) && !updated.has(id)
            })
        }

        // Convert updated instance IDs → slots for re-insertion
        const updatedSlots: number[] = []
        for (const id of updated) {
            const s = col.slotMap.get(id)
            if (s !== undefined) updatedSlots.push(s)
        }
        this.addUpdatedToGroups(new Int32Array(updatedSlots), this.lastOrder)

        for (let group of objValues(this.result.index)) {
            if (group.slots.length == 0) delete this.result.index[group.id]
            const oldLen = group.children.length
            group.children = group.children.filter(g => g.slots.length > 0)
            if (group.children.length < oldLen) group.dirty = true
        }

        for (let group of objValues(this.result.index)) {
            if (!group.dirty) continue
            if (group.subGroupType == GroupType.Property) {
                const option = this.state.options[group.children[0].meta.propertyValues[0].propertyId]
                sortGroup(group, option)
            }
            if (group.type == GroupType.Property) sortGroupSlots(group, this.lastOrder)
            group.dirty = false
        }
        setOrder(this.result.root)

        if (this.state.sha1Mode) this.groupLeafsBySha1()
        this.computeImageOrder()

        let structureChanged = removed.size > 1
        if (!structureChanged) {
            for (let id of updated) {
                const before = oldGroupIds[id] ?? []
                const after = this.result.imageToGroups[id] ?? []
                if (before.length !== after.length || before.some(g => !after.includes(g))) {
                    structureChanged = true
                    break
                }
            }
        }
        if (structureChanged) this.onResultChange.emit(this.result)
        return this.result
    }

    sort(order: ImageOrder, emit?: boolean) {
        this.invalidateIterators()
        if (this.state.sha1Mode) this.removeSha1Groups()
        this.lastOrder = order

        Object.values(this.result.index).map(v => v as Group).forEach(g => {
            sortGroupSlots(g, order)
        })

        if (this.state.sha1Mode) this.groupLeafsBySha1()
        if (emit) {
            this.computeImageOrder()
            this.onResultChange.emit(this.result)
        }
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
        this.computeImageOrder()
        this.onStateChange.emit()
    }

    delGroupOption(propertyId: number) {
        const index = this.state.groupBy.indexOf(propertyId)
        if (index < 0) return
        this.state.groupBy.splice(index, 1)
        this.customGroups = {}
        this.computeImageOrder()
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
        this.computeImageOrder()
        if (emit) this.onResultChange.emit(this.result)
    }

    delCustomGroups(targetGroupId: number, emit?: boolean) {
        delete this.customGroups[targetGroupId]
        this.removeChildren(this.result.index[targetGroupId])
        if (this.state.sha1Mode) this.groupBySha1(this.result.index[targetGroupId])
        if (emit) {
            this.computeImageOrder()
            this.onResultChange.emit(this.result)
        }
    }

    clearCustomGroups(emit?: boolean) {
        for (let groupId of Object.keys(this.customGroups).map(Number)) {
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
        for (let group of groups) {
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
        const tagWithParents: { [id: number]: Set<number> } = {}
        if (isTag(property.type) && property.tags) {
            for (let tag of objValues(property.tags)) {
                tagWithParents[tag.id] = new Set(tag.allParents)
                tagWithParents[tag.id].add(tag.id)
            }
        }

        group.subGroupType = GroupType.Property
        const subGroups: Group[] = []

        for (const s of group.slots) {
            let value = col.readSlot(property.id, s)
            value = valueParser[property.type](value)

            let intervalEnd = undefined
            if (property.type == PropertyType.date) {
                const res = closestDate(value, option.stepSize, option.stepUnit)
                if (res) { value = res.first; intervalEnd = res.last }
            }

            let values = Array.isArray(value) ? value : [value]
            if (isTag(property.type) && values[0] !== undefined) {
                const withParents = new Set<any>()
                for (let v of values) {
                    if (!v) continue
                    for (let p of tagWithParents[v]) withParents.add(p)
                }
                values = Array.from(withParents)
            }

            for (let v of values) {
                let keyValue = v
                if (v && property.type == PropertyType.date) keyValue = keyValue.toISOString()
                const key = [...group.key, keyValue]
                const groupId = this.result.valueIndex.get(key)
                if (!this.result.index[groupId]) {
                    let propValues = [{ propertyId: property.id, value: v, valueEnd: intervalEnd, unit: option.stepUnit } as PropertyValue]
                    const newGroup = buildGroup(groupId, [], GroupType.Property)
                    newGroup.meta.propertyValues = propValues
                    newGroup.key = key
                    this.regsiterGroup(newGroup)
                    subGroups.push(newGroup)
                }
                this.result.index[groupId].slots.push(s)
            }
        }

        const children: Group[] = subGroups
        this.setChildGroup(group, children)
        if (groupBy.length > 1) {
            for (let c of children) {
                this.computePropertySubGroup(c, groupBy.slice(1), properties, tags)
            }
        }
        sortGroup(group, option)
    }

    private removeImageToGroups(group: Group) {
        const col = useColumnStore()
        for (const s of group.slots) {
            const id = col.instanceIds[s]
            if (!this.result.imageToGroups[id]) continue
            const idx = this.result.imageToGroups[id].indexOf(group.id)
            if (idx >= 0) this.result.imageToGroups[id].splice(idx, 1)
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
        const col = useColumnStore()
        this.selectImages(iterator.slots.map(s => col.instanceIds[s]))
        this.clearLastSelected()
        this.selection.lastImage = iterator.clone()
    }

    unselectImageIterator(iterator: ImageIterator) {
        const col = useColumnStore()
        this.unselectImages(iterator.slots.map(s => col.instanceIds[s]))
        this.clearLastSelected()
    }

    toggleImageIterator(iterator: ImageIterator, shift = false) {
        const col = useColumnStore()
        const selected = iterator.slots.every(s => this.selectedImages.value[col.instanceIds[s]])
        if (selected) this.unselectImageIterator(iterator)
        else this.selectImageIterator(iterator, shift)
    }

    toggleAll() {
        const iterator = this.getGroupIterator()
        this.toggleGroupIterator(iterator)
    }

    private _shiftSelect(iterator: ImageIterator) {
        if (this.selection.lastImage == undefined) return false
        const col = useColumnStore()
        let start = this.selection.lastImage.isImageBefore(iterator) ? this.selection.lastImage : iterator
        let end = start == iterator ? this.selection.lastImage : iterator

        let ids: number[] = []
        let it = start.clone()
        while (it) {
            if (end.isImageBefore(it)) break
            if (it.sha1Group) {
                ids.push(...it.sha1Group.slots.map(s => col.instanceIds[s]))
            } else {
                ids.push(col.instanceIds[it.slot])
            }
            it = it.nextImages()
        }
        if (ids.length) { this.selectImages(ids); return true }
        return false
    }

    private _shiftGroup(iterator: GroupIterator) {
        if (this.selection.lastGroup == undefined) return false
        const col = useColumnStore()
        let start = this.selection.lastGroup.isGroupBefore(iterator) ? this.selection.lastGroup : iterator
        let end = start == iterator ? this.selection.lastGroup : iterator
        let ids: number[] = []
        let it = start.clone()
        while (it) {
            if (end.isGroupBefore(it)) break
            if (it.group.slots.length) {
                ids.push(...it.group.slots.map(s => col.instanceIds[s]))
            }
            it = it.nextGroup()
        }
        if (ids.length) { this.selectImages(ids); return true }
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
        const col = useColumnStore()
        if (group.children.length == 0 || group.subGroupType == GroupType.Sha1) {
            group.view.selected = group.slots.every(s => this.selectedImages.value[col.instanceIds[s]])
        } else {
            group.view.selected = group.children.every(g => g.view.selected)
        }
        if (!group.parent) return
        this.propagateSelect(group.parent)
    }

    selectGroup(group: Group) {
        const col = useColumnStore()
        this.selectImages(group.slots.map(s => col.instanceIds[s]))
    }

    unselectGroup(group: Group) {
        const col = useColumnStore()
        this.unselectImages(group.slots.map(s => col.instanceIds[s]))
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
        const col = useColumnStore()
        const selected = !iterator.group.slots.some(s => !this.selectedImages.value[col.instanceIds[s]])
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
        let current = this.group
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

    getImageOrder() {
        return this.manager.result.imageIteratorOrder[this.groupId]?.[this.imageIdx]
    }
}
