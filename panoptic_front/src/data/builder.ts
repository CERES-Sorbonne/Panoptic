import { reactive } from "vue";
import { PropertyOption, PropertyType, TabState } from "./models";
import { createFilterState } from "@/core/FilterManager";
import { createSortState } from "@/core/SortManager";
import { createGroupState } from "@/core/GroupManager";
import { softwareUiVersion } from "./projectStore";

export function buildTabState(): TabState {
    return reactive({
        version: softwareUiVersion,
        id: -1,
        name: 'Tab',
        display: 'tree',
        filterState: createFilterState(),
        sortState: createSortState(),
        groupState: createGroupState(),
        imageSize: 100,
        visibleProperties: {},
        visibleFolders: {},
        selectedFolders: {},
        propertyOptions: {},
        sha1Mode: true
    })
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

type ObjectValues<T> = T[keyof T][];

export function objValues<T>(obj: T): ObjectValues<T> {
  return Object.keys(obj).map(key => obj[key as keyof T]);
}