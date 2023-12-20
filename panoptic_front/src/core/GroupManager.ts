/**
 * The GroupManager is used to get from an image array to a Group tree structure
 * The images can be grouped by properties. 
 * Custom groups can be appended to the tree.
 * GroupIterator and ImageIterator can be used to iterate over the tree
 */

import { Image, Property, PropertyValue, isTag } from "@/data/models";
import { nextTick, reactive } from "vue";
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
    options: { [groupId: string]: GroupOption },
    sha1Mode: boolean
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

export type SelectedImages = { [imageId: number]: boolean }


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
        options: {},
        sha1Mode: false
    }
}

export class GroupManager {
    state: GroupState
    result: GroupResult

    lastOrder: ImageOrder
    customGroups: { [parentGroupId: string]: Group[] }
    onChange: EventEmitter

    selectedImages: SelectedImages
    private selection: { lastImage: ImageIterator, lastGroup: GroupIterator }

    constructor(state?: GroupState, selectedImages?: SelectedImages) {
        if (state) {
            this.state = state
        } else {
            this.state = reactive(createGroupState())
        }
        this.result = { root: undefined, index: {}, imageToGroups: {} }
        this.customGroups = {}
        this.onChange = new EventEmitter()

        this.selectedImages = selectedImages ?? {}
        this.selection = { lastImage: undefined, lastGroup: undefined }
    }

    group(images: Image[], order: ImageOrder, emit?: boolean) {
        console.time('Group')
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

        for (let group of Object.values(this.result.index)) {
            if (group.children.length > 0 && group.subGroupType != GroupType.Sha1) continue
            this.saveImagesToGroup(group)
        }

        if (this.state.sha1Mode) {
            this.groupLeafsBySha1()
        }


        setOrder(this.result.root)

        console.timeEnd('Group')
        if (emit) this.onChange.emit(this.result)
        return this.result
    }

    sortGroups(emit?: boolean) {
        for (let group of Object.values(this.result.index) as Group[]) {
            if (group.subGroupType != GroupType.Property) continue
            if (group.children.length == 0) continue
            console.log(group)
            sortGroup(group, this.state.options[group.children[0].meta.propertyValues[0].propertyId])
        }
        if (emit) this.onChange.emit()
    }

    private saveImagesToGroup(group: Group) {
        for (let img of group.images) {
            if (!this.result.imageToGroups[img.id]) {
                this.result.imageToGroups[img.id] = []
            }
            this.result.imageToGroups[img.id].push(group.id)
        }
    }

    private groupLeafsBySha1() {
        this.removeSha1Groups()
        for (let group of Object.values(this.result.index) as Group[]) {
            if (group.children.length > 0) continue
            if (group.type == GroupType.Cluster) continue
            this.groupBySha1(group)
        }
    }

    removeSha1Groups() {
        for (let group of Object.values(this.result.index) as Group[]) {
            if (group.subGroupType != GroupType.Sha1) continue
            if (group.type == GroupType.Cluster) continue
            this.removeChildren(group)
        }
    }

    hasResult() {
        return this.result.root != undefined
    }

    clear() {
        this.result.imageToGroups = {}
        this.result.index = {}
        this.result.root = undefined
        this.clearLastSelected()
        this.clearSelection()
    }

    private removeChildren(group: Group) {
        this.removeImageToGroups(group)
        group.children.forEach(c => {
            delete this.result.index[c.id]
        })
        group.children.length = 0
        group.subGroupType = undefined
    }

    private groupBySha1(group: Group) {
        if (group.children) group.children.length = 0
        let order = []
        let groups: { [sha1: string]: Group } = {}

        for (let img of group.images) {
            if (!groups[img.sha1]) {
                groups[img.sha1] = buildGroup('sha1:' + img.sha1 + ':' + group.id, [img], GroupType.Sha1)
                groups[img.sha1].meta.propertyValues.push({ propertyId: -1, value: img.sha1 })
                order.push(img.sha1)

            } else {
                groups[img.sha1].images.push(img)
            }
        }

        const children = order.map(sha1 => groups[sha1])
        children.forEach(c => this.regsiterGroup(c))
        this.setChildGroup(group, children)
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

        if (emit) this.onChange.emit(this.result)
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
        this.setChildGroup(parent, groups)

        if (parent.subGroupType == GroupType.Cluster) {
            groups.forEach(g => {
                this.groupBySha1(g)
            })
        }
        setOrder(this.result.root)
        if (emit) this.onChange.emit(this.result)
    }

    delCustomGroups(targetGroupId: string, emit?: boolean) {
        delete this.customGroups[targetGroupId]
        this.removeChildren(this.result.index[targetGroupId])

        if (emit) this.onChange.emit(this.result)
    }

