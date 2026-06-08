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

// ── Bitmask filter core ────────────────────────────────────────────────────
// All filter functions operate on a Uint8Array mask parallel to the slots array.
// mask[i] = 1 means slots[i] is still a candidate; 0 means already rejected.
// Functions only clear bits — they never set a 0 back to 1 (except OR groups
// which reset the mask for their own sub-evaluation and then write it back).

type TagCache = Map<number, Set<number>[]>

// Applies a single leaf filter in-place (AND semantics: clears failing bits).
// Dates are converted to epoch numbers for fast numeric comparison.
// Strings are lowercased once per call (filter value) and per slot (slot value).
// Tag sets are read from tagCache — built once per filter() call to avoid
// reconstructing Set<allChildren> on every invocation.
function applyLeafFilterMaskAnd(
    filter: Filter, slots: Int32Array, mask: Uint8Array,
    properties: PropertyIndex, tags: TagIndex, tagCache: TagCache
): void {
    const col = useColumnStore()
    const property = properties[filter.propertyId]
    const operatorFunc = operatorMap[filter.operator]
    const n = slots.length
    const propId = property.id

    // Fast path for numeric columns (number, date, _width, _height, _id, color):
    // work directly on the Float64Array to avoid readSlot + operatorFunc overhead.
    // Dates are stored as epoch-ms in the Float64Array, so slot comparisons are plain
    // number compares — only the filter value needs Date parsing (once, below). This
    // removes the per-slot `new Date(raw)` allocation the old date path incurred.
    if (property.type !== PropertyType.string) {
        const buf = col.getRawBuffer(propId)
        if (buf instanceof Float64Array) {
            const op = filter.operator
            if (op === FilterOperator.isSet)  { for (let i = 0; i < n; i++) { if (mask[i] && isNaN(buf[slots[i]])) mask[i] = 0 }; return }
            if (op === FilterOperator.notSet) { for (let i = 0; i < n; i++) { if (mask[i] && !isNaN(buf[slots[i]])) mask[i] = 0 }; return }
            // For value operators, undefined filter value means "pass everything"
            if (filter.value == null) return
            const b = property.type === PropertyType.date ? +new Date(filter.value as any) : Number(filter.value)
            if (isNaN(b)) return
            if (op === FilterOperator.lower)   { for (let i = 0; i < n; i++) { if (mask[i] && (isNaN(buf[slots[i]]) || buf[slots[i]] >= b)) mask[i] = 0 }; return }
            if (op === FilterOperator.leq)     { for (let i = 0; i < n; i++) { if (mask[i] && (isNaN(buf[slots[i]]) || buf[slots[i]] >  b)) mask[i] = 0 }; return }
            if (op === FilterOperator.greater) { for (let i = 0; i < n; i++) { if (mask[i] && (isNaN(buf[slots[i]]) || buf[slots[i]] <= b)) mask[i] = 0 }; return }
            if (op === FilterOperator.geq)     { for (let i = 0; i < n; i++) { if (mask[i] && (isNaN(buf[slots[i]]) || buf[slots[i]] <  b)) mask[i] = 0 }; return }
            if (op === FilterOperator.equal)   { for (let i = 0; i < n; i++) { if (mask[i] && buf[slots[i]] !== b) mask[i] = 0 }; return }
            if (op === FilterOperator.equalNot){ for (let i = 0; i < n; i++) { if (mask[i] && buf[slots[i]] === b) mask[i] = 0 }; return }
        }
    }

    if (property.type === PropertyType.string) {
        const fvLower = filter.value ? (filter.value as string).toLowerCase() : filter.value
        for (let i = 0; i < n; i++) {
            if (!mask[i]) continue
            const raw: string = col.readSlot(propId, slots[i])
            if (!operatorFunc(raw ? raw.toLowerCase() : raw, fvLower)) mask[i] = 0
        }
        return
    }

    const filterValue = isTag(property.type) && filter.value
        ? (tagCache.get(filter.id) ?? filter.value)
        : filter.value

    for (let i = 0; i < n; i++) {
        if (!mask[i]) continue
        if (!operatorFunc(col.readSlot(propId, slots[i]), filterValue)) mask[i] = 0
    }
}

// Applies a filter group in-place.
// AND group: each child filter narrows the mask — no intermediate arrays.
// OR group: collects passes across children using a todoMask to skip already-passed slots.
function applyGroupFilterMask(
    group: FilterGroup, slots: Int32Array, mask: Uint8Array,
    properties: PropertyIndex, tags: TagIndex, tagCache: TagCache
): void {
    if (!group.filters.length) return

    if (group.groupOperator === FilterOperator.and) {
        for (const f of group.filters) {
            if (f.isGroup)
                applyGroupFilterMask(f as FilterGroup, slots, mask, properties, tags, tagCache)
            else
                applyLeafFilterMaskAnd(f as Filter, slots, mask, properties, tags, tagCache)
        }
        return
    }

    // OR group: a slot passes if it passes at least one child.
    // todoMask tracks which active slots haven't matched any child yet.
    // mask is reset to 0 and rebuilt as children match.
    const n = slots.length
    const todoMask = new Uint8Array(mask)  // copy of parent-active slots
    mask.fill(0)                            // nothing passes yet

    for (const f of group.filters) {
        let hasTodo = false
        for (let i = 0; i < n; i++) if (todoMask[i]) { hasTodo = true; break }
        if (!hasTodo) break

        const workMask = new Uint8Array(todoMask)
        if (f.isGroup)
            applyGroupFilterMask(f as FilterGroup, slots, workMask, properties, tags, tagCache)
        else
            applyLeafFilterMaskAnd(f as Filter, slots, workMask, properties, tags, tagCache)

        for (let i = 0; i < n; i++) {
            if (workMask[i]) { mask[i] = 1; todoMask[i] = 0 }
        }
    }
}

