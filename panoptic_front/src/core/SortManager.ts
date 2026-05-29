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

// ── Columnar sort core ─────────────────────────────────────────────────────
//
// SortCols is a slot-indexed struct-of-arrays: cols[k][slot] = sort key of
// property k for that slot. Float64Array for numeric types (direct typed-array
// element access, cache-line friendly), string[] for string types.
//
// Indexed by slot value (not position in the result) so the cache stays valid
// across insertions/removals without position-mapping recomputation.
// updateSortCols() refreshes only the dirty subset in O(N × P) after a data
// change, avoiding a full O(M × P) rebuild on every incremental update.

type SortCols = (Float64Array | string[])[]

function isNumericSortProp(p: Property): boolean {
    switch (p.type) {
        case PropertyType.checkbox:
        case PropertyType.color:
        case PropertyType.date:
        case PropertyType.multi_tags:
        case PropertyType.number:
        case PropertyType._height:
        case PropertyType._width:
        case PropertyType._id:
            return true
        default:
            return false
    }
}

function numericSortValue(
    slot: number, p: Property,
    col: ReturnType<typeof useColumnStore>, folders: FolderIndex
): number {
    const raw = col.readSlot(p.id, slot)
    const parser = sortParser[p.type]
    const v = parser ? parser(raw, folders) : raw
    if (v == null) return Number.NEGATIVE_INFINITY
    const n = +v
    return isNaN(n) ? Number.NEGATIVE_INFINITY : n
}

function stringSortValue(
    slot: number, p: Property,
    col: ReturnType<typeof useColumnStore>, folders: FolderIndex
): string {
    const raw = col.readSlot(p.id, slot)
    // Tag columns store number[] (tag IDs); resolve to the first tag's label.
    if (p.type === PropertyType.tag) {
        const tagLabel = (Array.isArray(raw) && raw.length > 0) ? p.tags?.[raw[0]]?.value : undefined
        return tagLabel ? tagLabel.toLocaleLowerCase() : LAST_STRING
    }
    const parser = sortParser[p.type]
    const v = parser ? parser(raw, folders) : raw
    return v != null ? String(v) : LAST_STRING
}

// Build fresh slot-indexed column arrays for all slots in the input.
// Allocates typed arrays of size maxSlot+1; useColumnStore() is hoisted
// once per call instead of once per slot.
function buildSortCols(
    slots: Int32Array, properties: Property[], maxSlot: number, folders: FolderIndex
): SortCols {
    const col = useColumnStore()
    return properties.map(p => {
        if (isNumericSortProp(p)) {
            const arr = new Float64Array(maxSlot + 1)
            // Fast path: for plain numeric columns (number, _width, _height, _id, color)
            // read directly from the Float64Array buffer — avoids readSlot + sortParser overhead.
            const raw = col.getRawBuffer(p.id)
            if (raw instanceof Float64Array) {
                for (let i = 0; i < slots.length; i++) {
                    const v = raw[slots[i]]
                    arr[slots[i]] = isNaN(v) ? Number.NEGATIVE_INFINITY : v
                }
                return arr
            }
            for (let i = 0; i < slots.length; i++) {
                arr[slots[i]] = numericSortValue(slots[i], p, col, folders)
            }
            return arr
        }
        const arr: string[] = new Array(maxSlot + 1).fill(LAST_STRING)
        for (let i = 0; i < slots.length; i++) {
            arr[slots[i]] = stringSortValue(slots[i], p, col, folders)
        }
        return arr
    })
}

// Refresh column values for a subset of slots after a data change.
// Only touches the dirty slots; everything else in cols remains valid.
function updateSortCols(
    cols: SortCols, slots: number[], properties: Property[], maxSlot: number, folders: FolderIndex
): void {
    const col = useColumnStore()
    for (let k = 0; k < properties.length; k++) {
        const p = properties[k]
        const arr = cols[k]
        if (arr instanceof Float64Array) {
            for (const s of slots) {
                if (s <= maxSlot) arr[s] = numericSortValue(s, p, col, folders)
            }
        } else {
            for (const s of slots) {
                if (s <= maxSlot) arr[s] = stringSortValue(s, p, col, folders)
            }
        }
    }
}

function compareSlotsByCols(slotA: number, slotB: number, cols: SortCols, orders: number[]): number {
    for (let k = 0; k < cols.length; k++) {
        const va = cols[k][slotA], vb = cols[k][slotB]
        if (va < vb) return -orders[k]
        if (va > vb) return orders[k]
    }
    return slotA - slotB
}

