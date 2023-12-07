import { Image, ImageStack, PropertyType, PropertyValue } from "@/data/models";
import { useStore } from "@/data/store2";
import { reactive } from "vue";
import { SortOption, SortOrder, SortType } from "./Sort";
// import { UNDEFINED_KEY } from "@/utils/groups";


const store = useStore()

const UNDEFINED_KEY = '__undefined__'
const ROOT_ID = 'root'

export enum GroupType {
    All = 'all',
    Selection = 'selection',
    Property = 'property',
    Cluster = 'cluster',
    Sha1 = 'sha1'
}

export interface Group {
    id: String
    images: Image[]
    type: GroupType
    subGroupType?: GroupType

    parent?: Group
    children: Group[]
    depth: number

    // Used by Groups with type Property
    propertyValues?: PropertyValue[]
    // Use by Groups with type Cluster
    score?: Number
}

export interface GroupIndex {[key: string]: Group}

export interface GroupResult {
    root: Group
    index: GroupIndex
    order: Array<string>,
    imageToGroups: {[imgId: number]: string[]}
}

export interface GroupOption extends SortOption {
    type: SortType
}

function isLeaf(group: Group) {
    return group.children.length == 0
}

function buildGroup(id: String, images: Image[], type: GroupType = GroupType.All): Group {
    return {
        id,
        images,
        type,
        children: [],
        depth: 0
    }
}

function valueToKey(propertyValue: PropertyValue) {
    const property = store.propertyIndex[propertyValue.propertyId]
    if (Array.isArray(propertyValue)) {
        throw new Error('ValueToKey doesnt work for Array values: ' + propertyValue)
    }
    if (property.type == PropertyType.checkbox) {
        return propertyValue.value ?? false
    }
    if (propertyValue.value == undefined) {
        return UNDEFINED_KEY
    }
}

function genPropertyGroupId(propertyValues: PropertyValue[]) {
    let res = 'prop-group:'
    propertyValues.forEach(v => res += String(v.propertyId) + '-' + valueToKey(v))
    return res
}

function buildRoot(images: Image[]): Group {
    return buildGroup(ROOT_ID, images)
}

function buildPropertyGroup(images: Image[], propertyValues: PropertyValue[],): Group {
    return buildGroup(genPropertyGroupId(propertyValues), images, GroupType.Property)
}

export function buildGroupOption(): GroupOption {
    return { type: SortType.Value, order: SortOrder.Ascending }
}


interface GroupManagerState {
    root: Group
    groupBy: GroupOption[]
}

class GroupManager {
    state: GroupManagerState
    result: GroupResult

    constructor(state?: GroupManagerState) {
        if(state) {
            this.state = state
        } else {
            this.state = reactive({
                root: buildRoot([]),
                groupBy: []
            })
        }
        // this.result = reactive(this.state.root)
    }

    addGroupOption(option: GroupOption) {

    }

    delGroupOption(propertyId: number) {

    }

    computeResult() {

    }

    addCustomGroups(targetGroupId: string, groups: Group[]) {

    }
}