/**
 * SortManager — sorts instances by multiple properties.
 *
 * Operates on Int32Array of column-store slot indices.
 * ImageOrder is keyed by slot (not instance ID).
 *
 * Column contract: sort() loads every sortBy column before computing.
 * updateSelection() assumes those columns are already loaded.
 */

import { useDataStore } from "@/data/dataStore"
import { useColumnStore } from "@/data/columnStore"
import { deletedID, FolderIndex, PropertyIndex, Property } from "@/data/models"
import { PropertyType } from "@/data/models"
import { EventEmitter } from "@/utils/utils"
import { reactive } from "vue"

const LAST_STRING = 'zzzzzzzzzzzzzzzzzzzzzzzzzzzz'

export enum SortDirection {
    Ascending = 1,
    Descending = -1
}

export interface SortOption {
    direction?: SortDirection
}

export interface SortState {
    sortBy: number[]
    options: { [propId: number]: SortOption }
}

// Keyed by slot index (not instance ID).
export type ImageOrder = { [slot: number]: number }

export interface SortResult {
    order: ImageOrder
    slots: Int32Array
}

interface SortableImage {
    slot: number
    values: any[]
}

export function createSortState(): SortState {
    return reactive({ sortBy: [], options: {} })
}

export function buildSortOption(): SortOption {
    return { direction: SortDirection.Ascending }
}

export const sortParser: { [type in PropertyType]?: any } = {
    [PropertyType.checkbox]:  (x?: boolean) => (!x ? 0 : 1),
    [PropertyType.color]:     (x?: number)  => (isNaN(x) ? -1 : x),
    [PropertyType.date]:      (x?: Date)    => (!x ? 0 : new Date(x).getTime()),
    [PropertyType.multi_tags]:(x?: number[])=> (!x ? 0 : x.length),
    [PropertyType.number]:    (x?: number)  => (x == undefined ? Number.NEGATIVE_INFINITY : x),
    [PropertyType.path]:      (x?: string)  => (!x ? LAST_STRING : x.toLocaleLowerCase()),
    [PropertyType.string]:    (x?: string)  => (!x ? LAST_STRING : x.toLocaleLowerCase()),
    [PropertyType.tag]:       (x?: string)  => (!x ? LAST_STRING : x.toLocaleLowerCase()),
    [PropertyType.url]:       (x?: string)  => (!x ? LAST_STRING : x.toLocaleLowerCase()),
    [PropertyType._ahash]:    (x: string)   => x,
    [PropertyType._sha1]:     (x: string)   => x,
    [PropertyType._folders]:  (x: number, folders: FolderIndex) => folders[x]?.name,
    [PropertyType._height]:   (x: number)   => x,
    [PropertyType._width]:    (x: number)   => x,
    [PropertyType._id]:       (x: number)   => x,
}

// Slot is the direct column index — no slotMap lookup needed.
function readSortValue(slot: number, property: Property, folders: FolderIndex): any {
    const col = useColumnStore()
    let value = col.readSlot(property.id, slot)

    if (property.type == PropertyType.tag) {
        value = (Array.isArray(value) && value.length > 0)
            ? property.tags?.[value[0]]?.value
            : undefined
    }
    return sortParser[property.type]?.(value, folders) ?? value
}

function buildSortable(slots: number[], properties: Property[]): SortableImage[] {
    const data = useDataStore()
    return slots.map(s => ({
        slot: s,
        values: properties.map(p => readSortValue(s, p, data.folders)),
    }))
}

function compareSortable(a: SortableImage, b: SortableImage, orders: number[]): number {
    for (let i = 0; i < a.values.length; i++) {
        if (a.values[i] == b.values[i]) continue
        return (a.values[i] < b.values[i] ? -1 : 1) * orders[i]
    }
    return a.slot - b.slot
}

function runSort(sortable: SortableImage[], orders: number[]) {
    sortable.sort((a, b) => compareSortable(a, b, orders))
}

function insertSort(
    old: Int32Array,
    updatedSlots: Set<number>,
    removedSlots: Set<number>,
    properties: Property[],
    orders: number[]
): Int32Array {
    const updatedSortable = buildSortable([...updatedSlots], properties)
    runSort(updatedSortable, orders)

    const res: number[] = []
    let oldIndex = 0
    let nowIndex = 0

    while (nowIndex < updatedSortable.length) {
        const insertAt = binaryFindIndex(old, updatedSortable[nowIndex], oldIndex, properties, orders)
        for (let i = oldIndex; i < insertAt; i++) {
            const s = old[i]
            if (!updatedSlots.has(s) && !removedSlots.has(s)) res.push(s)
            oldIndex++
        }
        res.push(updatedSortable[nowIndex].slot)
        nowIndex++
    }
    for (let i = oldIndex; i < old.length; i++) {
        const s = old[i]
        if (!updatedSlots.has(s) && !removedSlots.has(s)) res.push(s)
    }
    return new Int32Array(res)
}