// Sort slots without a JS comparator by packing all column ranks + the original
// position index into a single Float64 per element:
//   packed[i] = sortKey(i) * n + i
// Calling Float64Array.sort() with no comparator runs native C++ TimSort —
// no JS function call overhead per comparison (vs ~1.7M calls at ~30ns each).
// Decode after sort: originalIndex = packed[j] % n, slot = slots[originalIndex].
// Returns null if values would overflow float64 safe integer range (rare; falls
// back to comparison sort).
function sortByPackedKey(slots: Int32Array, sortCols: SortCols, orders: number[]): Int32Array | null {
    const n = slots.length
    if (n === 0) return slots

    const colRanks: Uint32Array[] = []
    const numUniques: number[] = []
    let keyScale = 1

    for (let k = 0; k < sortCols.length; k++) {
        const col = sortCols[k]
        const ascending = orders[k] === 1

        const vals: any[] = new Array(n)
        if (col instanceof Float64Array) {
            for (let i = 0; i < n; i++) vals[i] = col[slots[i]]
        } else {
            for (let i = 0; i < n; i++) vals[i] = (col as string[])[slots[i]]
        }

        const unique: any[] = Array.from(new Set(vals))
        if (col instanceof Float64Array) unique.sort((a, b) => a - b)
        else unique.sort()

        const numUnique = unique.length
        // packed[i] = sortKey * n + i; check (keyScale * numUnique) * n fits in MAX_SAFE_INTEGER
        if (keyScale > Number.MAX_SAFE_INTEGER / numUnique / (n + 1)) return null
        keyScale *= numUnique

        const rankMap = new Map<any, number>()
        for (let j = 0; j < numUnique; j++) {
            rankMap.set(unique[j], ascending ? j : numUnique - 1 - j)
        }

        const ranks = new Uint32Array(n)
        for (let i = 0; i < n; i++) ranks[i] = rankMap.get(vals[i]) ?? 0
        colRanks.push(ranks)
        numUniques.push(numUnique)
    }

    // Build packed sort keys
    const packed = new Float64Array(n)
    let multiplier = 1
    for (let k = colRanks.length - 1; k >= 0; k--) {
        const ranks = colRanks[k]
        for (let i = 0; i < n; i++) packed[i] += ranks[i] * multiplier
        multiplier *= numUniques[k]
    }
    // Embed original position as tiebreaker: packed[i] = sortKey * n + i
    for (let i = 0; i < n; i++) packed[i] = packed[i] * n + i

    // Native typed-array sort — no JS comparator, runs in C++
    packed.sort()

    // Decode: packed[j] % n is the original position index
    const result = new Int32Array(n)
    for (let i = 0; i < n; i++) result[i] = slots[packed[i] % n]
    return result
}

// Binary-search the insertion point for slot within sorted[startIndex..end].
// Reads sort keys from slot-indexed cols — no object allocation per step.
function binaryFindSlotIndex(
    sorted: Int32Array, slot: number, startIndex: number,
    cols: SortCols, orders: number[]
): number {
    if (startIndex >= sorted.length) return sorted.length
    let lo = startIndex, hi = sorted.length
    let dist = hi - lo
    while (dist > 10) {
        const center = lo + (dist >> 1)
        const cmp = compareSlotsByCols(slot, sorted[center], cols, orders)
        if (cmp === 0) return center
        if (cmp < 0) hi = center + 1
        else lo = center
        dist = hi - lo
    }
    for (let i = lo; i < hi; i++) {
        if (compareSlotsByCols(slot, sorted[i], cols, orders) < 0) return i
    }
    return hi
}

// Merge-insert insertSlots (pre-sorted by cols) into old sorted result,
// filtering out removed and re-inserted (updated) slots from old.
// Pre-allocates the maximum possible result size to avoid any dynamic push().
function mergeInsertSorted(
    old: Int32Array, insertSlots: Int32Array,
    removedSet: Set<number>, updatedSet: Set<number>,
    cols: SortCols, orders: number[]
): Int32Array {
    const buf = new Int32Array(old.length + insertSlots.length)
    let resLen = 0, oldIdx = 0, nowIdx = 0

    while (nowIdx < insertSlots.length) {
        const insertAt = binaryFindSlotIndex(old, insertSlots[nowIdx], oldIdx, cols, orders)
        for (let i = oldIdx; i < insertAt; i++) {
            const s = old[i]
            if (!updatedSet.has(s) && !removedSet.has(s)) buf[resLen++] = s
            oldIdx++
        }
        buf[resLen++] = insertSlots[nowIdx++]
    }
    for (let i = oldIdx; i < old.length; i++) {
        const s = old[i]
        if (!updatedSet.has(s) && !removedSet.has(s)) buf[resLen++] = s
    }
    return buf.slice(0, resLen)
}

// ── SortManager ────────────────────────────────────────────────────────────

export class SortManager {
    state: SortState
    result: SortResult

    onResultChange: EventEmitter
    onStateChange: EventEmitter

