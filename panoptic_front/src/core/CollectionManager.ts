/**
 * CollectionManager
 * Connects FilterManager → SortManager → GroupManager.
 * All three managers operate on Int32Array of column-store slot indices.
 * Instance objects are never allocated in this pipeline.
 */

import { CollectionState } from "@/data/models";
import { FilterContext, FilterManager, FilterState } from "./FilterManager";
import { SortManager, SortState } from "./SortManager";
import { GroupManager, GroupState } from "./GroupManager";
import { EventEmitter } from "@/utils/utils";
import { useDataStore } from "@/data/dataStore";
import { useColumnStore } from "@/data/columnStore";
import { Reactive, reactive, watch, WatchStopHandle } from "vue";

export interface RunCollectionState {
    isDirty: boolean
    active: boolean
}

export function createCollectionState(): CollectionState {
    return { autoReload: true }
}

// Recompute entrypoints, most → least expensive. A state change maps to one of
// these; the CollectionManager coalesces concurrent requests to the most
// expensive pending one (Pillar B).
export type ReloadKind = 'filter' | 'sort' | 'group' | 'sortGroups'
const RELOAD_PRIORITY: Record<ReloadKind, number> = { filter: 4, sort: 3, group: 2, sortGroups: 1 }
const RELOAD_DEBOUNCE_MS = 50

function maxReloadKind(a: ReloadKind | null, b: ReloadKind): ReloadKind {
    if (!a) return b
    return RELOAD_PRIORITY[a] >= RELOAD_PRIORITY[b] ? a : b
}

export class CollectionManager {
    state: CollectionState
    filterManager: FilterManager
    sortManager: SortManager
    groupManager: GroupManager

    runState: Reactive<RunCollectionState>

    onStateChange: EventEmitter

    // Pillar B orchestration state
    private runToken = 0
    private pendingKind: ReloadKind | null = null
    private reloadTimer: ReturnType<typeof setTimeout> | null = null

    // Lifecycle: stop handles for the config watches + the bound data listener,
    // so a collection can be torn down when its last view stops referencing it
    // (bind/unbind toggle in TabManager).
    private stops: WatchStopHandle[] = []
    private boundUpdateInstances = this.updateInstances.bind(this)

    constructor(state?: CollectionState, filterState?: FilterState, sortState?: SortState, groupState?: GroupState) {
        const data = useDataStore()
        const col = useColumnStore()
        const ctx: FilterContext = { properties: data.properties, tags: data.tags, folders: data.folders }
        this.filterManager = new FilterManager(ctx, filterState)
        this.sortManager = new SortManager(sortState)
        this.groupManager = new GroupManager(groupState)
        if (state) {
            this.state = state as CollectionState
        } else {
            this.state = reactive({ autoReload: true })
        }

        this.runState = reactive({ isDirty: false, active: true })

        // Pipeline ordering is inline in update()/runReload() (filter→sort→group);
        // the old onResultChange cascade (onFilter/onSort/onGroup) is removed
        // (note §6, P-A, step 3). filter()/sort() were only ever called with
        // emit=false, so those listeners never fired.
        data.onChange.addListener(this.boundUpdateInstances)

        // Pillar B: the CollectionManager is the single orchestrator. It watches
        // each persisted state slice and maps it to the right recompute
        // entrypoint, coalesced + active/autoReload-gated + debounced. This
        // generalises the old `filterManager.onStateChange -> setDirty` wiring
        // (one slice) to all three managers. State mutations still go through the
        // managers' setters (which keep id/index bookkeeping); only the recompute
        // trigger moves here. `sha1Mode` is intentionally not watched — it does an
        // incremental restructure inside `setSha1Mode`.
        this.stops.push(watch(() => this.filterManager.state,        () => this.requestReload('filter'),     { deep: true }))
        this.stops.push(watch(() => this.sortManager.state,          () => this.requestReload('sort'),       { deep: true }))
        this.stops.push(watch(() => this.groupManager.state.groupBy, () => this.requestReload('group'),      { deep: true }))
        this.stops.push(watch(() => this.groupManager.state.options, () => this.requestReload('sortGroups'), { deep: true }))
        // stepSize/stepUnit changes require a full group rebuild (buckets change), not just a re-sort
        this.stops.push(watch(
            () => this.groupManager.state.groupBy.map(id => {
                const o = this.groupManager.state.options[id]
                return `${o?.stepSize}-${o?.stepUnit}`
            }).join(','),
            () => this.requestReload('group')
        ))

        // Trigger full update whenever the column store finishes (re)loading.
        // immediate:true handles the case where a tab is created after init completes.
        this.stops.push(watch(() => col.isReady, (ready) => {
            if (ready) this.update()
        }, { immediate: true }))

        this.onStateChange = new EventEmitter()
    }

