/**
 * The FilterManager allows to create complexe filters to select a subset of images
 * The FilterState allows the user to save all current filtering options
 * The FilterState must be treated as a reactive Readonly object outside of the FilterManager class
 * Images are first filtered by folders then by properties
 */

import { Filter, Image, FilterGroup, PropertyType, AFilter, propertyDefault, isTag, availableOperators } from "@/data/models";
import { globalStore } from "@/data/store";
import { EventEmitter, getTagChildren } from "@/utils/utils";
import { reactive } from "vue";


export interface FilterState {
    folders: number[]
    filter: FilterGroup
}

export interface FilterResult {
    images: Image[]
}

export interface FilterUpdate {
    propertyId?: number
    operator?: FilterOperator
    value?: any
}

export enum FilterOperator {
    equal = "equal",
    equalNot = "equalNot",
    like = "like",
    lower = "lower",
    leq = "leq",
    greater = "greater",
    geq = "geq",
    isTrue = "isTrue",
    isFalse = "isFalse",
    contains = "contains",
    startsWith = "startsWith",
    containsAny = "containsAny",
    containsAll = "containsAll",
    containsNot = "containsNot",
    and = "and",
    or = "or",
    isSet = "isSet",
    notSet = "notSet"
}

const operatorMap: { [operator in FilterOperator]?: any } = {
    [FilterOperator.geq]: (a: any, b: any) => {
        if (b == undefined) return true;
        if (a == undefined) return false;
        return a >= b
    },
    [FilterOperator.leq]: (a: any, b: any) => {
        if (b == undefined) return true;
        if (a == undefined) return false;
        return a <= b
    },
    [FilterOperator.lower]: (a: any, b: any) => {
        if (b == undefined) return true;
        if (a == undefined) return false;
        return a < b
    },
    [FilterOperator.greater]: (a: any, b: any) => {
        if (b == undefined) return true;
        if (a == undefined) return false;
        return a > b
    },
    [FilterOperator.and]: (a: boolean, b: boolean) => a && b,
    [FilterOperator.or]: (a: boolean, b: boolean) => a || b,
    [FilterOperator.contains]: (a: string, b: string) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;
        return a.includes(b)
    },
    [FilterOperator.containsAll]: (a: Set<number>, b: number[][]) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;

        for (let tagList of b) {
            if (!tagList.some(tId => a.has(tId))) return false
        }
        return true
        // return b.filter(e => a.includes(e)).length == b.length
    },
    [FilterOperator.containsAny]: (a: Set<number>, b: number[][]) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;
        // return a.some(e => b.includes(e))

        for (let tagList of b) {
            if (tagList.some(tId => a.has(tId))) return true
        }
        return false
    },
    [FilterOperator.containsNot]: (a: Set<number>, b: number[][]) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return true;
        return !b.some(e => e.some(tagId => a.has(tagId)))
    },
    [FilterOperator.equal]: (a: any, b: any) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;
        return a == b
    },
    [FilterOperator.equalNot]: (a: any, b: any) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return true;
        return a != b
    },
    [FilterOperator.isFalse]: (a: any) => {
        if (isEmpty(a)) return true;
        return a == false
    },
    [FilterOperator.isTrue]: (a: any) => a,
    [FilterOperator.isSet]: (a: any) => !isEmpty(a),
    [FilterOperator.notSet]: (a: any) => isEmpty(a),
    [FilterOperator.startsWith]: (a: string, b: string) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;
        return a.startsWith(b)
    },
    [FilterOperator.like]: (a: string, b: string) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;
        return a.match(b)
    }

}

function createFilterGroup() {
    let filter: FilterGroup = {
        filters: [],
        groupOperator: FilterOperator.or,
        depth: 0,
        isGroup: true,
        id: -1
    }
    return filter
}

export function createFilterState(): FilterState {
    const group = createFilterGroup()
    const state = reactive({
        folders: [],
        filter: group
    })
    return state
}

