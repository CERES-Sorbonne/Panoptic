/**
 * CollectionManager
 * Connects FilterManager → SortManager → GroupManager.
 * All three managers operate on Int32Array of column-store slot indices.
 * Instance objects are never allocated in this pipeline.
 */

import { CollectionState } from "@/data/models";
import { FilterContext, FilterManager, FilterState } from "./FilterManager";
import { SortManager, SortState } from "./SortManager";
import { GroupManager, GroupState, Group, GroupIteratorOptions, ClusterRequest, GroupInspector } from "./GroupManager";
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

export class CollectionManager implements GroupInspector {
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
    // In-flight data-driven reflow (see updateInstances / settle).
    private pending: Promise<void> | null = null

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

    // ── Inspection API ─────────────────────────────────────────────────────────
    // CollectionManager is the object views use to inspect a collection. These delegate to the
    // GroupManager / ClusterManager so components no longer reach through `.groupManager`.
    // (`groupState` is named to avoid clashing with `this.state`, the CollectionState.)

    get result() { return this.groupManager.result }
    get clusters() { return this.groupManager.clusters }
    get version() { return this.groupManager.version }
    get groupState(): GroupState { return this.groupManager.state }
    get selectionNamespace() { return this.groupManager.selectionNamespace }

    hasResult() { return this.groupManager.hasResult() }
    // Publish view-state changes made without `emit` (batched open/close in the group lines).
    emitResult() { return this.groupManager.emitResult() }
    getRequiredColumns() { return this.groupManager.getRequiredColumns() }

    // Iteration
    getGroupIterator(groupId?: number, options?: GroupIteratorOptions) { return this.groupManager.getGroupIterator(groupId, options) }
    getImageIterator(groupId?: number, imageIdx?: number, options?: GroupIteratorOptions) { return this.groupManager.getImageIterator(groupId, imageIdx, options) }
    findImageIterator(groupId: number, imageId: number) { return this.groupManager.findImageIterator(groupId, imageId) }

    // Grouping state
    setGroupOption(...args: Parameters<GroupManager['setGroupOption']>) { return this.groupManager.setGroupOption(...args) }
    delGroupOption(...args: Parameters<GroupManager['delGroupOption']>) { return this.groupManager.delGroupOption(...args) }
    setSha1Mode(value: boolean, emit?: boolean) { return this.groupManager.setSha1Mode(value, emit) }
    sortGroups(emit?: boolean) { return this.groupManager.sortGroups(emit) }

    // Open / close — completes the inspection API so views never need `.groupManager`.
    toggleGroup(groupId: number, emit?: boolean) { return this.groupManager.toggleGroup(groupId, emit) }
    openGroup(groupId: number, emit?: boolean) { return this.groupManager.openGroup(groupId, emit) }
    closeGroup(groupId: number, emit?: boolean) { return this.groupManager.closeGroup(groupId, emit) }

    // Selection
    setSelectionNamespace(ns: string) { return this.groupManager.setSelectionNamespace(ns) }
    clearSelection() { return this.groupManager.clearSelection() }
    toggleAll() { return this.groupManager.toggleAll() }
    toggleGroupIterator(...args: Parameters<GroupManager['toggleGroupIterator']>) { return this.groupManager.toggleGroupIterator(...args) }
    toggleImageIterator(...args: Parameters<GroupManager['toggleImageIterator']>) { return this.groupManager.toggleImageIterator(...args) }
    selectImages(imageIds: number[]) { return this.groupManager.selectImages(imageIds) }
    unselectImages(imageIds: number[]) { return this.groupManager.unselectImages(imageIds) }
    // Reactive in a template/computed (reads the namespace's selection tick internally).
    isGroupSelected(group: Group) { return this.groupManager.isGroupSelected(group) }

    // Cluster / custom-group ops (delegate through to ClusterManager)
    addCustomGroups(targetGroupId: number, groups: Group[], emit?: boolean) { return this.groupManager.addCustomGroups(targetGroupId, groups, emit) }
    moveImagesToGroup(fromGroupId: number, toGroupId: number, instanceIds: number[], emit = true) { return this.groupManager.moveImagesToGroup(fromGroupId, toGroupId, instanceIds, emit) }
    renameGroup(groupId: number, name: string, emit = true) { return this.groupManager.renameGroup(groupId, name, emit) }
    delCustomGroups(targetGroupId: number, emit?: boolean) { return this.groupManager.delCustomGroups(targetGroupId, emit) }
    clearCustomGroups(emit?: boolean) { return this.groupManager.clearCustomGroups(emit) }
    // Cluster a group. Fire-and-forget from the caller's point of view: the ClusterManager owns
    // the run, so the result lands even if the button that started it is long unmounted.
    cluster(targetGroupId: number, req: ClusterRequest) { return this.groupManager.cluster(targetGroupId, req) }
    isClustering(groupId: number) { return this.groupManager.isClustering(groupId) }
    get onCluster() { return this.groupManager.clusters.onCluster }

