import { TagIndex } from "./tag"
import { DateUnit } from "./ui"

export interface Property {
    id: number
    name: string
    type: PropertyType
    mode: PropertyMode
    systemKey?: string
    access?: PropertyAccess
    propertyGroupId?: number
    tags?: TagIndex
}

export type PropertyAccess = 'read' | 'write'

// Single edit gate: panoptic computes it (systemKey), or its owner — a plugin, an
// import — declared it non-editable. The backend refuses writes to these with a 403.
export function isReadonly(property: Property): boolean {
    return Boolean(property.systemKey) || property.access === 'read'
}

export interface PropertyDescription extends Property {
    col: number
}

export type PropertyIndex = { [propertyId: number]: Property }

export type PropertyGroupIndex = { [groupId: number]: PropertyGroup }

export enum PropertyType {
    multi_tags = "multi_tags",
    tag = "tag",
    string = "text",
    number = "number",
    date = "date",
    color = "color",
    url = "url",


    checkbox = "checkbox",
    path = "path",
    image_link = "image_link",
    _ahash = "ahash",
    _sha1 = "sha1",
    _folders = "folder",
    _id = "id",
    _width = "width",
    _height = "height"
}

export enum PropertyMode {
    sha1 = 'sha1',
    id = 'id',
    file = 'file'
}

export interface PropertyValue {
    propertyId: number
    value: any

    // ui only
    valueEnd?: any // allow to specidy an interval [value, valueEnd] in special cases like date grouping
    unit?: DateUnit
}

export interface InstancePropertyValue {
    propertyId: number
    instanceId: number
    value: any
}

export interface ImagePropertyValue {
    propertyId: number
    sha1: string
    value: any
}

export interface FilePropertyValue {
    propertyId: number
    fileId: number
    value: any
}

export interface ImageValuesArray {
    propertyId: number
    sha1s: string[]
    values: any[]
}

export interface FileValuesArray {
    propertyId: number
    fileIds: number[]
    values: any[]
}

export interface InstanceValuesArray {
    propertyId: number
    ids: number[]
    values: any[]
}

export interface PropertyRef extends PropertyValue {
    type: PropertyType
    imageId: number
    mode: PropertyMode
}

export interface PropertyValueUpdate extends PropertyValue {
    updatedIds: number[]
}

export enum PropertyID {
    id = -1,
    sha1 = -2,
    ahash = -3,
    folders = -4,
    width = - 5,
    height = - 6
}

export interface PropertyOption {
    size: number
}

export interface PropertyGroup {
    id: number,
    name: string
}

export interface PropertyGroupNode {
    groupId: number
    propertyIds: number[]
}

export interface PropertyGroupOrder {
    groups: { [groupId: number]: number }
    properties: { [propertyId: number]: number }
}

export enum PropertyGroupId {
    DEFAULT = -1,
    METADATA = -2
}
