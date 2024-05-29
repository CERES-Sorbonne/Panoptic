/**
 * CollectionManager
 * Is responsible to connect the different managers together for reactivity
 */

import { ImageIndex, InstanceIndex } from "@/data/models";
import { FilterManager, FilterResult, FilterState } from "./FilterManager";
import { SortManager, SortResult, SortState } from "./SortManager";
import { GroupManager, GroupState, SelectedImages } from "./GroupManager";
import { objValues } from "@/utils/utils";
import { useDataStore } from "@/data/dataStore";

export class CollectionManager {
    images: InstanceIndex
    filterManager: FilterManager
    sortManager: SortManager
    groupManager: GroupManager

    constructor(images?: InstanceIndex, filterState?: FilterState, sortState?: SortState, groupState?: GroupState, selectedImages?: SelectedImages) {
        this.filterManager = new FilterManager(filterState)
        this.sortManager = new SortManager(sortState)
        this.groupManager = new GroupManager(groupState, selectedImages)

        this.filterManager.onChange.addListener(this.onFilter.bind(this))
        this.sortManager.onChange.addListener(this.onSort.bind(this))
        this.groupManager.onChange.addListener(this.onGroup.bind(this))
        
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
        this.filterManager.verifyState()
        this.sortManager.verifyState()
        this.groupManager.verifyState(data.properties)
    }

    async update(images?: InstanceIndex) {
        // throw new Error('update')
        // console.log('update')
        this.images = images ?? this.images
        if(!this.images) return
        
        const filterRes = await this.filterManager.filter(objValues(this.images))
        const sortRes = this.sortManager.sort(filterRes.images)
        this.groupManager.group(sortRes.images, sortRes.order, true)
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
}