    setSha1Mode(value: boolean, emit?: boolean) {
        if (this.state.sha1Mode == value) return

        this.state.sha1Mode = value
        if (value) {
            this.groupLeafsBySha1()
        }
        else {
            console.log('remove')
            this.removeSha1Groups()
        }

        if (emit) this.onChange.emit()
    }

    toggleGroup(groupId, emit?: boolean) {
        this.result.index[groupId].view.closed = this.result.index[groupId].view.closed ? false : true

        if (emit) this.onChange.emit()
    }

    openGroup(groupId, emit?: boolean) {
        this.result.index[groupId].view.closed = false

        if (emit) this.onChange.emit()
    }

    closeGroup(groupId, emit?: boolean) {
        this.result.index[groupId].view.closed = true

        if (emit) this.onChange.emit()
    }

    getGroupIterator(groupId?: string, options?: GroupIteratorOptions) {
        return new GroupIterator(this, groupId, options)
    }

    getImageIterator(groupId?: string, imageIdx?: number, options?: GroupIteratorOptions) {
        return new ImageIterator(this, groupId, imageIdx, options)
    }

    findImageIterator(groupId: string, imageId: number) {
        const group = this.result.index[groupId]
        const image = globalStore.images[imageId]
        let idx = 0
        if (group.subGroupType == GroupType.Sha1) {
            idx = group.children.findIndex(g => g.images[0].sha1 == image.sha1)
        } else {
            idx = group.images.findIndex(i => i.id == imageId)
        }
        return this.getImageIterator(groupId, idx)
    }

    private setChildGroup(parent: Group, groups: Group[]) {
        this.removeChildren(parent)
        for (let group of groups) {
            group.parentIdx = parent.children.length
            group.parent = parent
            group.depth = parent.depth + 1
            parent.children.push(group)
            this.regsiterGroup(group)
            if (group.type != GroupType.Sha1) {
                this.saveImagesToGroup(group)
            }
        }
        parent.subGroupType = parent.children.length ? groups[0].type : undefined
        this.removeImageToGroups(parent)
        if (parent.subGroupType == GroupType.Sha1) {
            this.saveImagesToGroup(parent)
        }
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
        const children: Group[] = Object.values(subGroups)
        this.setChildGroup(group, children)

        if (groupBy.length > 1) {
            for (let c of children) {
                this.computePropertySubGroup(c, groupBy.slice(1))
            }
        }


        sortGroup(group, option)
    }

    private removeImageToGroups(group: Group) {
        group.images.forEach(img => {
            if (this.result.imageToGroups[img.id] == undefined) return

            const idx = this.result.imageToGroups[img.id].indexOf(group.id)
            if (idx < 0) return
            this.result.imageToGroups[img.id].splice(idx, 1)
        })
    }

    // Selection
    clearSelection() {
        if (this.result.root) this.unselectGroup(this.result.root)

        for (let k of Object.keys(this.selectedImages)) {
            delete this.selectedImages[k]
        }

        this.clearLastSelected()
    }

    selectImageIterator(iterator: ImageIterator, shift = false) {
        console.time('1')
        if (shift) {
            let res = this._shiftSelect(iterator)
        }
        this.selectImages(iterator.getImages().map(i => i.id))
        this.clearLastSelected()
        this.selection.lastImage = iterator.clone()
        nextTick(() => console.timeEnd('1'))
    }

    unselectImageIterator(iterator: ImageIterator) {
        this.unselectImages(iterator.getImages().map(i => i.id))
        this.clearLastSelected()
    }

    toggleImageIterator(iterator: ImageIterator, shift = false) {
        const selected = iterator.getImages().every(i => this.selectedImages[i.id])
        if (selected) {
            this.unselectImageIterator(iterator)
        } else {
            this.selectImageIterator(iterator, shift)
        }
    }
    toggleAll() {
        const iterator = this.getGroupIterator()
        this.toggleGroupIterator(iterator)
    }

    private _shiftSelect(iterator: ImageIterator) {
        if (this.selection.lastImage == undefined) return false

        let start = this.selection.lastImage.isImageBefore(iterator) ? this.selection.lastImage : iterator
        let end = start == iterator ? this.selection.lastImage : iterator

        // console.log(start, end)

        let images = []
        let it = start.clone()
        while (it) {
            // console.log(it)
            if (end.isImageBefore(it)) {
                break
            }
            images.push(...it.getImages().map(i => i.id))
            it = it.nextImages()
        }
        if (images.length) {
            this.selectImages(images)
            return true
        }
        return false
    }

