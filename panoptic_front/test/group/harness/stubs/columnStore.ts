/**
 * Headless stand-in for @/data/stores/columnStore.
 *
 * The real store is a pinia store that pulls in the router and axios, so the suite aliases this
 * module over it (see build.mjs). It keeps the surface the group engine actually touches:
 * the slot table (ids / sha1s / slotMap), raw column buffers so a real group() can bucket by a
 * property value, and the namespaced selection masks GroupNavigator writes to.
 */

import { stripTagIds } from '@/data/lib/columns'

type Column = any[]

const state = {
    ids: new Int32Array(0),
    sha1s: [] as (string | null)[],
    cols: {} as { [propId: number]: Column },
    slotMap: new Map<number, number>(),
    epoch: 1,
    masks: new Map<string, Set<number>>(),
    ticks: {} as { [ns: string]: number },
}

const maskOf = (ns: string) => {
    let m = state.masks.get(ns)
    if (!m) { m = new Set<number>(); state.masks.set(ns, m) }
    return m
}

export const columnStub = {
    // ── slot table ───────────────────────────────────────────────────────────
    slotMap: state.slotMap,
    instanceIds() { return state.ids },
    sha1s() { return state.sha1s },
    slotCount() { return state.ids.length },
    slotEpoch() { return state.epoch },

    // ── columns ──────────────────────────────────────────────────────────────
    getRawBuffer(propId: number) { return state.cols[propId] },
    // Faithful to the real store, and this divergence is the whole point of A1: a numeric
    // column stores "unset" as NaN in the buffer getRawBuffer hands out, while readSlot maps
    // that same slot to null. The full rebuild reads the buffer, the incremental update reads
    // readSlot, so both spellings must key to the same group.
    readSlot(propId: number, slot: number) {
        const v = state.cols[propId]?.[slot]
        if (v === undefined) return null
        if (typeof v === 'number' && Number.isNaN(v)) return null
        return v
    },
    async requireFullColumn(_propId: number) { /* everything is already in memory here */ },
    async requireTagInverted(_propId: number) { },

    // ── selection ────────────────────────────────────────────────────────────
    ensureNamespace(ns: string) { maskOf(ns); if (state.ticks[ns] === undefined) state.ticks[ns] = 0 },
    clearSelection(ns = 'global') { maskOf(ns).clear() },
    select(slots: number[], ns = 'global') { const m = maskOf(ns); for (const s of slots) m.add(s) },
    deselect(slots: number[], ns = 'global') { const m = maskOf(ns); for (const s of slots) m.delete(s) },
    selectIds(ids: number[], ns = 'global') {
        const m = maskOf(ns)
        for (const id of ids) { const s = state.slotMap.get(id); if (s !== undefined) m.add(s) }
    },
    deselectIds(ids: number[], ns = 'global') {
        const m = maskOf(ns)
        for (const id of ids) { const s = state.slotMap.get(id); if (s !== undefined) m.delete(s) }
    },
    isSelected(slot: number, ns = 'global') { return maskOf(ns).has(slot) },
    isSelectedId(id: number, ns = 'global') {
        const s = state.slotMap.get(id)
        return s === undefined ? false : maskOf(ns).has(s)
    },
    selectedCount(ns = 'global') { return maskOf(ns).size },
    selectionTick(ns = 'global') { return state.ticks[ns] ?? 0 },
    selection: {},
}

// ── test-side controls ───────────────────────────────────────────────────────

/** Reset the whole store: `n` slots with instance ids 1000..1000+n and sha1s 'h0'..'hn'. */
export function setSlots(n: number) {
    state.ids = new Int32Array(Array.from({ length: n }, (_, i) => 1000 + i))
    state.sha1s = Array.from({ length: n }, (_, i) => 'h' + i)
    state.cols = {}
    state.slotMap.clear()
    for (let i = 0; i < n; i++) state.slotMap.set(1000 + i, i)
    state.masks.clear()
    state.ticks = {}
    state.epoch++
}

/** Reset the store from an explicit sha1-per-slot list (duplicates and nulls welcome). */
export function setSha1s(sha1s: (string | null)[]) {
    setSlots(sha1s.length)
    state.sha1s = sha1s.slice()
}

export function setColumn(propId: number, values: any[]) { state.cols[propId] = values.slice() }
export function setValue(propId: number, slot: number, value: any) { state.cols[propId][slot] = value }
export function selectedSlots(ns = 'global') { return [...maskOf(ns)].sort((a, b) => a - b) }
export function instanceIdOf(slot: number) { return state.ids[slot] }

export function useColumnStore() { return columnStub as any }

/**
 * Append `n` slots, the way the real store's addInstances does: ids continue where the last
 * batch stopped, the masks and columns are grown in place, and the epoch is NOT bumped (only a
 * project reset re-mints slots, and that is what invalidates a cluster container).
 * Returns the new slot indices.
 */
export function addSlots(n: number, sha1s?: (string | null)[]): number[] {
    const start = state.ids.length
    const ids = new Int32Array(start + n)
    ids.set(state.ids)
    const added: number[] = []
    for (let i = 0; i < n; i++) {
        const slot = start + i
        const id = 1000 + slot
        ids[slot] = id
        state.slotMap.set(id, slot)
        state.sha1s.push(sha1s?.[i] ?? ('h' + slot))
        added.push(slot)
    }
    state.ids = ids
    for (const key of Object.keys(state.cols)) state.cols[Number(key)].length = start + n
    return added
}

/** setValue, but it mints the column when the property has never been written to. */
export function writeValue(propId: number, slot: number, value: any) {
    if (!state.cols[propId]) state.cols[propId] = new Array(state.ids.length).fill(undefined)
    state.cols[propId][slot] = value
}

/**
 * The column-side half of a tag delete, through the REAL `stripTagIds` the store calls — so the
 * D2 tests exercise the production scrub rather than a copy of it. Returns the instance ids
 * whose value changed, which is what removeTagIds hands dataStore for the dirty set.
 */
export function stripTagsInStub(propId: number, tagIds: number[]): number[] {
    const col = state.cols[propId]
    if (!col) return []
    const slots = stripTagIds(col as any, state.ids.length, new Set(tagIds))
    return slots.map(s => state.ids[s])
}
