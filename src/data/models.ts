import { ComputedRef } from "vue";

export enum PropertyType {
    string = "string",
    number = "number",
    tag = "tag",
    multi_tags = "multi_tags",
    image_link = "image_link",
    url = "url",
    date = "date",
    path = "path",
    color = "color",
    checkbox = "checkbox"
}

export interface Tag {
    id: number;
    property_id: number;
    parents: number[];
    value: string;
    color?: string;
}

export interface Property {
    id: number
    name: string
    type: PropertyType
}

export interface PropertyValue{
    propertyId: number
    // value: string | number | number[] | string[]
    value: any
}

export interface PropertyRef extends PropertyValue {
    type: PropertyType
    imageSHA1: String
}

export interface Image {
    sha1: string
    width: number
    height: number
    url: string
    paths: [string]
    extension: string
    properties: {
        [id:number]: PropertyValue
    }
}

export interface Images {
    [sha1:string]: Image
}

export interface Properties {
    [id:number]: Property
}

export interface Params {
    folders: Array<string>
    tabs: Array<TabState>
}

export interface Tags {
    [property_id: number]: {
        [id: number]: Tag
    }
}

export interface IndexedTags {
    [id: number]: Tag
}

// a tag inside a tagstree
export interface TreeTag{
    value: string
    id: number
    children: TreeTag[]
    localId: string
}

export interface TagsTree {
    [tagId: number]: TreeTag
}

export interface PropsTree {
    [propId:number]: TagsTree
}

export interface GlobalStore {
    tags: Tags,
    tagTrees: ComputedRef<TagsTree>
    properties: Properties
    propertyList: ComputedRef<Array<Property>>
    params: Params
    images: Images
    imageList: ComputedRef<{url: String, imageName: String}[]>
    fetchAllData: () => void
    [otherOptions: string]: any
}

export interface ReactiveStore{
    tags: Tags,
    tagTrees: TagsTree
    properties: Properties
    propertyList: Array<Property>
    params: Params
    images: Images
    imageList: {url: String, imageName: String}[]
    fetchAllData: () => void
    [otherOptions: string]: any
}

export enum FilterOperator {
    equal = "equal",
    equalNot = "not equal",
    like = "like",
    lower = "lower",
    leq = "lower or equal",
    greater = "greater",
    geq = "greater or equal",
    isTrue = "is true",
    isFalse = "is false",
    contains = "contains",
    startsWith = "starts with",
    containsAny = "contains any",
    containsAll = "contains all",
    containsNot = "does not contain",
    and = "and",
    or = "or",
    isSet = "is set",
    notSet = "is not set"
}

export interface Filter {
    propertyId: number,
    operator: FilterOperator,
    value: any,
    // strict: boolean // strict to true will be an "OR" filter, set to false it would be an "AND"
    isGroup?: false
}

export enum Modals {
    IMAGE = 'image',
    PROPERTY = 'property'
}

export interface PropertySetting {
    propertyId: number,
    maxLines: number
}

export interface FilterGroup {
    filters: Array<Filter | FilterGroup>
    groupOperator: FilterOperator.and | FilterOperator.or
    depth: number
    isGroup: true
}

export function availableOperators(propertyType: PropertyType): Array<FilterOperator> {
    switch(propertyType) {
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
        default:
            return []
    }
}

export function operatorHasInput(operator: FilterOperator) {
    switch(operator) {
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

export interface TabState {
    name: string
    display: string
    filter: FilterGroup
    groups: Object
}