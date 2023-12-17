/**
 * The GroupManager is used to get from an image array to a Group tree structure
 * The images can be grouped by properties. 
 * Custom groups can be appended to the tree.
 * GroupIterator and ImageIterator can be used to iterate over the tree
 */

import { Image, Property, PropertyValue, isTag } from "@/data/models";
import { reactive } from "vue";
import { ImageOrder, SortDirection, SortOption, sortParser } from "./SortManager";
import { globalStore } from "@/data/store";
import { PropertyType } from "@/data/models2";
import { EventEmitter } from "@/utils/utils";

// const store = useStore()

export const UNDEFINED_KEY = '_$undef_key_'
export const ROOT_ID = 'root'

export enum GroupType {
    All = 'all',
    Selection = 'selection',
    Property = 'property',
    Cluster = 'cluster',
    Sha1 = 'sha1'
}

export interface GroupState {
    groupBy: number[],
    options: { [groupId: string]: GroupOption }
}

export interface Group {
    id: string
    images: Image[]
    type: GroupType
    subGroupType?: GroupType

    parent?: Group
    // Needed for O(1) next neighbor
    // parent.children[parentIdx] == this
    parentIdx?: number
    children: Group[]
    depth: number
    order: number

    view: GroupView
    meta: GroupMetaData
}

export interface GroupView {
    selected: boolean
    closed: boolean
}

export interface GroupMetaData {
    // Used by Groups with type Property
    propertyValues?: PropertyValue[]
    // Use by Groups with type Cluster
    score?: number
}

export interface GroupIndex { [key: string]: Group }

export interface GroupResult {
    root: Group
    index: GroupIndex
    imageToGroups: { [imgId: number]: string[] }
}

export enum GroupSortType {
    Size,
    Property
}

export interface GroupOption extends SortOption {
    type?: GroupSortType
}

// function isLeaf(group: Group) {
//     return group.children.length == 0
// }


export function buildGroup(id: string, images: Image[], type: GroupType = GroupType.All): Group {
    return {
        id,
        images,
        type,
        children: [],
        depth: 0,
        order: -1,
        meta: { propertyValues: [] },
        view: { closed: false, selected: false }
    }
}

function valueToKey(propertyValue: PropertyValue) {
    const property = globalStore.properties[propertyValue.propertyId]
    if (Array.isArray(propertyValue)) {
        throw new Error('ValueToKey doesnt work for Array values: ' + propertyValue)
    }
    if (property.type == PropertyType.checkbox) {
        return propertyValue.value ?? false
    }
    if (propertyValue.value == undefined) {
        return UNDEFINED_KEY
    }
    return String(propertyValue.value)
}

function propValuesToId(propertyValues: PropertyValue[]) {
    let res = ''
    propertyValues.forEach(v => res += ':' + String(v.propertyId) + '-' + valueToKey(v))
    return res
}

function buildRoot(images: Image[]): Group {
    return buildGroup(ROOT_ID, images)
}

export function buildGroupOption(): GroupOption {
    return { direction: SortDirection.Ascending, type: GroupSortType.Property }
}

const valueParser: { [type in PropertyType]?: any } = {
    [PropertyType.checkbox]: (x?: boolean) => {
        if (!x) return false
        return true
    },
    [PropertyType.color]: (x?: number) => {
        if (isNaN(x)) return undefined
        return x
    },
    [PropertyType.date]: (x?: Date) => {
        if (!x) return undefined
        return x
    },
    [PropertyType.number]: (x?: number) => {
        if (x == undefined) return undefined
        return x
    },
    [PropertyType.path]: (x?: string) => {
        if (!x) return undefined
        return x
    },
    [PropertyType.string]: (x?: string) => {
        if (!x) return undefined
        return x
    },
    [PropertyType.url]: (x?: string) => {
        if (!x) return undefined
        return x
    },
    [PropertyType._ahash]: (x: string) => {
        return x
    },
    [PropertyType._sha1]: (x: string) => {
        return x
    },
    [PropertyType._folders]: (x: number) => {
        return x
    },
    [PropertyType.tag]: (x: number[]) => {
        if (Array.isArray(x)) return x
        return undefined
    },
    [PropertyType.multi_tags]: (x: number[]) => {
        if (Array.isArray(x)) return x
        return undefined
    }
}



function sortGroup(group: Group, option: GroupOption) {
    if (group.children.length == 0) return
    if (option.type == GroupSortType.Property) {
        sortGroupByProperty(group, option.direction)
    } else {
        sortGroupBySize(group, option.direction)
    }
    for (let i = 0; i < group.children.length; i++) {
        group.children[i].parentIdx = i
    }
}

