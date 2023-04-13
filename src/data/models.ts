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
    tabs: Array<Object>
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
    params: Params
    images: Images
    imageList: {url: String, imageName: String}[]
    fetchAllData: () => void
    [otherOptions: string]: any
}

export enum FilterOperator {
    equal = "equal",
    like = "like",
    lower = "lower",
    leq = "leq",
    greater = "greater",
    geq = "geq"
}

export interface Filter {
    propertyId: number,
    operator: FilterOperator,
    value: any,
    strict: boolean // strict to true will be an "OR" filter, set to false it would be an "AND"
}

export enum Modals {
    IMAGE = 'image',
    PROPERTY = 'property'
}