    // Slot-indexed column arrays cached after sort() for use in updateSelection().
    // _sortCols[k][slot] = sort key of property k for that slot.
    // Refreshed incrementally by updateSortCols() on data changes.
    private _sortCols: SortCols | null = null
    private _sortColsMaxSlot = 0

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
        this._sortCols = null
    }

    async sort(slots: Int32Array, emit?: boolean): Promise<SortResult> {
        await this._ensureColumns()
        console.time('Sort')

        const data = useDataStore()
        const properties = this.state.sortBy.map(id => data.properties[id])
        const orders = this.state.sortBy.map(id =>
            this.state.options[id].direction === SortDirection.Ascending ? 1 : -1)

        // Single pass to find max slot for typed-array allocation
        let maxSlot = 0
        for (let i = 0; i < slots.length; i++) if (slots[i] > maxSlot) maxSlot = slots[i]

        // Build and cache slot-indexed columns (one sequential pass per property)
        this._sortCols = buildSortCols(slots, properties, maxSlot, data.folders)
        this._sortColsMaxSlot = maxSlot

        // Sort using packed-key native sort (no JS comparator — pure C++ TimSort).
        // Falls back to comparison sort only when float64 range would overflow.
        let sorted: Int32Array
        if (properties.length === 0) {
            sorted = slots.slice()
        } else {
            sorted = sortByPackedKey(slots, this._sortCols, orders)
            ?? (() => {
                const s = slots.slice()
                if (properties.length === 1) {
                    const col0 = this._sortCols[0], ord0 = orders[0]
                    s.sort((a, b) => { const d = col0[a] < col0[b] ? -ord0 : col0[a] > col0[b] ? ord0 : 0; return d || a - b })
                } else {
                    const cols = this._sortCols
                    s.sort((a, b) => compareSlotsByCols(a, b, cols, orders))
                }
                return s
            })()
        }

        this.result.order = {}
        for (let i = 0; i < sorted.length; i++) this.result.order[sorted[i]] = i
        this.result.slots = sorted

        console.timeEnd('Sort')
        if (emit) this.onResultChange.emit(this.result)
        return this.result
    }

    // updated/removed are instance IDs from FilterManager.updateSelection.
    // Converts to slots once, then operates entirely on slot indices.
    updateSelection(updated: Set<number>, removed: Set<number>): SortResult {

        const col = useColumnStore()
        const data = useDataStore()
        const properties = this.state.sortBy.map(id => data.properties[id])
        const orders = this.state.sortBy.map(id =>
            this.state.options[id].direction === SortDirection.Ascending ? 1 : -1)

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

        // Check if any updated slot exceeds the cached column range
        let needsRebuild = !this._sortCols
        if (!needsRebuild) {
            for (const s of updatedSlots) {
                if (s > this._sortColsMaxSlot) { needsRebuild = true; break }
            }
        }

        if (needsRebuild) {
            // Safety net: build from scratch using all currently-relevant slots
            let maxSlot = this._sortColsMaxSlot
            for (const s of updatedSlots) if (s > maxSlot) maxSlot = s
            const allSlots = new Int32Array(this.result.slots.length + updatedSlots.size)
            let j = 0
            for (let i = 0; i < this.result.slots.length; i++) allSlots[j++] = this.result.slots[i]
            for (const s of updatedSlots) allSlots[j++] = s
            this._sortCols = buildSortCols(allSlots, properties, maxSlot, data.folders)
            this._sortColsMaxSlot = maxSlot
        } else {
            // Refresh only the dirty slots in the cached columns — O(N × P)
            updateSortCols(this._sortCols, [...updatedSlots], properties, this._sortColsMaxSlot, data.folders)
        }

        // Sort the updated slots by current criteria, then merge-insert into result
        const cols = this._sortCols
        let insertArr = sortByPackedKey(Int32Array.from(updatedSlots), cols, orders)
        if (!insertArr) {
            insertArr = Int32Array.from(updatedSlots)
            insertArr.sort((a, b) => compareSlotsByCols(a, b, cols, orders))
        }

        const res = mergeInsertSorted(this.result.slots, insertArr, removedSlots, updatedSlots, cols, orders)
        this.result.slots = res
        this.result.order = {}
        for (let i = 0; i < res.length; i++) this.result.order[res[i]] = i


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
        this._sortCols = null  // invalidate — caller must re-sort
        this.onStateChange.emit()
    }

    delSort(propertyId: number) {
        const index = this.state.sortBy.indexOf(propertyId)
        if (index < 0) return
        this.state.sortBy.splice(index, 1)
        this._sortCols = null  // invalidate — caller must re-sort
        this.onStateChange.emit()
    }

    verifyState(properties: PropertyIndex) {
        this.state.sortBy = this.state.sortBy.filter(id => properties[id] && properties[id].id != deletedID)
        Object.keys(this.state.options)
            .filter(id => !properties[Number(id)] || properties[Number(id)].id == deletedID)
            .forEach(id => delete this.state.options[Number(id)])
        this._sortCols = null  // invalidate — caller must re-sort
    }
}
