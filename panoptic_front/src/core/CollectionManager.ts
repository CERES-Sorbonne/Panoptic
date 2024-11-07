/**
 * CollectionManager
 * Is responsible to connect the different managers together for reactivity
 */

import { InstanceIndex } from "@/data/models";
import { CollectionState, FilterManager, FilterResult, FilterState } from "./FilterManager";
import { SortManager, SortResult, SortState } from "./SortManager";
import { GroupManager, GroupState, SelectedImages } from "./GroupManager";
import { objValues } from "@/utils/utils";
import { useDataStore } from "@/data/dataStore";
import { Ref, reactive } from "vue";

export class CollectionManager {
    images: InstanceIndex
    state: CollectionState
    filterManager: FilterManager
    sortManager: SortManager
    groupManager: GroupManager
    options: { autoReload: boolean }

    constructor(images?: InstanceIndex, filterState?: FilterState, sortState?: SortState, groupState?: GroupState, selectedImages?: Ref<SelectedImages>, options?: { autoReload: boolean }) {
        this.filterManager = new FilterManager(filterState)
        this.sortManager = new SortManager(sortState)
        this.groupManager = new GroupManager(groupState, selectedImages)
        this.state = reactive({ isDirty: false } as CollectionState)

        this.filterManager.onChange.addListener(this.onFilter.bind(this))
        this.sortManager.onChange.addListener(this.onSort.bind(this))
        this.groupManager.onChange.addListener(this.onGroup.bind(this))

        this.filterManager.onDirty.addListener(() => this.setDirty())
        this.options = options ?? { autoReload: false }

        const data = useDataStore()
        data.onChange.addListener((dirtyInstances) => this.updateInstances(dirtyInstances))
        // if(images) this.update(images)

    }

    load(filterState?: FilterState, sortState?: SortState, groupState?: GroupState) {
        this.filterManager.load(filterState)
        this.sortManager.load(sortState)
        this.groupManager.load(groupState)

        // if(this.images) this.update(this.images)
    }

    verifyState() {
        const data = useDataStore()
        this.filterManager.verifyState(data.properties)
        this.sortManager.verifyState(data.properties)
        this.groupManager.verifyState(data.properties)
    }

    async setDirty(instanceIds?: Set<number>) {
        this.state.isDirty = true
        if (this.options.autoReload) {
            if (instanceIds) {
                const filterUpdate = await this.filterManager.updateSelection(instanceIds)
                this.sortManager.updateSelection(filterUpdate.updated, filterUpdate.removed)
                this.groupManager.lastOrder = this.sortManager.result.order
                this.groupManager.updateSelection(filterUpdate.updated, filterUpdate.removed)
                this.state.isDirty = false
            } else {
                this.update()
            }

        }
    }

    async update(images?: InstanceIndex) {
        // throw new Error('update')
        // console.log('update')
        this.images = images ?? this.images
        if (!this.images) return

        const filterRes = await this.filterManager.filter(objValues(this.images))
        const sortRes = this.sortManager.sort(filterRes.images)
        this.groupManager.group(sortRes.images, sortRes.order, true)
        this.state.isDirty = false
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
        this.setDirty(instanceIds)
    }
}