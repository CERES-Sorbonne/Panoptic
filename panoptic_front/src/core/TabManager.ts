import { PropertyMode, ViewType, TabState } from "@/data/models"
import { CollectionManager } from "./CollectionManager"
import { EventEmitter } from "@/utils/utils"
import { useDataStore } from "@/data/dataStore"
import { createMapOptions, createViewState, defaultPropertyOption } from "@/data/builder"

export class TabManager {
    state: TabState
    collection: CollectionManager
    isNew?: boolean

    onLoad: EventEmitter

    constructor(state: TabState) {
        if(state.isSelection) {
            state.collectionState.filterBySelection = true
        }
        this.state = state
        this.collection = new CollectionManager(state.collectionState, state.filterState, state.sortState, state.groupState)
        this.onLoad = new EventEmitter()
        this.verifyState()
        // No save wiring here: persistence is a single debounced deep watch on
        // the active tab in tabStore (Pillar C). Mutating `this.state` (which is
        // the same proxy as tabs[id]) is enough to trigger autosave.
    }

    async update() {
        this.verifyState()
        if (useDataStore().isLoaded) {
            await this.collection.update()
        }
    }

    deactivate() {
        this.collection.runState.active = false
    }

    activate() {
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
        // Per-view display state (Pillar F): ensure both views exist and each
        // carries its map options.
        if (!Array.isArray(this.state.views) || this.state.views.length < 2) {
            this.state.views = [createViewState('tree'), createViewState('grid')]
        }
        for (const view of this.state.views) {
            if (!view.mapOptions) view.mapOptions = createMapOptions()
        }
        this.updatePropertyOptions()
    }

    setVisibleProperty(propId: number, value: boolean) {
        this.state.visibleProperties[propId] = value
    }

    setVisibleProperties(propIds: number[], value: boolean) {
        propIds.forEach(p => {
            this.state.visibleProperties[p] = value
        })
    }

    setSelectedFolder(selectedFolders) {
        this.state.selectedFolders = selectedFolders
    }

    isVisibleProperty(propId: number) {
        return this.state.visibleProperties[propId]
    }

    getSha1Mode() {
        return this.collection.groupManager.state.sha1Mode
    }

    getVisibleProperties() {
        const data = useDataStore()
        const order = data.propertyOrder?.properties ?? {}
        return (data.propertyList ?? [])
            .filter(p => this.isVisibleProperty(p.id))
            .sort((a, b) => (order[a.id] ?? 0) - (order[b.id] ?? 0))
    }

    getVisibleSha1Properties() {
        return this.getVisibleProperties().filter(p => p.mode == PropertyMode.sha1)
    }

    setViewType(viewIndex: number, type: ViewType) {
        const view = this.state.views[viewIndex]
        if (view) view.type = type
    }

    renameTab(name: string) {
        this.state.name = name
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

}
