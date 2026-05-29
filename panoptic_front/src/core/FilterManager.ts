import { useActionStore } from "@/data/actionStore";
import { apiCallActions } from "@/data/apiProjectRoutes";
import { propertyDefault } from "@/data/builder";
import { useColumnStore } from "@/data/columnStore";
import { deletedID, ActionContext, ExecuteActionPayload, FolderIndex, PropertyIndex, PropertyType, TagIndex, TextQuery } from "@/data/models";
import { EventEmitter, isTag, objValues } from "@/utils/utils";
import { reactive, toRefs } from "vue";

const fullTextTypes = new Set([PropertyType.string, PropertyType.path, PropertyType.url])

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
        case FilterOperator.notLike:
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
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.equal, FilterOperator.equalNot, FilterOperator.startsWith, FilterOperator.like, FilterOperator.notLike]
        case PropertyType.string:
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.equal, FilterOperator.equalNot, FilterOperator.startsWith, FilterOperator.like, FilterOperator.notLike]
        case PropertyType.tag:
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.containsAny, FilterOperator.containsNot]
        case PropertyType.url:
            return [FilterOperator.isSet, FilterOperator.notSet, FilterOperator.equal, FilterOperator.equalNot, FilterOperator.like, FilterOperator.notLike, FilterOperator.startsWith]
        case PropertyType._ahash:
        case PropertyType._sha1:
            return [FilterOperator.equal, FilterOperator.equalNot, FilterOperator.like, FilterOperator.notLike]
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
    propertyId: number
    operator: FilterOperator
    value: any
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
    query: TextQuery
}

export interface FilterResult {
    slots: Int32Array
}

export interface FilterUpdate {
    propertyId?: number
    operator?: FilterOperator
    value?: any
}

export interface FilterContext {
    properties: PropertyIndex
    tags: TagIndex
    folders: FolderIndex
}

export enum FilterOperator {
    equal = "equal",
    equalNot = "equalNot",
    like = "like",
    notLike = 'notLike',
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
    [FilterOperator.geq]:         (a: any, b: any) => b == undefined ? true  : a == undefined ? false : a >= b,
    [FilterOperator.leq]:         (a: any, b: any) => b == undefined ? true  : a == undefined ? false : a <= b,
    [FilterOperator.lower]:       (a: any, b: any) => b == undefined ? true  : a == undefined ? false : a < b,
    [FilterOperator.greater]:     (a: any, b: any) => b == undefined ? true  : a == undefined ? false : a > b,
    [FilterOperator.and]:         (a: boolean, b: boolean) => a && b,
    [FilterOperator.or]:          (a: boolean, b: boolean) => a || b,
    [FilterOperator.contains]:    (a: string, b: string) => isEmpty(b) ? true : isEmpty(a) ? false : a.includes(b),
    [FilterOperator.equal]:       (a: any, b: any)  => isEmpty(b) ? true : isEmpty(a) ? false : a == b,
    [FilterOperator.equalNot]:    (a: any, b: any)  => isEmpty(b) ? true : isEmpty(a) ? true  : a != b,
    [FilterOperator.isFalse]:     (a: any) => isEmpty(a) ? true : a == false,
    [FilterOperator.isTrue]:      (a: any) => !!a,
    [FilterOperator.isSet]:       (a: any) => !isEmpty(a),
    [FilterOperator.notSet]:      (a: any) => isEmpty(a),
    [FilterOperator.startsWith]:  (a: string, b: string) => isEmpty(b) ? true : isEmpty(a) ? false : a.startsWith(b),
    [FilterOperator.like]:        (a: string, b: string) => isEmpty(b) ? true : isEmpty(a) ? false : !!a.match(b),
    [FilterOperator.notLike]:     (a: string, b: string) => isEmpty(b) ? true : isEmpty(a) ? false : !a.match(b),
    [FilterOperator.containsAll]: (a: number[], b: Set<number>[]) => {
        if (isEmpty(b)) return true
        if (isEmpty(a)) return false
        for (const tag of a)
            for (const tagSet of b)
                if (!tagSet.has(tag)) return false
        return true
    },
    [FilterOperator.containsAny]: (a: number[], b: Set<number>[]) => {
        if (isEmpty(b)) return true
        if (isEmpty(a)) return false
        for (const tag of a)
            for (const tagSet of b)
                if (tagSet.has(tag)) return true
        return false
    },
    [FilterOperator.containsNot]: (a: number[], b: Set<number>[]) => {
        if (isEmpty(b)) return true
        if (isEmpty(a)) return true
        for (const tag of a)
            for (const tagSet of b)
                if (tagSet.has(tag)) return false
        return true
    },
}

