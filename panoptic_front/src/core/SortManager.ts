/**
 * The SortManager is used to sort images by multiple properties
 * For each property a SortOption can be given to define the order (ascending, descending)
 * The result is a sorted array of images and an order index (Image -> order)
 */

import { deletedID, useDataStore } from "@/data/dataStore"
import { FolderIndex, Instance, InstanceIndex, Property, PropertyIndex } from "@/data/models"
import { PropertyType } from "@/data/models"
import { useProjectStore } from "@/data/projectStore"
import { EventEmitter } from "@/utils/utils"
import { reactive, toRefs, unref } from "vue"

export enum SortDirection {
    Ascending = 1,
    Descending = -1
}

export interface SortOption {
    direction?: SortDirection
}

export interface SortState {
    sortBy: number[]
    options: { [propId: number]: SortOption }
}

export type ImageOrder = { [imageId: number]: number }

export interface SortResult {
    order: ImageOrder
    images: Instance[]
}

interface SortableImage {
    imageId: number
    values: any[]
}

export function createSortState(): SortState {
    return reactive({
        sortBy: [],
        options: {}
    })
}

export function buildSortOption(): SortOption {
    return { direction: SortDirection.Ascending }
}

export const sortParser: { [type in PropertyType]?: any } = {
    [PropertyType.checkbox]: (x?: boolean) => {
        if (!x) return false
        return true
    },
    [PropertyType.color]: (x?: number) => {
        if (isNaN(x)) return -1
        return x
    },
    [PropertyType.date]: (x?: Date) => {
        if (!x) return 0
        return (new Date(x)).getTime()
    },
    [PropertyType.multi_tags]: (x?: number[]) => {
        if (!x) return 0
        return x.length
    },
    [PropertyType.number]: (x?: number) => {
        if (x == undefined) return Number.NEGATIVE_INFINITY
        return x
    },
    [PropertyType.path]: (x?: string) => {
        if (!x) return ''
        return x.toLocaleLowerCase()
    },
    [PropertyType.string]: (x?: string) => {
        if (!x) return ''
        return x.toLocaleLowerCase()
    },
    [PropertyType.tag]: (x?: string) => {
        if (!x) return ''
        return x
    },
    [PropertyType.url]: (x?: string) => {
        if (!x) return ''
        return x.toLocaleLowerCase()
    },
    [PropertyType._ahash]: (x: string) => {
        return x
    },
    [PropertyType._sha1]: (x: string) => {
        return x
    },
    [PropertyType._folders]: (x: number, folders: FolderIndex) => {
        return folders[x].name
    },
    [PropertyType._height]: (x: number) => {
        return x
    },
    [PropertyType._width]: (x: number) => {
        return x
    },
    [PropertyType._id]: (x: number) => {
        return x
    },
}

function getSortablePropertyValue(image: Instance, property: Property, folders: FolderIndex) {
    let value = image.properties[property.id]
    const type = property.type

    if (type == PropertyType.tag) {
        if (Array.isArray(value) && value.length > 0) {
            value = property.tags[value[0]].value
        } else {
            value = undefined
        }
    }
    if (type == PropertyType._folders) {
        value = sortParser[type](value, folders)
    } else {
        value = sortParser[type](value)
    }

    return value
}

function sortSortable(sortable: SortableImage[], orders: number[]) {
    sortable.sort((a, b) => compareSortable(a, b, orders))
    return sortable
}

function compareSortable(a: SortableImage, b: SortableImage, orders: number[]) {
    for (let i = 0; i < a.values.length; i++) {
        if (a.values[i] == b.values[i]) continue
        if (a.values[i] < b.values[i]) return -1 * orders[i]
        return 1 * orders[i]
    }
    return a.imageId - b.imageId
}

function insertSort(old: Instance[], updatedIds: Set<number>, removed: Set<number>, properties: Property[], orders: number[], instances: InstanceIndex) {
    const res: number[] = []
    const updated = Array.from(updatedIds).map(i => instances[i])
    const updatedSorted = sortSortable(getSortableImages(updated, properties), orders)

    let oldIndex = 0
    let nowIndex = 0
    while (nowIndex < updatedSorted.length) {
        const insertIndex = quadraticFindIndex(old, updatedSorted[nowIndex], oldIndex, properties, orders)
        for (let i = oldIndex; i < insertIndex; i++) {
            const id = old[i].id
            if (!updatedIds.has(id) && !removed.has(id)) {
                res.push(id)
            }
            oldIndex += 1
        }
        res.push(updatedSorted[nowIndex].imageId)
        nowIndex += 1
    }
    for (let i = oldIndex; i < old.length; i++) {
        const id = old[i].id
        if (!updatedIds.has(id) && !removed.has(id)) {
            res.push(id)
        }
    }
    return res
}

