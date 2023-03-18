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
    value: string | number | number[] | string[]
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
    images: Images
    imageList: ComputedRef<{url: String, imageName: String}[]>
    fetchAllData: () => void
    [otherOptions: string]: unknown
}

export interface ReactiveStore{
    tags: Tags,
    tagTrees: TagsTree
    properties: Properties
    images: Images
    imageList: {url: String, imageName: String}[]
    fetchAllData: () => void
    [otherOptions: string]: unknown
}