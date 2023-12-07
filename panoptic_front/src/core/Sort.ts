import { reactive } from "vue"

export enum SortType {
    Number = 'number',
    Value = 'value'
}

export enum SortOrder {
    Ascending = 'asc',
    Descending = 'desc'
}

export interface SortOption {
    order: SortOrder
}

export interface SorterState {
    sortBy: SortOption[]
}


export function buildSortOption(): SortOption {
    return { order: SortOrder.Ascending }
}

export class Sorter {
    state: SorterState

    constructor() {
        this.state = reactive({
            sortBy: []
        })
    }

    addSortOption(option: SortOption) {

    }

    setSortOption(option: SortOption) {
        
    }

    delSortOption(propertyId: number) {

    }

}