    private _shiftGroup(iterator: GroupIterator) {
        if (this.selection.lastGroup == undefined) return false

        let start = this.selection.lastGroup.isGroupBefore(iterator) ? this.selection.lastGroup : iterator
        let end = start == iterator ? this.selection.lastGroup : iterator
        let images = []
        let it = start.clone()

        while (it) {
            if (end.isGroupBefore(it)) {
                break
            }
            const group = it.getGroup()
            if (group.images.length) {
                images.push(...group.images.map(i => i.id))
            }
            it = it.nextGroup()
        }
        if (images.length) {
            this.selectImages(images)
            return true
        }
        return false

    }

    clearLastSelected() {
        this.selection.lastGroup = undefined
        this.selection.lastImage = undefined
    }

    unselectImage(imageId: number) {
        this.unselectImages([imageId])
    }

    selectImage(imageId: number) {
        this.selectImages([imageId])
    }

    selectImages(imageIds: number[]) {
        imageIds.forEach(id => this.selectedImages[id] = true)

        let groups = new Set<string>()
        imageIds.forEach(id => this.result.imageToGroups[id].forEach(gId => groups.add(gId)))

        groups.forEach(gId => this.propagateSelect(this.result.index[gId]))
    }

    unselectImages(imageIds: number[]) {
        imageIds.forEach(id => delete this.selectedImages[id])
        let groups = new Set<string>()
        imageIds.forEach(id => this.result.imageToGroups[id].forEach(gId => groups.add(gId)))

        groups.forEach(gId => this.propagateUnselect(this.result.index[gId]))
    }

    propagateUnselect(group: Group) {
        group.view.selected = false
        if (!group.parent) return

        this.propagateUnselect(group.parent)
    }

    propagateSelect(group: Group) {
        if (group.children.length == 0 || group.subGroupType == GroupType.Sha1) {
            group.view.selected = group.images.every(i => this.selectedImages[i.id])
        }
        else {
            group.view.selected = group.children.every(g => g.view.selected)
        }

        if (!group.parent) return
        this.propagateSelect(group.parent)
    }

    selectGroup(group: Group) {
        this.selectImages(group.images.map(i => i.id))
        const recursive = (g: Group) => {
            g.view.selected = true
            g.children.forEach(c => recursive(c))
        }
        recursive(group)
    }

    unselectGroup(group: Group) {
        this.unselectImages(group.images.map(i => i.id))

        const recursive = (g: Group) => {
            g.view.selected = false
            g.children.forEach(c => recursive(c))
        }
        recursive(group)
    }

    selectGroupIterator(iterator: GroupIterator, shift = false) {
        if (shift) {
            this._shiftGroup(iterator)
        }
        this.selectGroup(iterator.getGroup())
        this.clearLastSelected()
        this.selection.lastGroup = iterator.clone()
    }

    unselectGroupIterator(iterator: GroupIterator) {
        this.unselectGroup(iterator.getGroup())
        this.clearLastSelected()
    }

    toggleGroupIterator(iterator: GroupIterator, shift = false) {
        const selected = iterator.getGroup().view.selected
        if (selected) {
            this.unselectGroupIterator(iterator)
        } else {
            this.selectGroupIterator(iterator, shift)
        }
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
        if (!current.view.closed && current.children.length > 0 && current.subGroupType != GroupType.Sha1) {
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

        if (this.getGroup().children.length > 0 && this.getGroup().subGroupType != GroupType.Sha1) {
            const next = this.nextGroup()
            this.groupId = next.groupId
        }
    }

    getImages(): Image[] {
        const group = this.getGroup()
        if (group.subGroupType == GroupType.Sha1) {
            return group.children[this.imageIdx].images
        }
        return [group.images[this.imageIdx]]
    }

    nextGroup(): ImageIterator {
        let next = super.nextGroup()
        while (next) {
            const group = next.getGroup()
            if (!group.view.closed && (group.subGroupType == GroupType.Sha1 || group.children.length == 0)) {
                return new ImageIterator(this.manager, next.groupId, 0, this.options)
            }
            next = next.nextGroup()
        }
        return undefined
    }

    nextImages(): ImageIterator {
        let current = this.clone()
        let nextIdx = current.imageIdx + 1
        while (current) {
            const group = current.getGroup()
            if (group.subGroupType == GroupType.Sha1) {
                if (group.children[nextIdx]) {
                    return new ImageIterator(this.manager, current.groupId, nextIdx, this.options)
                }
            } else {
                if (group.images[nextIdx]) {
                    return new ImageIterator(this.manager, current.groupId, nextIdx, this.options)
                }
            }

            current = current.nextGroup()
            nextIdx = 0
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