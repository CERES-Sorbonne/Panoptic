/**
 * Group child-ordering helpers: sort a group's children by property value or by size,
 * and assign DFS display order.
 */
import { FolderIndex, PropertyIndex, PropertyType } from "@/data/models";
import { isTag } from "@/utils/utils";
import { useDataStore } from "@/data/dataStore";
import { sortParser } from "../SortManager";
import { Group, GroupOption, GroupSortType } from "./types";

export function sortGroup(group: Group, option: GroupOption) {
    const data = useDataStore()
    if (group.children.length == 0) return
    if (option.type == GroupSortType.Property) {
        sortGroupByProperty(group, option.direction, data.properties, data.folders)
    } else {
        sortGroupBySize(group, option.direction)
    }
    for (let i = 0; i < group.children.length; i++) {
        group.children[i].parentIdx = i
    }
}

export function sortGroupByProperty(group: Group, direction: number, properties: PropertyIndex, folders: FolderIndex) {
    const sortable: { [id: number]: any[] } = {}
    for (const child of group.children) {
        const values = []
        for (const propValue of child.meta.propertyValues) {
            const prop = properties[propValue.propertyId]
            const type = isTag(prop.type) ? PropertyType.tag : prop.type
            let value = propValue.value
            if (isTag(type) && value != undefined) {
                const tagObj = prop.tags?.[value]
                value = tagObj ? tagObj.value : value
            }
            value = sortParser[type](value, folders)
            values.push(value)
        }
        sortable[child.id] = values
    }
    group.children.sort((ca, cb) => {
        const a = sortable[ca.id]
        const b = sortable[cb.id]
        for (let i = 0; i < a.length; i++) {
            if (a[i] == b[i]) continue
            if (a[i] < b[i]) return -1 * direction
            return 1 * direction
        }
        return 0
    })
}

export function sortGroupBySize(group: Group, direction: number) {
    group.children.sort((a, b) => (a.slots.length - b.slots.length) * direction)
}

export function setOrder(group: Group) {
    let i = 0
    const recursive = (g: Group) => {
        g.order = i++
        g.children.forEach(c => recursive(c))
    }
    recursive(group)
}