function extractFromMask(slots: Int32Array, mask: Uint8Array): { valid: Int32Array; reject: Int32Array } {
    let validCount = 0
    for (let i = 0; i < mask.length; i++) if (mask[i]) validCount++
    const valid = new Int32Array(validCount)
    const reject = new Int32Array(slots.length - validCount)
    let vi = 0, ri = 0
    for (let i = 0; i < slots.length; i++) {
        if (mask[i]) valid[vi++] = slots[i]
        else         reject[ri++] = slots[i]
    }
    return { valid, reject }
}

// ── Text / regex / plugin query (mask-based) ───────────────────────────────

function filterByTextMask(
    slots: Int32Array, mask: Uint8Array, queryText: string,
    textProps: any[], tagProps: any[], tags: TagIndex
): void {
    const col = useColumnStore()
    const query = queryText.toLocaleLowerCase()
    const n = slots.length
    for (let i = 0; i < n; i++) {
        if (!mask[i]) continue
        let found = false
        for (const p of textProps) {
            const val: string = col.readSlot(p.id, slots[i])
            if (val && val.toLocaleLowerCase().includes(query)) { found = true; break }
        }
        if (!found) {
            outer: for (const p of tagProps) {
                const value: number[] = col.readSlot(p.id, slots[i])
                if (!value) continue
                for (const tId of value) {
                    if (tags[tId]?.value.toLocaleLowerCase().includes(query)) { found = true; break outer }
                }
            }
        }
        if (!found) mask[i] = 0
    }
}

function filterByRegexMask(
    slots: Int32Array, mask: Uint8Array, queryText: string,
    textProps: any[], tagProps: any[], tags: TagIndex
): void {
    const col = useColumnStore()
    let regex: RegExp
    try { regex = new RegExp(queryText, 'i') }
    catch (e) { console.error('Invalid regex pattern:', e); return }
    const n = slots.length
    for (let i = 0; i < n; i++) {
        if (!mask[i]) continue
        let found = false
        for (const p of textProps) {
            const val: string = col.readSlot(p.id, slots[i])
            if (val && regex.test(val)) { found = true; break }
        }
        if (!found) {
            outer: for (const p of tagProps) {
                const value: number[] = col.readSlot(p.id, slots[i])
                if (!value) continue
                for (const tId of value) {
                    if (tags[tId] && regex.test(tags[tId].value)) { found = true; break outer }
                }
            }
        }
        if (!found) mask[i] = 0
    }
}

async function filterByPluginMask(
    slots: Int32Array, mask: Uint8Array, fnc: string, ctx: ActionContext
): Promise<void> {
    const col = useColumnStore()
    const sha1PropId = col.systemProps.SHA1
    const ids = col.instanceIds()
    const activeInstanceIds: number[] = []
    for (let i = 0; i < slots.length; i++) {
        if (mask[i]) activeInstanceIds.push(ids[slots[i]])
    }
    // Build the payload from a clone: `ctx` is `state.query.ctx`, which is
    // reactive. Mutating it here would retrigger CollectionManager's deep watch
    // on filterManager.state and loop the recompute endlessly.
    const payloadCtx = { ...ctx, instanceIds: activeInstanceIds }
    const result = await apiCallActions({ function: fnc, context: payloadCtx } as ExecuteActionPayload)
    if (!result?.groups?.length) return
    const filteredSet = new Set(result.groups[0].sha1s)
    for (let i = 0; i < slots.length; i++) {
        if (!mask[i]) continue
        if (sha1PropId === null) { mask[i] = 0; continue }
        const sha1 = col.readSlot(sha1PropId, slots[i])
        if (sha1 == null || !filteredSet.has(sha1)) mask[i] = 0
    }
}

async function filterQueryMask(
    slots: Int32Array, mask: Uint8Array, query: TextQuery,
    properties: PropertyIndex, tags: TagIndex
): Promise<void> {
    if (!query?.text) return
    const actions = useActionStore()
    const props = objValues(properties)
    const textProps = props.filter(p => fullTextTypes.has(p.type))
    const tagProps  = props.filter(p => isTag(p.type))

    if (query.type === 'text')  { filterByTextMask(slots, mask, query.text, textProps, tagProps, tags); return }
    if (query.type === 'regex') { filterByRegexMask(slots, mask, query.text, textProps, tagProps, tags); return }
    if (query.ctx && actions.index[query.type]) { await filterByPluginMask(slots, mask, query.type, query.ctx); return }
}

