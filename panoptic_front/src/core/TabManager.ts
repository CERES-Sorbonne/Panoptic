import { PropertyMode, PropertyOption } from "@/data/models"
import { FilterState } from "./FilterManager"
import { GroupState } from "./GroupManager"
import { SortState } from "./SortManager"
import { CollectionManager } from "./CollectionManager"
import { useStore } from "@/data/store2"

const store = useStore()

export interface TabState {
    id: number
    name: string
    display: string

    filterState: FilterState
    sortState: SortState,
    groupState: GroupState,

    imageSize: number
    visibleProperties: { [key: number]: boolean }
    visibleFolders: { [key: number]: boolean }
    selectedFolders: { [key: number]: boolean }
    sha1Mode: boolean
    propertyOptions: { [key: number]: PropertyOption }
}

export class TabManager {
    isLoaded: boolean
    state: TabState
    collection: CollectionManager
    
    constructor(state?: TabState) {
        this.isLoaded = false
        this.collection = new CollectionManager()

        if(state) this.load(state)
    }

    load(state: TabState) {
        this.state = state
        this.collection.load(state.filterState, state.sortState, state.groupState)
        this.isLoaded = true
    }
    
    saveState() {
        store.updateTab(this.state)
    }

    setVisibleProperty(propId: number, value: boolean) {
        this.state.visibleProperties[propId] = value
    }

    isVisibleProperty(propId: number) {
        //console.log(this.tabs[this.selectedTab])
        return this.state.visibleProperties[propId]
    }

    getSha1Mode() {
        return this.collection.groupManager.state.sha1Mode
    }

    getVisibleProperties() {
        return store.propertyList.filter(p => this.isVisibleProperty(p.id))
    }

    getVisibleSha1Properties() {
        return this.getVisibleProperties().filter(p => p.mode == PropertyMode.sha1)
    }

}