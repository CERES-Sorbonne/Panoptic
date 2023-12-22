/**
 * The SortManager is used to sort images by multiple properties
 * For each property a SortOption can be given to define the order (ascending, descending)
 * The result is a sorted array of images and an order index (Image -> order)
 */

import { Image, Property } from "@/data/models"
import { PropertyType } from "@/data/models"
import { useStore } from "@/data/store"
import { EventEmitter } from "@/utils/utils"
import { reactive, toRefs } from "vue"

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
    images: Image[]
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
        return x.getTime()
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
        return x
    },
    [PropertyType.string]: (x?: string) => {
        if (!x) return ''
        return x
    },
    [PropertyType.tag]: (x?: string) => {
        if (!x) return ''
        return x
    },
    [PropertyType.url]: (x?: string) => {
        if (!x) return ''
        return x
    },
    [PropertyType._ahash]: (x: string) => {
        return x
    },
    [PropertyType._sha1]: (x: string) => {
        return x
    },
    [PropertyType._folders]: (x: number) => {
        const store = useStore()
        return store.data.folders[x].name
    }
}

function getSortablePropertyValue(image: Image, property: Property) {
    let value = image.properties[property.id]?.value
    const type = property.type

    if (type == PropertyType.tag) {
        if (Array.isArray(value) && value.length > 0) {
            value = property.tags[value[0]].value
        } else {
            value = undefined
        }
    }

    value = sortParser[type](value)
    return value
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

        this.result = reactive({
            images: [],
            order: {}
        })
    }

    load(state: SortState) {
        Object.assign(this.state, toRefs(state))
        this.clear()
    }

    clear() {
        this.result = { images: [], order: [] }
    }

    sort(images: Image[], emit?: boolean): SortResult {
        console.time('Sort')
        const sortable = this.getSortableImages(images)
        const order = this.state.sortBy.map(id => this.state.options[id].direction == SortDirection.Ascending ? 1 : -1)
        sortable.sort((a, b) => {
            for (let i = 0; i < a.values.length; i++) {
                if (a.values[i] == b.values[i]) continue
                if (a.values[i] < b.values[i]) return -1 * order[i]
                return 1 * order[i]
            }
            return a.imageId - b.imageId
        })
        this.result.images = []
        this.result.order = {}

        for (let i = 0; i < sortable.length; i++) {
            const store = useStore()
            this.result.images.push(store.data.images[sortable[i].imageId])
            this.result.order[sortable[i].imageId] = i
        }
        console.timeEnd('Sort')

        if (emit) this.onChange.emit(this.result)
        return this.result
    }

    update(emit?: boolean) {
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

    verifyState() {
        const store = useStore()
        this.state.sortBy = this.state.sortBy.filter(id => store.data.properties[id])
        Object.keys(this.state.options).filter(id => !store.data.properties[id]).forEach(id => delete this.state.options[id])
    }

    private getSortableImages(images: Image[]): SortableImage[] {
        const store = useStore()
        const res = []
        const properties = this.state.sortBy.map(id => store.data.properties[id])

        for (const image of images) {
            const sortable: SortableImage = { imageId: image.id, values: [] }
            properties.forEach(p => sortable.values.push(getSortablePropertyValue(image, p)))
            res.push(sortable)
        }
        return res
    }
}