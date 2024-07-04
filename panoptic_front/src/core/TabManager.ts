import { PropertyMode, TabState } from "@/data/models"
import { CollectionManager } from "./CollectionManager"
import { useProjectStore } from "@/data/projectStore"
import { reactive, toRefs } from "vue"
import { EventEmitter } from "@/utils/utils"
import { useDataStore } from "@/data/dataStore"
import { defaultPropertyOption } from "@/data/builder"

export class TabManager {
    isLoaded: boolean
    state: TabState
    collection: CollectionManager

    onLoad: EventEmitter
    
    constructor(state?: TabState) {
        this.isLoaded = false
        this.state = reactive({} as TabState)
        this.collection = new CollectionManager(undefined, undefined, undefined, undefined, undefined, this.state)
        this.onLoad = new EventEmitter()

        if(state) this.load(state)
    }

    async load(state: TabState) {
        const data = useDataStore()
        Object.assign(this.state, toRefs(state))
        if(!state) return
        this.collection.load(state.filterState, state.sortState, state.groupState)
        this.verifyState()
        this.isLoaded = true
        await this.collection.update(data.instances)

        this.onLoad.emit()
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
    }
    
    saveState() {
        const project = useProjectStore()
        project.updateTabs()
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
        const data = useDataStore()
        return data.propertyList.filter(p => this.isVisibleProperty(p.id))
    }

    getVisibleSha1Properties() {
        return this.getVisibleProperties().filter(p => p.mode == PropertyMode.sha1)
    }

}