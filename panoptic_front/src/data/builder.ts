import { reactive } from "vue";
import { MapOptions, PropertyGroupOrder, PropertyOption, PropertyType, TabState } from "./models";
import { createFilterState } from "@/core/FilterManager";
import { createSortState } from "@/core/SortManager";
import { createGroupState } from "@/core/GroupManager";
import { createCollectionState } from "@/core/CollectionManager";
import { TAB_MODEL_VERSION } from "./tabStore";

export function buildTabState(): TabState {
    return reactive({
        version: TAB_MODEL_VERSION,
        id: -1,
        name: 'New Tab',
        display: 'tree',
        filterState: createFilterState(),
        sortState: createSortState(),
        groupState: createGroupState(),
        collectionState: createCollectionState(),
        mapOptions: createMapOptions(),
        imageSize: 100,
        visibleProperties: {},
        visibleFolders: {},
        selectedFolders: {},
        propertyOptions: {},
        similarityDist: 0.7,
        sha1Mode: true,
        autoReload: true
    })
}

export function createMapOptions(): MapOptions {
    return {
        showPoints: false,
        groupOption: 'cluster',
        selectedMap: 0,
        imageSize: 50
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