// ── FilterManager ──────────────────────────────────────────────────────────

export class FilterManager {
    ctx: FilterContext
    state: FilterState
    result: FilterResult

    lastFilterId: number
    filterIndex: { [filterId: number]: AFilter }

    lastSlots: Int32Array
    onResultChange: EventEmitter
    onStateChange: EventEmitter

    // Cached to avoid scanning all properties on every filterSlots() call.
    // undefined = not yet computed; null = no folder property exists.
    private _folderPropId: number | null | undefined = undefined

    constructor(ctx: FilterContext, state?: FilterState) {
        this.ctx = ctx
        this.lastFilterId = null
        this.filterIndex = {}
        this.result = { slots: new Int32Array(0) }
        this.onResultChange = new EventEmitter()
        this.onStateChange = new EventEmitter()

        if (state) {
            this.state = state
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
            const folderPropId = this.getFolderPropId()
            if (folderPropId !== null) ids.add(folderPropId)
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
        const res = await this.filterSlots(slots)
        this.result.slots = res.valid
        console.timeEnd('Filter')
        if (emit) this.onResultChange.emit(this.result)
        return this.result
    }

    // Re-runs the filter on the last full slot set (recorded by filter()) and
    // emits so the collection re-sorts/re-groups. Call sites pass emit=true.
    async update(emit?: boolean) {
        if (!this.lastSlots) return this.result
        return this.filter(this.lastSlots, emit)
    }

    // Incremental update: re-filters only the dirty subset, splices into result.
    async updateSelection(instanceIds: Set<number>) {

        const col = useColumnStore()

        const dirtySlots = new Set<number>()
        for (const id of instanceIds) {
            const slot = col.slotMap.get(id)
            if (slot !== undefined) dirtySlots.add(slot)
        }

        // Pre-count kept slots to pre-allocate the result array.
        let keepCount = 0
        for (let i = 0; i < this.result.slots.length; i++) {
            if (!dirtySlots.has(this.result.slots[i])) keepCount++
        }

        const dirtySlotsArr = Int32Array.from(dirtySlots)
        const updated = await this.filterSlots(dirtySlotsArr)

        const newResult = new Int32Array(keepCount + updated.valid.length)
        let j = 0
        for (let i = 0; i < this.result.slots.length; i++) {
            if (!dirtySlots.has(this.result.slots[i])) newResult[j++] = this.result.slots[i]
        }
        for (let i = 0; i < updated.valid.length; i++) newResult[j++] = updated.valid[i]
        this.result.slots = newResult



        const ids = col.instanceIds()
        return {
            updated: new Set(Array.from(updated.valid,   s => ids[s])),
            removed: new Set(Array.from(updated.reject,  s => ids[s])),
        }
    }

    private async filterSlots(slots: Int32Array): Promise<{ valid: Int32Array; reject: Int32Array }> {
        await this._ensureColumns()
        const col = useColumnStore()

        const n = slots.length
        const mask = new Uint8Array(n)
        mask.fill(1)

        if (this.state.query?.text) {
            await filterQueryMask(slots, mask, this.state.query, this.ctx.properties, this.ctx.tags)
        }

        if (this.state.folders.length > 0) {
            const folderSet = new Set(this.state.folders)
            const folderPropId = this.getFolderPropId()
            if (folderPropId !== null) {
                for (let i = 0; i < n; i++) {
                    if (mask[i] && !folderSet.has(col.readSlot(folderPropId, slots[i]))) mask[i] = 0
                }
            }
        }

        const tagCache = this.buildTagCache()
        applyGroupFilterMask(this.state.filter, slots, mask, this.ctx.properties, this.ctx.tags, tagCache)

        return extractFromMask(slots, mask)
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
        if ('value' in update) {
            filter.value = update.value ?? propertyDefault(type)
        }
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
        this._folderPropId = undefined  // invalidate after property set may have changed
    }

    // Call when ctx.properties changes (e.g. after a property is added/removed).
    public invalidatePropCache(): void {
        this._folderPropId = undefined
    }

    private getFolderPropId(): number | null {
        if (this._folderPropId === undefined) {
            const prop = objValues(this.ctx.properties).find(p => p.systemKey === 'folder')
            this._folderPropId = prop ? prop.id : null
        }
        return this._folderPropId
    }

    // Builds tag-value Sets once per filter() call so applyLeafFilterMaskAnd
    // doesn't reconstruct Set<allChildren> on every slot iteration.
    private buildTagCache(): TagCache {
        const cache: TagCache = new Map()
        const visit = (group: FilterGroup) => {
            for (const f of group.filters) {
                if (f.isGroup) { visit(f as FilterGroup); continue }
                const filter = f as Filter
                const prop = this.ctx.properties[filter.propertyId]
                if (isTag(prop?.type) && Array.isArray(filter.value) && filter.value.length) {
                    cache.set(filter.id, filter.value.map((v: number) =>
                        new Set([...this.ctx.tags[v].allChildren, v])
                    ))
                }
            }
        }
        visit(this.state.filter)
        return cache
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