function defaultOperator(propertyType: PropertyType) {
    switch (propertyType) {
        case PropertyType.checkbox:
            return FilterOperator.isTrue

        case PropertyType.multi_tags:
        case PropertyType.tag:
            return FilterOperator.containsAny

        case PropertyType.date:
            return FilterOperator.greater

        default:
            return FilterOperator.equal
    }
}

function isEmpty(value: any) {
    return value === undefined || value === '' || (Array.isArray(value) && value.length === 0) || value === null
}


function computeFilter(filter: Filter, propertyValue: any) {
    // console.log('compute filter')
    let opFnc = operatorMap[filter.operator]
    let res = opFnc(propertyValue, filter.value)
    return res
}

function computeGroupFilter(image: Image, filterGroup: FilterGroup) {
    // console.log('compute group filter')
    if (filterGroup.filters.length == 0) {
        return true
    }

    let groupOp = filterGroup.groupOperator ? filterGroup.groupOperator : FilterOperator.and
    let res = groupOp == FilterOperator.and ? true : false
    let groupOperatorFnc = operatorMap[groupOp]

    // console.log(groupOp)

    for (let filter of filterGroup.filters) {
        // console.log('resssss ' + res)
        if (filter.isGroup) {
            // console.log('subgroup')
            res = groupOperatorFnc(computeGroupFilter(image, filter), res)
        }
        else {
            let nfilter = { ...filter } as Filter
            let propId = nfilter.propertyId
            let propType = globalStore.properties[propId].type

            let property = image.properties[propId]
            let propertyValue = property ? property.value : undefined

            if (Array.isArray(nfilter.value) && nfilter.value.length > 0 && isTag(propType)) {
                let filterValue = nfilter.value as number[]

                const tagSet = filterValue.map((v: number) => Array.from(getTagChildren(globalStore.tags[propId][v])))
                nfilter.value = tagSet
                if (!isEmpty(propertyValue)) {
                    propertyValue = new Set(propertyValue)
                }
            }

            let subRes = computeFilter(nfilter, propertyValue)
            res = groupOperatorFnc(res, subRes)
        }
    }
    return res
}

export class FilterManager {
    state: FilterState
    result: FilterResult

    filterIndex: { [filterId: number]: AFilter }

    lastImages: Image[]
    onChange: EventEmitter

    constructor(state?: FilterState) {
        this.filterIndex = {}
        this.result = { images: [] }
        this.onChange = new EventEmitter()

        if (state) {
            this.state = state
            this.recursiveRegister(this.state.filter)
        } else {
            this.initFilterState()
        }

        this.verifyFilter()
    }

    filter(images: Image[], emit?: boolean) {
        console.time('Filter')
        this.lastImages = images
        let filtered = images
        if (this.state.folders.length > 0) {
            const folderSet = new Set(this.state.folders)
            filtered = filtered.filter(img => folderSet.has(img.folder_id))
        }
        this.result.images = filtered.filter(img => computeGroupFilter(img, this.state.filter))
        console.timeEnd('Filter')

        if (emit) this.onChange.emit(this.result)

        return this.result
    }

    update(emit?: boolean) {
        if (!this.lastImages) return
        this.filter(this.lastImages)
        if (emit) this.onChange.emit(this.result)
    }

    setFolders(folderIds: number[]) {
        this.state.folders = folderIds
    }

    addNewFilterGroup(parentId: number = undefined) {
        let group = this.createFilterGroup()

        if (parentId != undefined) {
            let parent = this.filterIndex[parentId] as FilterGroup
            if (parent == undefined) throw 'Invalid Parent !'
            parent.filters.push(group)
            const reactiveGroup = parent.filters[parent.filters.length - 1]
            this.registerFilter(reactiveGroup)
            return reactiveGroup
        }

        const mainFilter = this.state.filter
        mainFilter.filters.push(group)
        const reactiveGroup = mainFilter.filters[mainFilter.filters.length - 1]
        this.registerFilter(reactiveGroup)
        return reactiveGroup
    }

