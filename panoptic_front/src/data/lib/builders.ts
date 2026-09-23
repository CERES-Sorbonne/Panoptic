import { ClusterOptions, GraphOptions, MapOptions, PropertyGroupOrder, PropertyOption, PropertyType, RecoOptions } from "@/data/models";

export function createMapOptions(): MapOptions {
    return {
        showPoints: false,
        selectedMap: 0,
        borderWidth: 0.05
    }
}

export function createRecoOptions(): RecoOptions {
    return {
        selectedGroupId: null,
        previousType: null
    }
}

export function createClusterOptions(): ClusterOptions {
    return {
        selectedGroupId: null
    }
}

export function createGraphOptions(): GraphOptions {
    return {
        chartType: 'area',
        stacked: false,
        showThumbnails: false
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

