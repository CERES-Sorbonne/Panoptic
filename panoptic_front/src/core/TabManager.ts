import { PropertyMode, ScoreInterval, TabState } from "@/data/models"
import { CollectionManager } from "./CollectionManager"
import { useProjectStore } from "@/data/projectStore"
import { reactive, toRefs } from "vue"
import { EventEmitter } from "@/utils/utils"
import { useDataStore } from "@/data/dataStore"
import { createMapOptions, defaultPropertyOption } from "@/data/builder"
import { useTabStore } from "@/data/tabStore"

export class TabManager {
    state: TabState
    collection: CollectionManager
    isNew?: boolean

    onLoad: EventEmitter

    constructor(state: TabState) {
        this.state = reactive(state)
        this.collection = new CollectionManager(state.collectionState, state.filterState, state.sortState, state.groupState)
        this.onLoad = new EventEmitter()
        this.verifyState()

        this.collection.filterManager.onStateChange.addListener(this.saveManagerStates.bind(this))
        this.collection.groupManager.onStateChange.addListener(this.saveManagerStates.bind(this))
        this.collection.sortManager.onStateChange.addListener(this.saveManagerStates.bind(this))
        this.collection.onStateChange.addListener(this.saveManagerStates.bind(this))
    }

    async update() {
        this.verifyState()
        if (useDataStore().isLoaded) {
            await this.collection.update()
        }
    }

    async deactivate() {
        this.collection.runState.active = false
    }

    async activate() {
        this.collection.runState.active = true
    }

    verifyState() {
        const data = useDataStore()
        this.collection.verifyState()
        if (this.state.propertyOptions == undefined) {
            this.state.propertyOptions = {}
        }
        for (let propId in data.properties) {
            this.state.propertyOptions[propId] = Object.assign(defaultPropertyOption(), this.state.propertyOptions[propId])
        }
        if(!this.state.mapOptions) {
            this.state.mapOptions = createMapOptions()
        }
        this.updatePropertyOptions()
    }

    setVisibleProperty(propId: number, value: boolean) {
        this.state.visibleProperties[propId] = value
        this.saveState()
    }

    setVisibleProperties(propIds: number[], value: boolean) {
        propIds.forEach(p => {
            this.state.visibleProperties[p] = value
        })
        this.saveState()
    }

    setSelectedFolder(selectedFolders) {
        this.state.selectedFolders = selectedFolders
        this.saveState()
    }

    isVisibleProperty(propId: number) {
        //console.log(this.tabs[this.selectedTab])
        return this.state.visibleProperties[propId]
    }

    getSha1Mode() {
        return this.collection.groupManager.state.sha1Mode
    }

    getVisibleProperties() {
        const data = useDataStore()
        return data.propertyList.filter(p => this.isVisibleProperty(p.id))
    }

    getVisibleSha1Properties() {
        return this.getVisibleProperties().filter(p => p.mode == PropertyMode.sha1)
    }

    setViewMode(mode: string) {
        this.state.display = mode
        this.saveState()
    }

    renameTab(name: string) {
        this.state.name = name
        this.saveState()
    }

    private saveManagerStates() {
        Object.assign(this.state.collectionState, this.collection.state)
        Object.assign(this.state.filterState, this.collection.filterManager.state)
        Object.assign(this.state.sortState, this.collection.sortManager.state)
        Object.assign(this.state.groupState, this.collection.groupManager.state)
        this.saveState()
    }

    private updatePropertyOptions() {
        if (this.state.propertyOptions == undefined) {
            this.state.propertyOptions = {}
        }
        const data = useDataStore()
        for (let propId in data.properties) {
            this.state.propertyOptions[propId] = Object.assign(defaultPropertyOption(), this.state.propertyOptions[propId])
        }
    }

    async saveState() {
        console.log('save state')
        const tabStore = useTabStore()
        tabStore.saveTabsToStorage()
    }

}