function createFilterGroup(): FilterGroup {
    return { filters: [], groupOperator: FilterOperator.and, depth: 0, isGroup: true, id: -1 }
}

export function createFilterState(): FilterState {
    return reactive({ folders: [], filter: createFilterGroup(), query: { type: 'text', text: '' } })
}

function defaultOperator(propertyType: PropertyType): FilterOperator {
    switch (propertyType) {
        case PropertyType.checkbox: return FilterOperator.isTrue
        case PropertyType.date:     return FilterOperator.greater
        default:                    return FilterOperator.isSet
    }
}

function isEmpty(value: any) {
    return value === undefined || value === '' || (Array.isArray(value) && value.length === 0) || value === null
}

// slots: column-store slot indices — no slotMap lookup needed, slot IS the index.
function applyFilter(filter: Filter, slots: number[], properties: PropertyIndex, tags: TagIndex) {
    const col = useColumnStore()
    const property = properties[filter.propertyId]
    const values: any[] = slots.map(s => col.readSlot(property.id, s))
    const operatorFunc = operatorMap[filter.operator]
    let filterValue = filter.value

    if (isTag(property.type) && filterValue) {
        filterValue = filterValue.map((v: number) => new Set([...tags[v].allChildren, v]))
    }
    if (property.type == PropertyType.date) {
        if (filterValue) filterValue = new Date(filterValue)
        for (let [i, v] of values.entries()) { if (v) values[i] = new Date(v) }
    }
    if (property.type == PropertyType.string) {
        if (filterValue) filterValue = filterValue.toLowerCase()
        for (let [i, v] of values.entries()) { if (v) values[i] = v.toLowerCase() }
    }

    const valid: number[] = []
    const reject: number[] = []
    for (let i = 0; i < slots.length; i++) {
        if (operatorFunc(values[i], filterValue)) valid.push(slots[i])
        else reject.push(slots[i])
    }
    return { valid, reject }
}

function applyGroupFilter(group: FilterGroup, slots: number[], properties: PropertyIndex, tags: TagIndex) {
    if (!group.filters.length) return { valid: slots, reject: [] as number[] }

    let valid: number[] = []
    let reject: number[] = []
    let test = [...slots]

    for (const filter of group.filters) {
        const res = filter.isGroup
            ? applyGroupFilter(filter as FilterGroup, test, properties, tags)
            : applyFilter(filter as Filter, test, properties, tags)

        valid.push(...res.valid)
        reject.push(...res.reject)

        if (group.groupOperator == FilterOperator.and) { test = valid; valid = [] }
        else                                            { test = reject; reject = [] }
    }
    if (group.groupOperator == FilterOperator.and) valid = test
    else reject = test
    return { valid, reject }
}

export class FilterManager {
    ctx: FilterContext
    state: FilterState
    result: FilterResult

    lastFilterId: number
    filterIndex: { [filterId: number]: AFilter }

    lastSlots: Int32Array
    onResultChange: EventEmitter
    onStateChange: EventEmitter

    constructor(ctx: FilterContext, state?: FilterState) {
        this.ctx = ctx
        this.lastFilterId = null
        this.filterIndex = {}
        this.result = { slots: new Int32Array(0) }
        this.onResultChange = new EventEmitter()
        this.onStateChange = new EventEmitter()

        if (state) {
            this.state = reactive(state)
            this.recursiveRegister(this.state.filter)
        } else {
            this.initFilterState()
        }
        this.verifyState(ctx.properties, ctx.folders)
    }

    // ── Column requirements ────────────────────────────────────────────────

    getRequiredColumns(): number[] {
        const ids = new Set<number>()
        const collect = (group: FilterGroup) => {
            for (const f of group.filters) {
                if (f.isGroup) collect(f as FilterGroup)
                else ids.add((f as Filter).propertyId)
            }
        }
        collect(this.state.filter)
        if (this.state.folders.length > 0) {
            const folderProp = objValues(this.ctx.properties).find(p => p.systemKey === 'folder')
            if (folderProp) ids.add(folderProp.id)
        }
        return [...ids]
    }

    private async _ensureColumns(): Promise<void> {
        const col = useColumnStore()
        const filterCols = this.getRequiredColumns()
        const queryCols = this.state.query?.text
            ? objValues(this.ctx.properties).filter(p => fullTextTypes.has(p.type) || isTag(p.type)).map(p => p.id)
            : []
        const all = [...new Set([...filterCols, ...queryCols])]
        await Promise.all(all.map(id => col.requireFullColumn(id)))
    }

    // ── Public API ─────────────────────────────────────────────────────────

    load(state: FilterState) {
        Object.assign(this.state, toRefs(state))
        this.clear()
        this.filterIndex = {}
        this.recursiveRegister(this.state.filter)
    }

