/**
 * The FilterManager allows to create complexe filters to select a subset of images
 * The FilterState allows the user to save all current filtering options
 * The FilterState must be treated as a reactive Readonly object outside of the FilterManager class
 * Images are first filtered by folders then by properties
 */

import { propertyDefault } from "@/data/builder";
import { useDataStore } from "@/data/dataStore";
import { Instance, PropertyIndex, PropertyType, TagIndex } from "@/data/models";
import { useProjectStore } from "@/data/projectStore";

import { EventEmitter, getTagChildren, isTag, objValues } from "@/utils/utils";
import { reactive, toRefs } from "vue";


export function operatorHasInput(operator: FilterOperator) {
    switch (operator) {
        case FilterOperator.contains:
        case FilterOperator.containsAll:
        case FilterOperator.containsAny:
        case FilterOperator.containsNot:
        case FilterOperator.equal:
        case FilterOperator.equalNot:
        case FilterOperator.geq:
        case FilterOperator.greater:
        case FilterOperator.leq:
        case FilterOperator.lower:
        case FilterOperator.like:
        case FilterOperator.startsWith:
            return true
        default:
            return false
    }
}

export function availableOperators(propertyType: PropertyType): Array<FilterOperator> {
    switch (propertyType) {
        case PropertyType.checkbox:
            return [FilterOperator.isTrue, FilterOperator.isFalse]
        case PropertyType.color:
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.equal, FilterOperator.equalNot]
        case PropertyType.date:
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.equal, FilterOperator.equalNot, FilterOperator.leq, FilterOperator.lower, FilterOperator.greater, FilterOperator.geq]
        case PropertyType.image_link:
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.equal, FilterOperator.equalNot]
        case PropertyType.multi_tags:
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.containsAll, FilterOperator.containsAny, FilterOperator.containsNot]
        case PropertyType.number:
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.equal, FilterOperator.equalNot, FilterOperator.leq, FilterOperator.lower, FilterOperator.greater, FilterOperator.geq]
        case PropertyType.path:
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.equal, FilterOperator.equalNot, FilterOperator.startsWith, FilterOperator.like]
        case PropertyType.string:
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.equal, FilterOperator.equalNot, FilterOperator.startsWith, FilterOperator.like]
        case PropertyType.tag:
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.containsAny, FilterOperator.containsNot]
        case PropertyType.url:
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.equal, FilterOperator.equalNot, FilterOperator.like, FilterOperator.startsWith]
        case PropertyType._ahash:
        case PropertyType._sha1:
            return [FilterOperator.equal, FilterOperator.equalNot]
        case PropertyType._width:
        case PropertyType._height:
            return [FilterOperator.equal, FilterOperator.lower, FilterOperator.leq, FilterOperator.greater, FilterOperator.geq]
        case PropertyType._id:
            return [FilterOperator.equal, FilterOperator.equalNot]
        default:
            return []
    }
}

export interface AFilter {
    id: number
    isGroup?: boolean
}

export interface Filter extends AFilter {
    propertyId: number,
    operator: FilterOperator,
    value: any,
    // strict: boolean // strict to true will be an "OR" filter, set to false it would be an "AND"
    isGroup?: false
}

export interface FilterGroup extends AFilter {
    filters: Array<Filter | FilterGroup>
    groupOperator: FilterOperator.and | FilterOperator.or
    depth: number
    isGroup: true
}

export interface CollectionState {
    isDirty: boolean
}

export interface FilterState {
    folders: number[]
    filter: FilterGroup
    query: string
}

export interface FilterResult {
    images: Instance[]
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
        if (b == undefined) return true
        if (a == undefined) return false
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
    [FilterOperator.containsAll]: (a: number[], b: Set<number>[]) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;

        for (let tag of a) {
            for (let tagSet of b) {
                if (!tagSet.has(tag)) {
                    return false
                }
            }
        }
        return true
    },
    [FilterOperator.containsAny]: (a: number[], b: Set<number>[]) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;
        // return a.some(e => b.includes(e))

        for (let tag of a) {
            for (let tagSet of b) {
                if (tagSet.has(tag)) {
                    return true
                }
            }
        }
        return false
    },
    [FilterOperator.containsNot]: (a: number[], b: Set<number>[]) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return true;
        for (let tag of a) {
            for (let tagSet of b) {
                if (tagSet.has(tag)) {
                    return false
                }
            }
        }
        return true
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
        groupOperator: FilterOperator.and,
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
        filter: group,
        query: ''
    })
    return state
}

function defaultOperator(propertyType: PropertyType) {
    switch (propertyType) {
        case PropertyType.checkbox:
            return FilterOperator.isTrue

        case PropertyType.color:
        case PropertyType.image_link:
        case PropertyType.number:
        case PropertyType.string:
        case PropertyType.path:
        case PropertyType.url:
        case PropertyType.multi_tags:
        case PropertyType.tag:
            return FilterOperator.isSet

        case PropertyType.date:
            return FilterOperator.greater
        default:
            return FilterOperator.equal
    }
}