function binaryFindIndex(target: Int32Array, elem: SortableImage, startIndex: number, properties: Property[], orders: number[]): number {
    if (startIndex >= target.length) return startIndex
    let lo = startIndex
    let hi = target.length
    let dist = hi - lo
    while (dist > 10) {
        const center = Math.floor(lo + dist / 2)
        const cmp = compareSortable(elem, buildSortable([target[center]], properties)[0], orders)
        if (cmp == 0) return center
        if (cmp < 0) hi = center + 1
        else lo = center
        dist = hi - lo
    }
    for (let i = lo; i < hi; i++) {
        if (compareSortable(elem, buildSortable([target[i]], properties)[0], orders) < 0) return i
    }
    return target.length
}

export class SortManager {
    state: SortState
    result: SortResult

    onResultChange: EventEmitter
    onStateChange: EventEmitter

    constructor(state?: SortState) {
        this.onResultChange = new EventEmitter()
        this.onStateChange = new EventEmitter()
        this.state = createSortState()
        if (state) Object.assign(this.state, state)
        this.result = { slots: new Int32Array(0), order: {} }
    }

    // ── Column requirements ────────────────────────────────────────────────

    getRequiredColumns(): number[] {
        return [...this.state.sortBy]
    }

    private async _ensureColumns(): Promise<void> {
        const col = useColumnStore()
        await Promise.all(this.getRequiredColumns().map(id => col.requireFullColumn(id)))
    }

    // ── Public API ─────────────────────────────────────────────────────────

    clear() {
        this.result = { slots: new Int32Array(0), order: {} }
    }

    async sort(slots: Int32Array, emit?: boolean): Promise<SortResult> {
        await this._ensureColumns()
        console.time('Sort')

        const data = useDataStore()
        const properties = this.state.sortBy.map(id => data.properties[id])
        const orders = this.state.sortBy.map(id =>
            this.state.options[id].direction == SortDirection.Ascending ? 1 : -1)

        const sortable = buildSortable(Array.from(slots), properties)
        runSort(sortable, orders)

        const newSlots = new Int32Array(sortable.length)
        this.result.order = {}
        for (let i = 0; i < sortable.length; i++) {
            newSlots[i] = sortable[i].slot
            this.result.order[sortable[i].slot] = i
        }
        this.result.slots = newSlots
        console.timeEnd('Sort')
        if (emit) this.onResultChange.emit(this.result)
        return this.result
    }

    // updated/removed are instance IDs from FilterManager.updateSelection.
    // Converts to slots once, then operates entirely on slot indices.
    updateSelection(updated: Set<number>, removed: Set<number>): SortResult {
        console.time('SortUpdate')
        const col = useColumnStore()
        const data = useDataStore()
        const properties = this.state.sortBy.map(id => data.properties[id])
        const orders = this.state.sortBy.map(id =>
            this.state.options[id].direction == SortDirection.Ascending ? 1 : -1)

        const updatedSlots = new Set<number>()
        for (const id of updated) {
            const s = col.slotMap.get(id)
            if (s !== undefined) updatedSlots.add(s)
        }
        const removedSlots = new Set<number>()
        for (const id of removed) {
            const s = col.slotMap.get(id)
            if (s !== undefined) removedSlots.add(s)
        }

        const res = insertSort(this.result.slots, updatedSlots, removedSlots, properties, orders)
        this.result.slots = res
        this.result.order = {}
        for (let i = 0; i < res.length; i++) {
            this.result.order[res[i]] = i
        }
        console.timeEnd('SortUpdate')
        return this.result
    }

    async update(emit?: boolean): Promise<void> {
        await this.sort(this.result.slots)
        if (emit) this.onResultChange.emit(this.result)
    }

    setSort(propertyId: number, option?: SortOption) {
        if (option) this.state.options[propertyId] = option
        else if (!this.state.options[propertyId]) this.state.options[propertyId] = buildSortOption()
        if (!this.state.sortBy.includes(propertyId)) this.state.sortBy.push(propertyId)
        this.onStateChange.emit()
    }

    delSort(propertyId: number) {
        const index = this.state.sortBy.indexOf(propertyId)
        if (index < 0) return
        this.state.sortBy.splice(index, 1)
        this.onStateChange.emit()
    }

    verifyState(properties: PropertyIndex) {
        this.state.sortBy = this.state.sortBy.filter(id => properties[id] && properties[id].id != deletedID)
        Object.keys(this.state.options)
            .filter(id => !properties[Number(id)] || properties[Number(id)].id == deletedID)
            .forEach(id => delete this.state.options[Number(id)])
    }
}