    clear() {
        this.result = { slots: new Int32Array(0) }
    }

    async filter(slots: Int32Array, emit?: boolean) {
        console.time('Filter')
        this.lastSlots = slots
        const res = await this.filterSlots(Array.from(slots))
        this.result.slots = new Int32Array(res.valid)
        console.timeEnd('Filter')
        if (emit) this.onResultChange.emit(this.result)
        return this.result
    }

    async update(slots: Int32Array, emit?: boolean) {
        await this.filter(slots)
        if (emit) this.onResultChange.emit(this.result)
        return this.result
    }

    // Incremental update: called with dirty instance IDs from data.onChange.
    // Converts IDs → slots, re-filters only the dirty subset, splices result.
    async updateSelection(instanceIds: Set<number>) {
        console.time('UpdateFilter')
        const col = useColumnStore()

        const dirtySlots = new Set<number>()
        for (const id of instanceIds) {
            const slot = col.slotMap.get(id)
            if (slot !== undefined) dirtySlots.add(slot)
        }

        // Keep current result slots that are not dirty
        const valid: number[] = []
        for (let i = 0; i < this.result.slots.length; i++) {
            const s = this.result.slots[i]
            if (!dirtySlots.has(s)) valid.push(s)
        }

        // Re-filter the dirty slots
        const updated = await this.filterSlots([...dirtySlots])
        for (const s of updated.valid) valid.push(s)
        this.result.slots = new Int32Array(valid)

        console.timeEnd('UpdateFilter')

        // Return instance IDs (sort/group managers use them for their own incremental updates)
        return {
            updated: new Set(updated.valid.map(s => col.instanceIds[s])),
            removed: new Set(updated.reject.map(s => col.instanceIds[s])),
        }
    }

    private async filterSlots(slots: number[]) {
        const col = useColumnStore()
        await this._ensureColumns()

        let filtered = slots

        if (this.state.query?.text) {
            filtered = await filterQuery(filtered, this.state.query, this.ctx.properties, this.ctx.tags)
        }
        if (this.state.folders.length > 0) {
            const folderSet = new Set(this.state.folders)
            const folderProp = objValues(this.ctx.properties).find(p => p.systemKey === 'folder')
            if (folderProp) {
                filtered = filtered.filter(s => folderSet.has(col.readSlot(folderProp.id, s)))
            }
        }
        return applyGroupFilter(this.state.filter, filtered, this.ctx.properties, this.ctx.tags)
    }

    setFolders(folderIds: number[]) { this.state.folders = folderIds }
    setQuery(query: TextQuery)       { this.state.query = query }

    addNewFilterGroup(parentId?: number) {
        const group = createFilterGroup()
        const target = parentId != undefined
            ? (this.filterIndex[parentId] as FilterGroup) ?? this.state.filter
            : this.state.filter
        target.filters.push(group)
        const reactive = target.filters[target.filters.length - 1]
        this.registerFilter(reactive)
        this.onStateChange.emit()
        return reactive
    }

    addNewFilter(propertyId: number, parentId?: number) {
        const filter = this.createFilter(propertyId)
        const target = parentId != undefined
            ? (this.filterIndex[parentId] as FilterGroup) ?? this.state.filter
            : this.state.filter
        target.filters.push(filter)
        const reactive = target.filters[target.filters.length - 1]
        this.registerFilter(reactive)
        this.onStateChange.emit()
        return reactive
    }

    deleteFilter(filterId: number) {
        Object.values(this.filterIndex).forEach(f => {
            if (!f.isGroup) return
            const g = f as FilterGroup
            g.filters = g.filters.filter(f => f.id != filterId)
        })
        delete this.filterIndex[filterId]
        this.onStateChange.emit()
    }

    updateFilter(filterId: number, update: FilterUpdate) {
        if (this.filterIndex[filterId] == undefined || this.filterIndex[filterId].isGroup) return
        const filter = this.filterIndex[filterId] as Filter

        if (update.propertyId != undefined) this.changeFilter(filter, update.propertyId)

        const type = this.ctx.properties[filter.propertyId].type
        if (update.operator != undefined && availableOperators(type).includes(update.operator)) {
            filter.operator = update.operator
        }
        filter.value = update.value ? update.value : propertyDefault(type)
        this.onStateChange.emit()
    }

    updateFilterGroup(filterId: number, operator: FilterOperator.or | FilterOperator.and) {
        if (this.filterIndex[filterId] == undefined || !this.filterIndex[filterId].isGroup) return
        ;(this.filterIndex[filterId] as FilterGroup).groupOperator = operator
        this.onStateChange.emit()
    }