function isEmpty(value: any) {
    return value === undefined || value === '' || (Array.isArray(value) && value.length === 0) || value === null
}

function applyFilter(filter: Filter, instances: Instance[], properties: PropertyIndex, tags: TagIndex) {
    const property = properties[filter.propertyId]
    const values = instances.map(i => i.properties[property.id])
    const operatorFunc = operatorMap[filter.operator]
    let filterValue = filter.value

    if (isTag(property.type) && filterValue) {
        const childrens = filterValue.map(v => new Set([...tags[v].allChildren, v]))
        filterValue = new Set(childrens)
    }
    if (property.type == PropertyType.date) {
        if (filterValue) {
            filterValue = new Date(filterValue)
        }
        for (let [i, v] of values.entries()) {
            if (!v) continue
            values[i] = new Date(v)
        }
    }
    if (property.type == PropertyType.string) {
        if (filterValue) {
            filterValue = filterValue.toLowerCase()
        }
        for (let [i, v] of values.entries()) {
            if (!v) continue
            values[i] = v.toLowerCase()
        }
    }
    const valid = []
    const reject = []
    for (let i = 0; i < instances.length; i++) {
        if (operatorFunc(values[i], filterValue)) {
            valid.push(instances[i])
        } else {
            reject.push(instances[i])
        }
    }
    return { valid, reject }
}

function applyGroupFilter(group: FilterGroup, instances: Instance[], properties: PropertyIndex, tags: TagIndex) {
    if (!group.filters.length) {
        return { valid: instances, reject: [] }
    }
    let valid = []
    let reject = []

    let test = [...instances]

    for (let filter of group.filters) {
        let res
        if (filter.isGroup) {
            res = applyGroupFilter(filter, test, properties, tags)
        } else {
            res = applyFilter(filter as Filter, test, properties, tags)
        }
        for(let v of res.valid) {
            valid.push(v)
        }
        for(let r of res.reject) {
            reject.push(r)
        }

        if (group.groupOperator == FilterOperator.and) {
            test = valid
            valid = []
        } else {
            test = reject
            reject = []
        }
    }
    if (group.groupOperator == FilterOperator.and) {
        valid = test
    } else {
        reject = test
    }

    return { valid, reject }
}

export class FilterManager {
    state: FilterState
    result: FilterResult

    lastFilterId: number
    filterIndex: { [filterId: number]: AFilter }

    lastImages: Instance[]
    onChange: EventEmitter
    onDirty: EventEmitter

    constructor(state?: FilterState) {
        this.lastFilterId = null
        this.filterIndex = {}
        this.result = { images: [] }
        this.onChange = new EventEmitter()
        this.onDirty = new EventEmitter()
        if (state) {
            this.state = reactive(state)
            this.recursiveRegister(this.state.filter)
        } else {
            this.initFilterState()
        }

        this.verifyState(useDataStore().properties)
    }

    load(state: FilterState) {
        Object.assign(this.state, toRefs(state))
        this.clear()

        this.filterIndex = {}
        this.recursiveRegister(this.state.filter)
    }

    clear() {
        this.result = { images: [] }
    }

    async filter(images: Instance[], emit?: boolean) {
        console.time('Filter')
        this.lastImages = images
        const res = this.filterInstances(images)
        // this.result.images = filtered.filter(img => computeGroupFilter(img, this.state.filter, data.properties, data.tags))
        this.result.images = res.valid
        console.timeEnd('Filter')

        if (emit) this.onChange.emit(this.result)

        return this.result
    }

    async update(emit?: boolean) {
        if (!this.lastImages) return
        await this.filter(this.lastImages)
        if (emit) this.onChange.emit(this.result)
    }

    async updateSelection(instanceIds: Set<number>) {
        console.time('UpdateFilter')
        const data = useDataStore()
        const instances = Array.from(instanceIds).map(i => data.instances[i])
        const valid = []
        for(let instance of this.result.images) {
            if(instanceIds.has(instance.id)) continue
            valid.push(instance.id)
        }
        const updated = this.filterInstances(instances)
        for(let instance of updated.valid) {
            valid.push(instance.id)
        }
        this.result.images = valid.map(id => data.instances[id])
        console.timeEnd('UpdateFilter')

        const res = {updated: new Set(updated.valid.map(i => i.id)), removed: new Set(updated.reject.map(i => i.id))}
        return res
    }

