import { reactive } from "vue";
import { CollectionConfig, MapOptions, PropertyGroupOrder, PropertyOption, PropertyType, RecoOptions, TabState, ViewState, ViewType } from "./models";
import { createFilterState } from "@/core/FilterManager";
import { createSortState } from "@/core/SortManager";
import { createGroupState } from "@/core/GroupManager";
import { createCollectionState } from "@/core/CollectionManager";
import { TAB_MODEL_VERSION } from "./tabStore";

export function createCollectionConfig(): CollectionConfig {
    return reactive({
        id: crypto.randomUUID(),
        collectionState: createCollectionState(),
        filterState: createFilterState(),
        sortState: createSortState(),
        groupState: createGroupState(),
    })
}

export function createViewState(type: ViewType, collectionId: string): ViewState {
    return reactive({
        type,
        imageSize: 100,
        mapOptions: createMapOptions(),
        recoOptions: createRecoOptions(),
        showProperties: true,
        collectionId,
    })
}

export function buildTabState(): TabState {
    // One shared collection by default; both views reference it (computed once).
    const collection = createCollectionConfig()
    return reactive({
        version: TAB_MODEL_VERSION,
        id: '',
        name: 'New Tab',
        collections: [collection],
        views: [createViewState('tree', collection.id), createViewState('grid', collection.id)],
        splitView: false,
        splitRatio: 0.5,
        visibleProperties: {},
        visibleFolders: {},
        selectedFolders: {},
        propertyOptions: {},
    }) as TabState
}

export function createMapOptions(): MapOptions {
    return {
        showPoints: false,
        groupOption: 'cluster',
        selectedMap: 0,
        imageSize: 50
    }
}

export function createRecoOptions(): RecoOptions {
    return {
        selectedGroupId: null
    }
}

export function propertyDefault(type: PropertyType): any {
    switch (type) {
        case PropertyType.checkbox:
            return false
        case PropertyType.color:
            return undefined
        case PropertyType.date:
            return undefined
        case PropertyType.number:
            return undefined
        case PropertyType.string:
        case PropertyType.image_link:
        case PropertyType.path:
        case PropertyType._sha1:
        case PropertyType.url:
        case PropertyType._ahash:
            return ''
        case PropertyType.multi_tags:
        case PropertyType.tag:
            return []
        default:
            return ''
    }
}

export function defaultPropertyOption() {
    return {
        size: 200
    } as PropertyOption
}

export function buildPropertyGroupOrder(): PropertyGroupOrder {
    return { groups: {}, properties: {} }
}

type ObjectValues<T> = T[keyof T][];

export function objValues<T>(obj: T): ObjectValues<T> {
    return Object.keys(obj).map(key => obj[key as keyof T]);
}

