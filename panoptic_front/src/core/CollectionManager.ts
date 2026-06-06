/**
 * CollectionManager
 * Connects FilterManager → SortManager → GroupManager.
 * All three managers operate on Int32Array of column-store slot indices.
 * Instance objects are never allocated in this pipeline.
 */

import { CollectionState } from "@/data/models";
import { FilterContext, FilterManager, FilterResult, FilterState } from "./FilterManager";
import { SortManager, SortResult, SortState } from "./SortManager";
import { GroupManager, GroupState, SelectedImages } from "./GroupManager";
import { EventEmitter } from "@/utils/utils";
import { useDataStore } from "@/data/dataStore";
import { useColumnStore } from "@/data/columnStore";
import { Reactive, Ref, reactive, watch } from "vue";

export interface RunCollectionState {
    isDirty: boolean
    active: boolean
}

export function createCollectionState(): CollectionState {
    return { autoReload: true }
}

export class CollectionManager {
    state: CollectionState
    filterManager: FilterManager
    sortManager: SortManager
    groupManager: GroupManager

    runState: Reactive<RunCollectionState>

    onStateChange: EventEmitter

    constructor(state?: CollectionState, filterState?: FilterState, sortState?: SortState, groupState?: GroupState, selectedImages?: Ref<SelectedImages>) {
        const data = useDataStore()
        const col = useColumnStore()
        const ctx: FilterContext = { properties: data.properties, tags: data.tags, folders: data.folders }
        this.filterManager = new FilterManager(ctx, filterState)
        this.sortManager = new SortManager(sortState)
        this.groupManager = new GroupManager(groupState, selectedImages)
        if (state) {
            this.state = state as CollectionState
        } else {
            this.state = reactive({ autoReload: true })
        }

        this.runState = reactive({ isDirty: false, active: true })

        this.filterManager.onResultChange.addListener(this.onFilter.bind(this))
        this.sortManager.onResultChange.addListener(this.onSort.bind(this))
        this.groupManager.onResultChange.addListener(this.onGroup.bind(this))

        this.filterManager.onStateChange.addListener(this.setDirty.bind(this))

        data.onChange.addListener(this.updateInstances.bind(this))

        // Trigger full update whenever the column store finishes (re)loading.
        // immediate:true handles the case where a tab is created after init completes.
        watch(() => col.isReady, (ready) => {
            if (ready) this.update()
        }, { immediate: true })

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
            const selected = this.groupManager.selectedImages
            for (const id of Array.from(instanceIds)) {
                if (!selected[id]) instanceIds.delete(id)
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
        console.log('update collection', col.instanceCount)
        if (!col.isReady) return

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
            const selected = this.groupManager.selectedImages.value
            const sel: number[] = []
            for (let i = 0; i < slots.length; i++) {
                if (selected[instanceIds[slots[i]]]) sel.push(slots[i])
            }
            slots = new Int32Array(sel)
        }

        const filterRes = await this.filterManager.filter(slots)
        const sortRes   = await this.sortManager.sort(filterRes.slots)
        this.groupManager.group(sortRes.slots, true)
        this.runState.isDirty = false
    }

    private async onFilter(result: FilterResult) {
        const sortRes = await this.sortManager.sort(result.slots)
        this.groupManager.group(sortRes.slots, true)
    }

    private onSort(result: SortResult) {
        this.groupManager.group(result.slots, true)
    }

    private onGroup() {

    }

    updateInstances(instanceIds: Set<number>) {
        this.setDirty(instanceIds)
    }
}
