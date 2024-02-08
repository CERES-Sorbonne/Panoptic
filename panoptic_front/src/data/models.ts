import { CollectionManager } from "@/core/CollectionManager"
import { FilterOperator, FilterState } from "@/core/FilterManager"
import { Group, GroupState, ImageIterator } from "@/core/GroupManager"
import { SortState } from "@/core/SortManager"

export interface Image {
    id: number
    name: string
    sha1: string
    ahash: string
    width: number
    height: number
    url: string
    fullUrl: string
    folder_id: number
    extension: string
    properties: {
        [id: number]: PropertyValue
    }
    dist?: number
    containerRatio?: number
}

export interface ImageIndex {
    [id: number]: Image
}

export type Sha1ToImages = { [sha1: string]: Image[] }
export type Sha1Scores = { [sha1: string]: number }

// ==================================
// ==============Property============
// ==================================

export interface Property {
    id: number
    name: string
    type: PropertyType
    mode: PropertyMode
    tags?: TagIndex
}

export type PropertyIndex = { [propertyId: number]: Property }

export enum PropertyType {
    multi_tags = "multi_tags",
    tag = "tag",
    string = "string",
    number = "number",
    date = "date",
    color = "color",
    url = "url",


    checkbox = "checkbox",
    path = "path",
    image_link = "image_link",
    _ahash = "average hash",
    _sha1 = "sha1",
    _folders = "folders",
    _id = "id",
    _width = "width",
    _height = "height"
}

export enum PropertyMode {
    sha1 = 'sha1',
    id = 'id',
    computed = 'computed'
}

export interface PropertyValue {
    propertyId: number
    value: any
    valueEnd?: any // allow to specidy an interval [value, valueEnd] in special cases like date grouping
    unit?: DateUnit
}

export interface PropertyRef extends PropertyValue {
    type: PropertyType
    imageId: number
    mode: PropertyMode
}

export interface PropertyValueUpdate extends PropertyValue {
    updated_ids: number[]
}

export enum PropertyID {
    id = -1,
    sha1 = -2,
    ahash = -3,
    folders = -4,
    width = - 5,
    height = - 6
}

//=============================
//===========Tag===============
//=============================

export interface Tag {
    id: number;
    property_id: number;
    parents: number[];
    value: string;
    color?: number;
    children?: number[]
    count?: number
}

export interface TagIndex {
    [tagId: number]: Tag
}

//=============================
//===========Folders===========
//=============================

export interface Folder {
    id: number
    name: string
    path: string
    parent: number
    children: Array<Folder>
    show?: boolean // frontend variable to know if exanded in view or not
    selected?: boolean // frontend variable for smart folder filter
    count?: number
}

export interface FolderIndex {
    [id: number]: Folder
}

//===================================
//==============Tab==================
//===================================

// export interface Tab {
//     id?: number
//     state: TabState

//     collection?: CollectionManager
// }

export interface TabState {
    version: number
    id: number
    name: string
    display: string

    filterState: FilterState
    sortState: SortState,
    groupState: GroupState,

    imageSize: number
    visibleProperties: { [key: number]: boolean }
    visibleFolders: { [key: number]: boolean }
    selectedFolders: { [key: number]: boolean }
    sha1Mode: boolean
    propertyOptions: { [key: number]: PropertyOption }
}

export interface TabIndex {
    [tabId: number]: TabState
}


// ===============================all=====================
export interface PropertyOption {
    size: number
}


export enum ModalId {
    IMAGE = 'image',
    IMAGE_ZOOM = 'image_zoom',
    PROPERTY = 'property',
    SHA1PILE = 'sha1pile',
    FOLDERTOPROP = 'folder_to_property',
    EXPORT = "export",
    FOLDERSELECTION = 'explorer',
    SETTINGS = "settings"
}

export interface ImportState {
    to_import: number
    imported: number
    computed: number
    new_images?: Image[],
    done: boolean
}

export interface StatusUpdate {
    tasks: TaskState[];
    // updated_images: Image[];
    pluginLoaded?: boolean
}

export interface DataUpdate {
    images?: Image[]
    properties?: Property[]
}

export interface TaskState {
    name: string;
    id: string;
    total: number;
    remain: number;
    computing: number;
    done: boolean;
}

export interface SyncResult {
    newImageCount: number
    missingImages: Image[]
}

export const Colors = [
    { name: 'red', color: '#ff8787' },
    { name: 'pink', color: '#f783ac' },
    { name: 'grape', color: '#da77f2' },
    { name: 'violet', color: '#9775fa' },
    { name: 'indigo', color: '#748ffc' },
    { name: 'blue', color: '#4dabf7' },
    { name: 'cyan', color: '#3bc9db' },
    { name: 'teal', color: '#38d9a9' },
    { name: 'green', color: '#69db7c' },
    { name: 'lime', color: '#a9e34b' },
    { name: 'yellow', color: '#ffd43b' },
    { name: 'orange', color: '#ffa94d' },
]

export interface ScrollerLine {
    id: string
    type: string
    groupId?: string
    data: any
    index?: number
    depth?: number
    size: number
}

export interface GroupLine extends ScrollerLine {
    data: Group
    nbClusters: number
}

export interface ImageLine extends ScrollerLine {
    data: ImageIterator[]
}

export interface RowLine extends ScrollerLine {
    data: Image,
    iterator: ImageIterator
}

export interface PileRowLine extends ScrollerLine {
    data: Group
    iterator: ImageIterator
}

export interface ScrollerPileLine extends ScrollerLine {
    data: ImageIterator[]
}

export interface Recommendation {
    images: string[]
    values: PropertyValue[]
    groupId: string
}

export interface DirInfo {
    path: string,
    name: string,
    images?: number
    images_url?: string,
    isProject: boolean
}

export enum DateUnit {
    Year = 'Year',
    Month = 'Month',
    Week = 'Week',
    Day = 'Day',
    Hour = 'Hour',
    Minute = 'Minute',
    Second = 'Second'
}

export const DateUnitFactor = {
    [DateUnit.Year]: 1,
    [DateUnit.Month]: 1,
    [DateUnit.Week]: 60 * 60 * 24 * 7,
    [DateUnit.Day]: 60 * 60 * 24,
    [DateUnit.Hour]: 60 * 60,
    [DateUnit.Minute]: 60,
    [DateUnit.Second]: 1,

}

export interface ActionContext {
    instanceIds?: number[]
    propertyIds?: number[]
    file?: string
    text?: string
    uiInputs?: { [key: string]: any }
}


// ================== Plugins ==================

export interface ParamDescription {
    name: string
    description: string
    type: string
}

export interface FunctionDescription {
    id: string
    name: string
    description: string | null
    action: string
    params: ParamDescription[]
}

export interface PluginBaseParamsDescription {
    description: string
    params: ParamDescription[]
}


export interface PluginDescription {
    name: string
    description: string
    path: string
    baseParams: PluginBaseParamsDescription
    registeredFunctions: FunctionDescription[]
    defaults: PluginDefaultParams
}

export interface PluginDefaultParams {
    name: string
    base: { [param: string]: any }
    functions: { [func: string]: { [param: string]: any } }
}

// ============= Actions ==============
export interface ActionDescription {
    name: string
    selectedFunction?: string
    availableFunctions?: string[]
}

export interface ActionParam {
    name: string
    value: string
}


// ========== Vectors ===============
export interface VectorDescription {
    source: string
    type: string
    count?: number
}

export interface ProjectVectorDescription {
    vectors: VectorDescription[]
    defaultVectors: VectorDescription
}