function sortGroupByProperty(group: Group, direction: number) {
    let sortable = {}

    for (let child of group.children) {
        const values = []
        for (let propValue of child.meta.propertyValues) {
            const prop = globalStore.properties[propValue.propertyId]
            const type = isTag(prop.type) ? PropertyType.tag : prop.type
            let value = propValue.value
            if (isTag(type) && value != undefined) {
                value = globalStore.tags[prop.id][value].value
            }
            value = sortParser[type](value)
            values.push(value)
        }
        sortable[child.id] = values
    }

    group.children.sort((ca, cb) => {
        let a = sortable[ca.id]
        let b = sortable[cb.id]
        for (let i = 0; i < a.length; i++) {
            if (a[i] == b[i]) continue
            if (a[i] < b[i]) return -1 * direction
            return 1 * direction
        }
        return 0
    })
}

function sortGroupBySize(group: Group, direction: number) {
    group.children.sort((a, b) => (a.images.length - b.images.length) * direction)
}

function sortGroupImages(group: Group, order: ImageOrder) {
    group.images.sort((a, b) => order[a.id] - order[b.id])
}

function setOrder(group: Group) {
    let i = 0
    const idx = () => i++
    const recursive = (group: Group) => {
        group.order = idx()
        group.children.forEach(c => recursive(c))
    }
    recursive(group)
}

export function createGroupState(): GroupState {
    return {
        groupBy: [],
        options: {}
    }
}

export class GroupManager {
    state: GroupState
    result: GroupResult

    lastOrder: ImageOrder

    customGroups: { [parentGroupId: string]: Group[] }

    onChange: EventEmitter

    constructor(state?: GroupState) {
        if (state) {
            this.state = state
        } else {
            this.state = reactive(createGroupState())
        }
        this.result = { root: undefined, index: {}, imageToGroups: {} }
        this.customGroups = {}
        this.onChange = new EventEmitter()
    }

    group(images: Image[], order: ImageOrder, emit?: boolean) {

        this.lastOrder = order
        this.result.root = buildRoot(images)
        this.result.index = {}
        this.result.imageToGroups = {}
        this.customGroups = {}
        this.regsiterGroup(this.result.root)

        if (this.state.groupBy.length > 0) {
            this.computePropertySubGroup(this.result.root, this.state.groupBy)
        }
        Object.values(this.result.index).map(v => v as Group).forEach(g => {
            sortGroupImages(g, order)
        })

        for (let parentId of Object.keys(this.customGroups)) {
            const groups = this.customGroups[parentId]
            groups.forEach(g => this.regsiterGroup(g))
        }

        setOrder(this.result.root)


        if (emit) this.onChange.emit(this.result)
        return this.result
    }

    update(emit?: boolean) {
        if (!this.result.root) return
        this.group(this.result.root.images, this.lastOrder, emit)
    }

    sort(order: ImageOrder, emit?: boolean) {
        this.lastOrder = order
        Object.values(this.result.index).map(v => v as Group).forEach(g => {
            sortGroupImages(g, order)
        })

        if(emit) this.onChange.emit(this.result)
    }

    setGroupOption(propertyId: number, option?: GroupOption) {
        if (!this.state.options[propertyId]) {
            this.state.options[propertyId] = buildGroupOption()
        }
        if (option) {
            Object.assign(this.state.options[propertyId], option)
        }

        if (this.state.groupBy.includes(propertyId)) return
        this.state.groupBy.push(propertyId)
    }

    delGroupOption(propertyId: number) {
        const index = this.state.groupBy.indexOf(propertyId)
        if (index < 0) return
        this.state.groupBy.splice(index, 1)
    }

    addCustomGroups(targetGroupId: string, groups: Group[], emit?: boolean) {
        const parent = this.result.index[targetGroupId]
        if (!parent) return

        this.customGroups[targetGroupId] = groups
        this.addChildGroup(parent, groups)

        if (emit) this.onChange.emit(this.result)
    }

    delCustomGroups(targetGroupId: string, emit?: boolean) {
        delete this.customGroups[targetGroupId]
        const parent = this.result.index[targetGroupId]
        if (!parent) return

        parent.subGroupType = undefined
        parent.children.forEach(c => {
            delete this.result.index[c.id]
        })
        parent.children.length = 0

        if (emit) this.onChange.emit(this.result)
    }

    toggleGroup(groupId) {
        this.result.index[groupId].view.closed = this.result.index[groupId].view.closed ? false : true
        this.onChange.emit()
    }

    openGroup(groupId) {
        this.result.index[groupId].view.closed = false
        this.onChange.emit()
    }

    closeGroup(groupId) {
        this.result.index[groupId].view.closed = true
        this.onChange.emit()
    }

    getGroupIterator() {
        return new GroupIterator(this)
    }

    getImageIterator() {
        return new ImageIterator(this)
    }