    verifyState() {
        const data = useDataStore()
        this.filterManager.verifyState(data.properties, data.folders)
        this.sortManager.verifyState(data.properties)
        this.groupManager.verifyState(data.properties)
    }

    setAutoReload(value: boolean) {
        this.state.autoReload = value
        this.onStateChange.emit()
    }

    async setDirty(instanceIds?: Set<number>) {
        this.runState.isDirty = true
        if (!this.runState.active) return

        if (this.state.filterBySelection) {
            const col = useColumnStore()
            for (const id of Array.from(instanceIds)) {
                if (!col.isSelectedId(id)) instanceIds.delete(id)
            }
        }

        if (this.state.autoReload) {
            if (instanceIds) {
                const filterUpdate = await this.filterManager.updateSelection(instanceIds)
                this.sortManager.updateSelection(filterUpdate.updated, filterUpdate.removed)
                if (this.groupManager.result.root) {
                    this.groupManager.updateSelection(filterUpdate.updated, filterUpdate.removed)
                } else {
                    this.groupManager.group(this.sortManager.result.slots, true)
                }
                this.runState.isDirty = false
            } else {
                this.update()
            }
        }
    }

    async update() {
        const col = useColumnStore()
        if (!col.isReady) return

        // Latest-wins guard: if a newer recompute starts while this one is
        // awaiting (slow column load / plugin query), the stale run bails before
        // writing results.
        const token = ++this.runToken

        const count       = col.slotCount()
        const deleted     = col.deletedMask()
        const instanceIds = col.instanceIds()

        // Build Int32Array of active slots — no Instance objects created.
        let slots: Int32Array
        if (this.state.instances) {
            const allowed = new Set(this.state.instances)
            const sub: number[] = []
            for (let s = 0; s < count; s++) {
                if (!deleted[s] && allowed.has(instanceIds[s])) sub.push(s)
            }
            slots = new Int32Array(sub)
        } else {
            const all: number[] = []
            for (let s = 0; s < count; s++) {
                if (!deleted[s]) all.push(s)
            }
            slots = new Int32Array(all)
        }

        if (this.state.filterBySelection) {
            const sel: number[] = []
            for (let i = 0; i < slots.length; i++) {
                if (col.isSelected(slots[i])) sel.push(slots[i])
            }
            slots = new Int32Array(sel)
        }

        const filterRes = await this.filterManager.filter(slots)
        if (token !== this.runToken) return
        const sortRes   = await this.sortManager.sort(filterRes.slots)
        if (token !== this.runToken) return
        this.groupManager.group(sortRes.slots, true)
        this.runState.isDirty = false
    }

    // Pillar B: single entry for state-driven recompute. Coalesces concurrent
    // requests, gates on active + autoReload, and debounces hot paths (typing,
    // slider drags). Background tabs only mark dirty and recompute on activate
    // (via TabManager.update on selectMainTab).
    requestReload(kind: ReloadKind) {
        this.runState.isDirty = true
        if (!this.runState.active || !this.state.autoReload) return
        this.pendingKind = maxReloadKind(this.pendingKind, kind)
        if (this.reloadTimer) clearTimeout(this.reloadTimer)
        this.reloadTimer = setTimeout(() => {
            const kind = this.pendingKind
            this.pendingKind = null
            this.reloadTimer = null
            if (kind) this.runReload(kind)
        }, RELOAD_DEBOUNCE_MS)
    }

    private async runReload(kind: ReloadKind) {
        if (kind === 'filter') {
            await this.update()
            return
        }
        const token = ++this.runToken
        if (kind === 'sort') {
            const sortRes = await this.sortManager.sort(this.filterManager.result.slots)
            if (token !== this.runToken) return
            this.groupManager.group(sortRes.slots, true)
            this.runState.isDirty = false
            return
        }
        if (kind === 'group') {
            this.groupManager.group(this.sortManager.result.slots, true)
            this.runState.isDirty = false
            return
        }
        if (kind === 'sortGroups') {
            this.groupManager.sortGroups(true)
        }
    }

    updateInstances(instanceIds: Set<number>) {
        this.setDirty(instanceIds)
    }

    // Tear down all reactive subscriptions. Called when the last view that
    // referenced this collection stops doing so (TabManager.pruneCollections).
    dispose() {
        this.stops.forEach(stop => stop())
        this.stops = []
        useDataStore().onChange.removeListener(this.boundUpdateInstances)
        if (this.reloadTimer) { clearTimeout(this.reloadTimer); this.reloadTimer = null }
        this.runState.active = false
    }
}