    public verifyState(properties: PropertyIndex, folders: FolderIndex) {
        const recursive = (group: FilterGroup) => {
            const toRem = new Set<number>()
            group.filters.forEach(f => {
                if (f.isGroup) recursive(f as FilterGroup)
                else {
                    const filter = f as Filter
                    if (!properties[filter.propertyId] || properties[filter.propertyId].id == deletedID)
                        toRem.add(filter.id)
                }
            })
            group.filters = group.filters.filter(f => !toRem.has(f.id))
        }
        recursive(this.state.filter)
        this.state.folders = this.state.folders.filter(fId => folders[fId])
    }

    private initFilterState() {
        this.state = createFilterState()
        this.registerFilter(this.state.filter)
    }

    private changeFilter(filter: Filter, propertyId: number) {
        const newFilter = this.createFilter(propertyId)
        newFilter.id = filter.id
        Object.assign(filter, newFilter)
    }

    private registerFilter(filter: AFilter) {
        if (filter.id >= 0) console.error('registerFilter should not receive a filter with valid id')
        filter.id = this.nextIndex()
        this.filterIndex[filter.id] = filter
        return this.filterIndex[filter.id]
    }

    private createFilter(propertyId: number): Filter {
        const property = this.ctx.properties[propertyId]
        return { propertyId: property.id, operator: defaultOperator(property.type), value: propertyDefault(property.type), id: -1 }
    }

    private nextIndex() {
        const ids = Object.keys(this.filterIndex).map(Number)
        let index = ids.length ? Math.max(...ids) + 1 : 0
        if (index === this.lastFilterId) index += 1
        this.lastFilterId = index
        return index
    }

    private recursiveRegister(filter: AFilter) {
        if (filter.id < 0) filter = this.registerFilter(filter)
        else this.filterIndex[filter.id] = filter
        if (!filter.isGroup) return
        ;(filter as FilterGroup).filters.forEach(g => this.recursiveRegister(g))
    }
}

async function filterQuery(slots: number[], query: TextQuery, properties: PropertyIndex, tags: TagIndex): Promise<number[]> {
    if (!query?.text) return slots

    const actions = useActionStore()
    const props = objValues(properties)
    const textProps = props.filter(p => fullTextTypes.has(p.type))
    const tagProps  = props.filter(p => isTag(p.type))

    if (query.type === 'text')  return filterByText(slots, query.text, textProps, tagProps, tags)
    if (query.type === 'regex') return filterByRegex(slots, query.text, textProps, tagProps, tags)
    if (query.ctx && actions.index[query.type]) return filterByPlugin(slots, query.type, query.ctx)
    return slots
}

function filterByText(slots: number[], queryText: string, textProps: any[], tagProps: any[], tags: TagIndex): number[] {
    const col = useColumnStore()
    const query = queryText.toLocaleLowerCase()
    return slots.filter(s => {
        for (const p of textProps) {
            const val: string = col.readSlot(p.id, s)
            if (val && val.toLocaleLowerCase().includes(query)) return true
        }
        for (const p of tagProps) {
            const value: number[] = col.readSlot(p.id, s)
            if (!value) continue
            for (const tId of value) {
                if (tags[tId]?.value.toLocaleLowerCase().includes(query)) return true
            }
        }
        return false
    })
}

function filterByRegex(slots: number[], queryText: string, textProps: any[], tagProps: any[], tags: TagIndex): number[] {
    const col = useColumnStore()
    let regex: RegExp
    try { regex = new RegExp(queryText, 'i') }
    catch (e) { console.error('Invalid regex pattern:', e); return slots }

    return slots.filter(s => {
        for (const p of textProps) {
            const val: string = col.readSlot(p.id, s)
            if (val && regex.test(val)) return true
        }
        for (const p of tagProps) {
            const value: number[] = col.readSlot(p.id, s)
            if (!value) continue
            for (const tId of value) {
                if (tags[tId] && regex.test(tags[tId].value)) return true
            }
        }
        return false
    })
}

async function filterByPlugin(slots: number[], fnc: string, ctx: ActionContext): Promise<number[]> {
    const col = useColumnStore()
    const sha1PropId = col.systemProps.SHA1
    // Plugin API requires instance IDs
    ctx.instanceIds = slots.map(s => col.instanceIds[s])
    const result = await apiCallActions({ function: fnc, context: ctx } as ExecuteActionPayload)
    if (!result?.groups?.length) return slots
    const filteredSet = new Set(result.groups[0].sha1s)
    return slots.filter(s => {
        if (sha1PropId === null) return false
        const sha1 = col.readSlot(sha1PropId, s)
        return sha1 != null && filteredSet.has(sha1)
    })
}