    private addChildGroup(parent: Group, groups: Group[]) {
        for (let group of groups) {
            group.parentIdx = parent.children.length
            group.parent = parent
            parent.children.push(group)
            this.regsiterGroup(group)
        }
        parent.subGroupType = groups[0].type
    }

    private regsiterGroup(group: Group) {
        this.result.index[group.id] = group
    }

    private computePropertySubGroup(group: Group, groupBy: number[]) {
        const property = globalStore.properties[groupBy[0]]
        const option = this.state.options[property.id]
        const subGroups: { [key: string]: Group } = {}

        group.subGroupType = GroupType.Property

        for (let img of group.images) {
            let value = img.properties[property.id]?.value
            value = valueParser[property.type](value)

            let values = Array.isArray(value) ? value : [value]

            for (let v of values) {
                const key = v == undefined ? UNDEFINED_KEY : String(v)
                if (!subGroups[key]) {
                    let propValues = [{ propertyId: property.id, value: v }]
                    let id = group.id == ROOT_ID ? 'prop' : group.id
                    id += propValuesToId(propValues)
                    const newGroup = buildGroup(id, [], GroupType.Property)
                    newGroup.meta.propertyValues = propValues
                    subGroups[key] = newGroup
                }
                subGroups[key].images.push(img)
            }
        }

        for (let key of Object.keys(subGroups)) {
            const subGroup = subGroups[key]
            this.regsiterGroup(subGroup)
            group.children.push(subGroup)
            subGroup.parent = group
            subGroup.depth = group.depth + 1

            if (groupBy.length > 1) {
                this.computePropertySubGroup(subGroup, groupBy.slice(1))
            }
        }

        sortGroup(group, option)
    }
}

export interface GroupIteratorOptions {
    ignoreClosed?: boolean
    onlyPropertyGroups?: boolean
}

export class GroupIterator {
    manager: GroupManager
    groupId: string
    options: GroupIteratorOptions

    constructor(manager: GroupManager, groupId?: string, options?: GroupIteratorOptions) {
        this.manager = manager
        this.groupId = groupId ?? ROOT_ID
        this.options = {}
        if (options) {
            this.options = options
        }
    }

    clone(): GroupIterator {
        return new GroupIterator(this.manager, this.groupId, this.options)
    }
    getGroup(): Group {
        return this.manager.result.index[this.groupId]
    }
    nextGroup(): GroupIterator {
        let current = this.getGroup()
        if (!current.view.closed && current.children.length > 0) {
            return new GroupIterator(this.manager, current.children[0].id)
        }

        let parent = current.parent
        while (parent != undefined) {
            const next = parent.children[current.parentIdx + 1]
            if (next) return new GroupIterator(this.manager, next.id)
            current = parent
            parent = current.parent
        }
        return undefined
    }
    isGroupBefore(it: GroupIterator): boolean {
        return this.getGroup().order < it.getGroup().order
    }
    isGroupEqual(it: GroupIterator): boolean {
        return this.getGroup().order == it.getGroup().order
    }
}

export class ImageIterator extends GroupIterator {
    imageIdx: number

    constructor(manager: GroupManager, groupId?: string, imageIdx?: number, options?: GroupIteratorOptions) {
        super(manager, groupId, options)
        this.imageIdx = imageIdx ?? 0

        if(this.getGroup().children.length > 0) {
            const next = this.nextGroup()
            this.groupId = next.groupId
        }
    }

    getImages(): Image[] {
        const group = this.getGroup()
        if (group.type == GroupType.Sha1) {
            return group.children[this.imageIdx].images
        }
        return [group.images[this.imageIdx]]
    }

    nextGroup(): ImageIterator {
        let next = super.nextGroup()
        while (next) {
            const group = next.getGroup()
            if (group.type == GroupType.Sha1 || group.children.length == 0) {
                return new ImageIterator(this.manager, next.groupId, 0, this.options)
            }
            next = next.nextGroup()
        }
        return undefined
    }

    nextImages(): ImageIterator {
        let current = this.clone()
        while (current) {
            const group = current.getGroup()
            const nextIdx = current.imageIdx + 1
            if(group.images[nextIdx]) {
                return new ImageIterator(this.manager, current.groupId, nextIdx, this.options)
            }
            current = current.nextGroup()
        }
    }

    isImageBefore(it: ImageIterator) {
        if (this.isGroupEqual(it)) {
            return this.imageIdx < it.imageIdx
        }
        return this.isGroupBefore(it)
    }

    isImageEqual(it: ImageIterator) {
        return this.isGroupEqual(it) && this.imageIdx == it.imageIdx
    }

    clone(): ImageIterator {
        return new ImageIterator(this.manager, this.groupId, this.imageIdx, this.options)
    }

}