    split(groupId: number, groups: Group[], emit = true) { return this.groupManager.split(groupId, groups, emit) }
    merge(groupIds: number[], emit = true) { return this.groupManager.merge(groupIds, emit) }
    delete(groupId: number, emit = true) { return this.groupManager.delete(groupId, emit) }
    // Cluster the empty bucket (adds a real leftover group) / drain an assigned pile — O(delta).
    clusterEmptyBucket(bucketId: number, groups: Group[], emit = true) { return this.groupManager.clusters.clusterEmptyBucket(bucketId, groups, emit) }
    drainCluster(groupId: number, instanceIds: number[], emit = true) { return this.groupManager.clusters.drain(groupId, instanceIds, emit) }

    setAutoReload(value: boolean) {
        this.state.autoReload = value
        this.onStateChange.emit()
    }

    async setDirty(instanceIds?: Set<number>) {
        this.runState.isDirty = true
        if (!this.runState.active) return

        // Narrow to the selection on a copy: the payload is shared with every other
        // collection listening to the same data change, so it must never be mutated here.
        let dirty = instanceIds
        if (dirty && this.state.filterBySelection) {
            const col = useColumnStore()
            const kept = new Set<number>()
            for (const id of dirty) if (col.isSelectedId(id)) kept.add(id)
            dirty = kept
        }

        if (this.state.autoReload) {
            if (dirty) {
                const filterUpdate = await this.filterManager.updateSelection(dirty)
                this.sortManager.updateSelection(filterUpdate.updated, filterUpdate.removed)
                if (this.groupManager.result.root) {
                    this.groupManager.updateSelection(filterUpdate.updated, filterUpdate.removed)
                } else {
                    await this.groupManager.group(this.sortManager.result.slots, true)
                }
                this.runState.isDirty = false
            } else {
                await this.update()
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

        const count   = col.slotCount()
        const deleted = col.deletedMask()

        // Build Int32Array of active slots — no Instance objects created. Written straight
        // into a pre-allocated typed array (slotCount is the exact upper bound) instead of a
        // boxed number[] + copy, which doubled peak memory on large collections.
        const buf = new Int32Array(count)
        let n = 0
        for (let s = 0; s < count; s++) {
            if (!deleted[s]) buf[n++] = s
        }

        if (this.state.filterBySelection) {
            let k = 0
            for (let i = 0; i < n; i++) {
                if (col.isSelected(buf[i])) buf[k++] = buf[i]
            }
            n = k
        }
        // FilterManager retains this array (lastSlots), so hand it an exactly-sized one
        // rather than a view that pins the full-slotCount buffer alive.
        const slots = n === count ? buf : buf.slice(0, n)

        const filterRes = await this.filterManager.filter(slots)
        if (token !== this.runToken) return
        const sortRes   = await this.sortManager.sort(filterRes.slots)
        if (token !== this.runToken) return
        // Awaited: group() loads any missing columns first, so leaving it dangling cleared
        // isDirty (and resolved TabManager.update) before the tree actually existed.
        await this.groupManager.group(sortRes.slots, true)
        if (token !== this.runToken) return
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
            await this.groupManager.group(sortRes.slots, true)
            if (token !== this.runToken) return
            this.runState.isDirty = false
            return
        }
        if (kind === 'group') {
            await this.groupManager.group(this.sortManager.result.slots, true)
            if (token !== this.runToken) return
            this.runState.isDirty = false
            return
        }
        if (kind === 'sortGroups') {
            this.groupManager.sortGroups(true)
            this.runState.isDirty = false
        }
    }

    updateInstances(instanceIds: Set<number>) {
        // Keep the in-flight reflow so callers that write a value and then act on the
        // resulting tree (e.g. assign-then-drain in the group view) can await it.
        this.pending = this.setDirty(instanceIds).catch(e => { console.error('[collection] update failed', e) })
    }

    // Resolve once no data-driven reflow is in flight. Chains rather than snapshots, so a
    // reflow started while awaiting an earlier one is covered too.
    async settle(): Promise<void> {
        while (this.pending) {
            const p = this.pending
            await p
            if (this.pending === p) this.pending = null
        }
    }

    // Activate / deactivate. Going inactive must also drop any debounced reload, otherwise a
    // timer armed while visible still fires (and recomputes) after the tab is hidden.
    setActive(value: boolean) {
        this.runState.active = value
        if (!value && this.reloadTimer) {
            clearTimeout(this.reloadTimer)
            this.reloadTimer = null
            this.pendingKind = null
        }
    }

    // Tear down all reactive subscriptions. Called when the last view that
    // referenced this collection stops doing so (TabManager.pruneCollections),
    // and when the owning tab is deleted (TabManager.dispose).
    dispose() {
        this.stops.forEach(stop => stop())
        this.stops = []
        useDataStore().onChange.removeListener(this.boundUpdateInstances)
        if (this.reloadTimer) { clearTimeout(this.reloadTimer); this.reloadTimer = null }
        this.pendingKind = null
        this.runState.active = false
        // Bump the token so any run still awaiting a column load bails instead of writing
        // results into a collection nobody references anymore.
        this.runToken++
    }
}