    private filterInstances(instances: Instance[]) {
        const data = useDataStore()
        let filtered = instances

        if (this.state.query) {
            const query = this.state.query.toLocaleLowerCase()
            const project = useProjectStore()
            const props = objValues(data.properties)
            const textProps = props.filter(p => p.type == PropertyType.string)
            const tagProps = props.filter(p => isTag(p.type))
            filtered = filtered.filter(img => {
                for (let p of textProps) {
                    if (img.properties[p.id] && img.properties[p.id] && img.properties[p.id].toLocaleLowerCase().includes(query)) {
                        return true
                    }
                }
                for (let p of tagProps) {
                    const value = img.properties[p.id]
                    if (!value) continue
                    const tagNames = value.map(tId => data.tags[tId].value.toLocaleLowerCase())
                    for (let name of tagNames) {
                        if (name.includes(query)) {
                            return true
                        }
                    }
                }
                return false
            })
        }

        if (this.state.folders.length > 0) {
            const folderSet = new Set(this.state.folders)
            filtered = filtered.filter(img => folderSet.has(img.folderId))
        }
        const res = applyGroupFilter(this.state.filter, filtered, data.properties, data.tags)
        return res
    }

    setFolders(folderIds: number[]) {
        this.state.folders = folderIds
    }

    setQuery(query: string) {
        this.state.query = query
    }

    addNewFilterGroup(parentId: number = undefined) {
        let group = createFilterGroup()

        if (parentId != undefined) {
            let parent = this.filterIndex[parentId] as FilterGroup
            if (parent == undefined) throw 'Invalid Parent !'
            parent.filters.push(group)
            const reactiveGroup = parent.filters[parent.filters.length - 1]
            this.registerFilter(reactiveGroup)
            this.onDirty.emit()
            return reactiveGroup
        }

        const mainFilter = this.state.filter
        mainFilter.filters.push(group)
        const reactiveGroup = mainFilter.filters[mainFilter.filters.length - 1]
        this.registerFilter(reactiveGroup)
        this.onDirty.emit()
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
            this.onDirty.emit()
            return reactiveFilter
        }

        const mainFilter = this.state.filter
        mainFilter.filters.push(filter)
        // get the reactive version
        const reactiveFilter = mainFilter.filters[mainFilter.filters.length - 1]
        this.registerFilter(reactiveFilter)
        this.onDirty.emit()
        return reactiveFilter
    }

    deleteFilter(filterId: number) {
        Object.values(this.filterIndex).forEach(f => {
            if (!f.isGroup) return
            const group = f as FilterGroup
            group.filters = group.filters.filter(f => f.id != filterId)
        })
        delete this.filterIndex[filterId]
        this.onDirty.emit()
    }



    updateFilter(filterId: number, update: FilterUpdate) {
        const data = useDataStore()
        if (this.filterIndex[filterId] == undefined || this.filterIndex[filterId].isGroup) return
        const filter = this.filterIndex[filterId] as Filter

        if (update.propertyId != undefined) {
            this.changeFilter(filter, update.propertyId)
        }

        const type = data.properties[filter.propertyId].type
        if (update.operator != undefined && availableOperators(type).includes(update.operator)) {
            filter.operator = update.operator
        }

        if (update.value) {
            filter.value = update.value
        } else {
            filter.value = propertyDefault(type)
        }
        this.onDirty.emit()
    }

    updateFilterGroup(filterId: number, operator: FilterOperator.or | FilterOperator.and) {
        if (this.filterIndex[filterId] == undefined || !this.filterIndex[filterId].isGroup) return
        const group = this.filterIndex[filterId] as FilterGroup
        group.groupOperator = operator
        this.onDirty.emit()
    }

    private changeFilter(filter: Filter, propertyId: number) {
        const newFilter = this.createFilter(propertyId)
        newFilter.id = filter.id
        Object.assign(filter, newFilter)
    }

    // used to remove properties that doesnt exist anymore from filters 
    public verifyState(properties: PropertyIndex) {
        const recursive = (group: FilterGroup) => {
            const toRem = new Set()
            group.filters.forEach(f => {
                if (f.isGroup) {
                    recursive(f)
                }
                else {
                    const filter = f as Filter
                    if (properties[filter.propertyId] == undefined) {
                        toRem.add(filter.id)
                    }
                }
            })
            group.filters = group.filters.filter(f => !toRem.has(f.id))
        }
        recursive(this.state.filter)
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
        const data = useDataStore()
        let property = data.properties[propertyId]

        let filter: Filter = {
            propertyId: property.id,
            operator: defaultOperator(property.type),
            value: propertyDefault(property.type),
            id: -1
        }
        return filter
    }

    private nextIndex() {
        const ids = Object.keys(this.filterIndex).map(Number)
        let index = 0
        if (ids.length) {
            index = Math.max(...ids) + 1
        }
        if (index === this.lastFilterId) {
            index += 1
        }
        this.lastFilterId = index
        return index
    }

    private recursiveRegister(filter: AFilter) {
        if (filter.id < 0) {
            filter = this.registerFilter(filter)
        } else {
            this.filterIndex[filter.id] = filter
        }

        if (!filter.isGroup) return

        const group = filter as FilterGroup
        group.filters.forEach(g => this.recursiveRegister(g))
    }
}