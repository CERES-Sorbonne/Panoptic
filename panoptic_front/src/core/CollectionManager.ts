/**
 * CollectionManager
 * Is responsible to connect the different managers together for reactivity
 */

import { CollectionState, InstanceIndex } from "@/data/models";
import { FilterManager, FilterResult, FilterState } from "./FilterManager";
import { SortManager, SortResult, SortState } from "./SortManager";
import { GroupManager, GroupState, SelectedImages } from "./GroupManager";
import { EventEmitter, objValues } from "@/utils/utils";
import { useDataStore } from "@/data/dataStore";
import { Reactive, Ref, reactive } from "vue";

export interface RunCollectionState {
    isDirty: boolean
    active: boolean
}

export function createCollectionState(): CollectionState {
    return { autoReload: true }
}

export class CollectionManager {
    images: InstanceIndex
    state: CollectionState
    filterManager: FilterManager
    sortManager: SortManager
    groupManager: GroupManager

    runState: Reactive<RunCollectionState>

    onStateChange: EventEmitter

    constructor(state?: CollectionState, filterState?: FilterState, sortState?: SortState, groupState?: GroupState, selectedImages?: Ref<SelectedImages>) {
        this.filterManager = new FilterManager(filterState)
        this.sortManager = new SortManager(sortState)
        this.groupManager = new GroupManager(groupState, selectedImages)
        this.state = reactive({ autoReload: true })
        this.runState = reactive({ isDirty: false, active: true })

        if (state) {
            Object.assign(this.state, state)
        }

        this.filterManager.onResultChange.addListener(this.onFilter.bind(this))
        this.sortManager.onResultChange.addListener(this.onSort.bind(this))
        this.groupManager.onResultChange.addListener(this.onGroup.bind(this))

        this.filterManager.onStateChange.addListener(this.setDirty.bind(this))

        const data = useDataStore()
        data.onChange.addListener(this.updateInstances.bind(this))

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
        if(!this.runState.active) {
            return
        }

        if (this.state.autoReload) {
            if (instanceIds) {
                const filterUpdate = await this.filterManager.updateSelection(instanceIds)
                this.sortManager.updateSelection(filterUpdate.updated, filterUpdate.removed)
                this.groupManager.lastOrder = this.sortManager.result.order
                this.groupManager.updateSelection(filterUpdate.updated, filterUpdate.removed)
                this.runState.isDirty = false
            } else {
                this.update()
            }

        }
    }

    async update() {
        // console.log('collection update')
        const data = useDataStore()
        if(this.state.instances) {
            this.images = {}
            this.state.instances.forEach(i => this.images[i] = data.instances[i])
        } else {
            this.images = data.instances
        }
        if (!this.images) return

        const filterRes = await this.filterManager.filter(objValues(this.images))
        const sortRes = this.sortManager.sort(filterRes.images)
        this.groupManager.group(sortRes.images, sortRes.order, true)
        this.runState.isDirty = false
    }

    private onFilter(result: FilterResult) {
        const sortRes = this.sortManager.sort(result.images)
        this.groupManager.group(sortRes.images, sortRes.order, true)
    }

    private onSort(result: SortResult) {
        this.groupManager.sort(result.order, true)
    }

    private onGroup() {

    }

    updateInstances(instanceIds: Set<number>) {
        console.log('update instances', instanceIds)
        this.setDirty(instanceIds)
    }
}