    addNewFilter(propertyId: number, parentId: number = undefined) {
        let filter = this.createFilter(propertyId)

        if (parentId != undefined) {
            let group = this.filterIndex[parentId] as FilterGroup

            if (group == undefined) throw new Error('group is undefined')
            if (!group.isGroup) throw new TypeError('Parent filter is not a FilterGroup, cannot add filter to it')

            group.filters.push(filter)
            const reactiveFilter = group.filters[group.filters.length - 1]
            this.registerFilter(reactiveFilter)
            return reactiveFilter
        }

        const mainFilter = this.state.filter
        mainFilter.filters.push(filter)
        // get the reactive version
        const reactiveFilter = mainFilter.filters[mainFilter.filters.length - 1]
        this.registerFilter(reactiveFilter)
        return reactiveFilter
    }

    deleteFilter(filterId: number) {
        Object.values(this.filterIndex).forEach(f => {
            if (!f.isGroup) return
            const group = f as FilterGroup
            group.filters = group.filters.filter(f => f.id != filterId)
        })

        delete this.filterIndex[filterId]
    }



    updateFilter(filterId: number, update: FilterUpdate) {
        if (this.filterIndex[filterId] == undefined || this.filterIndex[filterId].isGroup) return
        const filter = this.filterIndex[filterId] as Filter

        if(update.propertyId != undefined) {
            this.changeFilter(filter, update.propertyId)
        }

        const type = globalStore.properties[filter.propertyId].type
        if(update.operator != undefined && availableOperators(type).includes(update.operator)) {
            filter.operator = update.operator
        }

        if(update.value) {
            filter.value = update.value
        } else {
            filter.value = propertyDefault(type)
        }
    }

    private changeFilter(filter: Filter, propertyId: number) {
        const newFilter = this.createFilter(propertyId)
        newFilter.id = filter.id
        Object.assign(filter, newFilter)
    }

    // used to remove properties that doesnt exist anymore from filters 
    public verifyFilter() {
        const recurive = (group: FilterGroup) => {
            const toRem = new Set()
            group.filters.forEach(f => {
                if (f.isGroup) {
                    recurive(f)
                }
                else {
                    const filter = f as Filter
                    if (globalStore.properties[filter.propertyId] == undefined) {
                        toRem.add(filter.id)
                    }
                }
            })
            group.filters = group.filters.filter(f => !toRem.has(f.id))
        }
        recurive(this.state.filter)
    }

    private initFilterState() {
        const state = createFilterState()
        this.state = state
        this.registerFilter(this.state.filter)
    }

    private registerFilter(filter: AFilter) {
        if (filter.id >= 0) {
            console.error('registerFilter should not receive a filter with valid id')
        }
        filter.id = this.nextIndex()
        this.filterIndex[filter.id] = filter
        return this.filterIndex[filter.id]
    }

    private createFilter(propertyId: number) {
        let property = globalStore.properties[propertyId]

        let filter: Filter = {
            propertyId: property.id,
            operator: defaultOperator(property.type),
            value: propertyDefault(property.type),
            id: -1
        }
        return filter
    }

    private createFilterGroup() {
        let filter: FilterGroup = {
            filters: [],
            groupOperator: FilterOperator.or,
            depth: 0,
            isGroup: true,
            id: -1
        }
        return filter
    }

    private nextIndex() {
        if (this.state.filter == undefined || Object.keys(this.filterIndex).length == 0) {
            return 0
        }
        return Math.max(...Object.keys(this.filterIndex).map(Number)) + 1
    }

    private recursiveRegister(filter: AFilter) {
        if (filter.id == undefined || filter.id == -1) {
            filter = this.registerFilter(filter)
        } else {
            this.filterIndex[filter.id] = filter
        }

        if (!filter.isGroup) return

        const group = filter as FilterGroup
        group.filters.forEach(g => this.recursiveRegister(g))
    }
}