// Finds the first index where elem < target[index]
function quadraticFindIndex(target: Instance[], elem: SortableImage, startIndex: number, properties: Property[], orders: number[]) {
    if (startIndex >= target.length) return startIndex
    let maxIndex = target.length
    let dist = maxIndex - startIndex
    while (dist > 10) {
        const center = Math.floor(startIndex + dist / 2)
        // console.log(startIndex, center, maxIndex)
        const sortableTarget = getSortableImages([target[center]], properties)[0]
        const cmp = compareSortable(elem, sortableTarget, orders)
        if (cmp == 0) return center
        if (cmp < 0) {
            maxIndex = center
        }
        else {
            startIndex = center
        }
        dist = maxIndex - startIndex
    }
    for (let i = startIndex; i < maxIndex; i++) {
        const sortableTarget = getSortableImages([target[i]], properties)[0]
        if (compareSortable(elem, sortableTarget, orders) < 0) {
            return i
        }
    }
    return target.length
}

function getSortableImages(images: Instance[], properties: Property[]): SortableImage[] {
    const res = []
    const data = useDataStore()
    for (const image of images) {
        const sortable: SortableImage = { imageId: image.id, values: [] }
        properties.forEach(p => sortable.values.push(getSortablePropertyValue(image, p, data.folders)))
        res.push(sortable)
    }
    return res
}

export class SortManager {
    state: SortState
    result: SortResult

    onChange: EventEmitter

    constructor(state?: SortState) {
        this.state = state
        this.onChange = new EventEmitter()
        if (!this.state) {
            this.state = createSortState()
        }

        this.result = {
            images: [],
            order: {}
        }
    }

    load(state: SortState) {
        Object.assign(this.state, toRefs(state))
        this.clear()
    }

    clear() {
        this.result = { images: [], order: [] }
    }

    sort(images: Instance[], emit?: boolean): SortResult {
        console.time('Sort')
        const data = useDataStore()

        const properties = this.state.sortBy.map(id => data.properties[id])
        const sortable = getSortableImages(images, properties)

        const orders = this.state.sortBy.map(id => this.state.options[id].direction == SortDirection.Ascending ? 1 : -1)
        sortSortable(sortable, orders)

        this.result.images = []
        this.result.order = {}
        for (let i = 0; i < sortable.length; i++) {
            this.result.images.push(data.instances[sortable[i].imageId])
            this.result.order[sortable[i].imageId] = i
        }
        console.timeEnd('Sort')

        if (emit) this.onChange.emit(this.result)
        return this.result
    }

    updateSelection(updated: Set<number>, removed: Set<number>) {
        console.time('SortUpdate')
        const data = useDataStore()
        const properties = this.state.sortBy.map(id => data.properties[id])
        const orders = this.state.sortBy.map(id => this.state.options[id].direction == SortDirection.Ascending ? 1 : -1)
        const res = insertSort(this.result.images, updated, removed, properties, orders, data.instances)
        this.result.images = []
        this.result.order = {}
        for (let i = 0; i < res.length; i++) {
            this.result.images.push(data.instances[res[i]])
            this.result.order[res[i]] = i
        }
        console.timeEnd('SortUpdate')

        return this.result
    }

    update(emit?: boolean) {
        console.log('update sort', this.result.images.length)
        this.sort(this.result.images)
        if (emit) this.onChange.emit(this.result)
    }

    setSort(propertyId: number, option?: SortOption) {
        if (option) {
            this.state.options[propertyId] = option
        } else if (!option && this.state.options[propertyId] == undefined) {
            this.state.options[propertyId] = buildSortOption()
        }

        if (this.state.sortBy.includes(propertyId)) return
        this.state.sortBy.push(propertyId)
        console.log(this.state)
    }

    delSort(propertyId: number) {
        const index = this.state.sortBy.indexOf(propertyId)
        if (index < 0) return
        this.state.sortBy.splice(index, 1)
    }

    verifyState(properties: PropertyIndex) {
        this.state.sortBy = this.state.sortBy.filter(id => properties[id] && properties[id].id != deletedID)
        Object.keys(this.state.options).filter(id => !properties[id] || properties[id].id == deletedID).forEach(id => delete this.state.options[id])
    }
}