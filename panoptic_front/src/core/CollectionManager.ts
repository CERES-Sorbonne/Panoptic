/**
 * CollectionManager
 * Is responsible to connect the different managers together for reactivity
 */

import { ImageIndex } from "@/data/models";
import { FilterManager, FilterResult, FilterState } from "./FilterManager";
import { SortManager, SortResult, SortState } from "./SortManager";
import { GroupManager, GroupState, SelectedImages } from "./GroupManager";

export class CollectionManager {
    images: ImageIndex
    filterManager: FilterManager
    sortManager: SortManager
    groupManager: GroupManager

    constructor(images?: ImageIndex, filterState?: FilterState, sortState?: SortState, groupState?: GroupState, selectedImages?: SelectedImages) {
        this.filterManager = new FilterManager(filterState)
        this.sortManager = new SortManager(sortState)
        this.groupManager = new GroupManager(groupState, selectedImages)

        this.filterManager.onChange.addListener(this.onFilter.bind(this))
        this.sortManager.onChange.addListener(this.onSort.bind(this))
        this.groupManager.onChange.addListener(this.onGroup.bind(this))
        
        if(images) this.updateImages(images)

    }

    load(filterState?: FilterState, sortState?: SortState, groupState?: GroupState) {
        this.filterManager.load(filterState)
        this.sortManager.load(sortState)
        this.groupManager.load(groupState)
        
        if(this.images) this.updateImages(this.images)
    }

    verifyState() {
        this.filterManager.verifyState()
        this.sortManager.verifyState()
        this.groupManager.verifyState()
    }

    updateImages(images: ImageIndex) {
        this.images = images
        const filterRes = this.filterManager.filter(Object.values(this.images))
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