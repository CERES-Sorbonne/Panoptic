import { CollectionConfig, PropertyMode, ViewType, TabState } from "@/data/models"
import { CollectionManager } from "./CollectionManager"
import { deepCopy, EventEmitter } from "@/utils/utils"
import { useDataStore } from "@/data/dataStore"
import { createCollectionConfig, createMapOptions, createViewState, defaultPropertyOption } from "@/data/builder"

export class TabManager {
    state: TabState
    // One CollectionManager per collectionId. Two views sharing an id share the
    // same runtime instance (computed once — M4 / §4).
    collections: Record<string, CollectionManager>
    isNew?: boolean

    onLoad: EventEmitter

    constructor(state: TabState) {
        this.state = state
        this.collections = {}
        this.onLoad = new EventEmitter()
        // verifyState (below) guarantees collections/views exist and are coherent
        // BEFORE we build the runtime managers from them.
        this.verifyState()
        if (state.isSelection) {
            for (const cfg of this.state.collections) cfg.collectionState.filterBySelection = true
        }
        this.buildCollections()
        // No save wiring here: persistence is a single debounced deep watch on
        // the active tab in tabStore (Pillar C). Mutating `this.state` (which is
        // the same proxy as tabs[id]) is enough to trigger autosave.
    }

    // Build a CollectionManager for every config that doesn't have one yet.
    private buildCollections() {
        for (const cfg of this.state.collections) {
            if (!this.collections[cfg.id]) {
                this.collections[cfg.id] = new CollectionManager(
                    cfg.collectionState, cfg.filterState, cfg.sortState, cfg.groupState
                )
            }
        }
    }

    // The "primary" collection — the one view 0 renders. Backwards-compatible
    // accessor for the shared tab-bar forms and any component that only holds a
    // tab (modals, menus). Per-view rendering uses collectionForView().
    get collection(): CollectionManager {
        return this.collectionForView(0)
    }

    collectionForView(viewIndex: number): CollectionManager {
        const view = this.state.views[viewIndex]
        const id = view?.collectionId ?? this.state.collections[0]?.id
        return this.collections[id] ?? this.collections[this.state.collections[0].id]
    }

    // ── View binding (M4) ───────────────────────────────────────────────────
    // "Bound" = both views render the same collection (one pipeline, computed
    // once). "Unbound" = view 1 has its own copy so the two filters diverge.

    isBound(): boolean {
        const v = this.state.views
        return !v[1] || v[0].collectionId === v[1].collectionId
    }

    toggleBind() {
        if (this.isBound()) this.unbindViews()
        else this.bindViews()
    }

    // Make view 1 share view 0's collection again; drop the orphaned one.
    private bindViews() {
        if (this.isBound()) return
        this.state.views[1].collectionId = this.state.views[0].collectionId
        this.pruneCollections()
        this.activate()
        this.update()
    }

    // Give view 1 its own copy of view 0's collection so the filters diverge.
    private unbindViews() {
        if (!this.isBound()) return
        const src = this.state.collections.find(c => c.id === this.state.views[0].collectionId)
        if (!src) return
        const clone = deepCopy(src) as CollectionConfig
        clone.id = crypto.randomUUID()
        this.state.collections.push(clone)
        this.state.views[1].collectionId = clone.id
        this.buildCollections()
        this.activate()
        this.update()
    }

    // Drop collection configs (and dispose their runtime managers) that no view
    // references anymore.
    private pruneCollections() {
        const used = new Set(this.state.views.map(v => v.collectionId))
        this.state.collections = this.state.collections.filter(c => used.has(c.id))
        for (const id of Object.keys(this.collections)) {
            if (!used.has(id)) {
                this.collections[id].dispose()
                delete this.collections[id]
            }
        }
    }

    // Distinct collections currently shown: view 0 always; view 1 only on split.
    get activeCollections(): CollectionManager[] {
        const ids = new Set<string>()
        ids.add(this.state.views[0].collectionId)
        if (this.state.splitView && this.state.views[1]) ids.add(this.state.views[1].collectionId)
        return [...ids].map(id => this.collections[id]).filter(Boolean)
    }

    async update() {
        this.verifyState()
        this.buildCollections()
        if (useDataStore().isLoaded) {
            await Promise.all(this.activeCollections.map(c => c.update()))
        }
    }

    deactivate() {
        for (const id in this.collections) this.collections[id].runState.active = false
    }

    activate() {
        // Only visible collections recompute; the rest stay dirty and activate
        // lazily when their view becomes visible (e.g. split toggled on).
        const active = new Set(this.activeCollections)
        for (const id in this.collections) {
            this.collections[id].runState.active = active.has(this.collections[id])
        }
    }

    verifyState() {
        const data = useDataStore()

        // Ensure at least one collection config exists.
        if (!Array.isArray(this.state.collections) || this.state.collections.length === 0) {
            this.state.collections = [createCollectionConfig()]
        }
        const firstId = this.state.collections[0].id

        // Per-view display state (Pillar F): ensure both views exist, each carries
        // its map options, and each references an existing collection.
        if (!Array.isArray(this.state.views) || this.state.views.length < 2) {
            this.state.views = [createViewState('tree', firstId), createViewState('grid', firstId)]
        }
        for (const view of this.state.views) {
            if (!view.mapOptions) view.mapOptions = createMapOptions()
            if (!view.collectionId || !this.state.collections.find(c => c.id === view.collectionId)) {
                view.collectionId = firstId
            }
        }

        // Verify the runtime managers we have already built.
        for (const id in this.collections) this.collections[id].verifyState()

        if (this.state.propertyOptions == undefined) {
            this.state.propertyOptions = {}
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
