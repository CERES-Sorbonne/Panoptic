import { FilterState } from "@/core/FilterManager"
import { Group, GroupState, ImageIterator } from "@/core/GroupManager"
import { SortState } from "@/core/SortManager"

export interface Instance {
    id: number
    name: string
    sha1: string
    ahash: string
    width: number
    height: number
    url: string
    // fullUrl: string
    folderId: number
    extension: string
    properties: {
        [id: number]: any
    }
    dist?: number
    containerRatio?: number

    urlSmall: string
    urlMedium: string
    urlLarge: string
    urlRaw: string
}

export interface InstanceIndex {
    [id: number]: Instance
}

export type Sha1ToInstances = { [sha1: string]: Instance[] }
export type Sha1Scores = { [sha1: string]: number }

// ==================================
// ==============Property============
// ==================================

export interface Property {
    id: number
    name: string
    type: PropertyType
    mode: PropertyMode
    computed?: boolean
    tags?: TagIndex
}

export interface PropertyDescription extends Property {
    col: number
}

export type PropertyIndex = { [propertyId: number]: Property }

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
    id = 'id'
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

//=============================
//===========Tag===============
//=============================

export interface Tag {
    id: number;
    propertyId: number;
    parents: number[];
    value: string;
    color?: number;
    children?: number[]
    count?: number
    deleted?: boolean

    allParents?: number[]
    allChildren?: number[]
}

export interface TagIndex {
    [tagId: number]: Tag
}

export interface DeleteTagResult {
    tagId: number
    updatedValues: any[]
    updatedTags: Tag[]
}

export function buildTag(id: number, propertyId: number, value: string, parents?: number[], color: number = -1) {
    return { id, propertyId, value, parents: parents ?? [], color: color }
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
    selected?: boolean

    filterState: FilterState
    sortState: SortState,
    groupState: GroupState,

    imageSize: number
    visibleProperties: { [key: number]: boolean }
    visibleFolders: { [key: number]: boolean }
    selectedFolders: { [key: number]: boolean }
    sha1Mode: boolean
    propertyOptions: { [key: number]: PropertyOption }
    similarityDist: number
    autoReload: boolean
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
    SETTINGS = "settings",
    IMPORT = "import",
    TAG = "tag",
    FIRSTMODAL = "firstmodal",
    NOTIF = "notif"
}

export interface ImportState {
    to_import: number
    imported: number
    computed: number
    new_images?: Instance[],
    done: boolean
}

export interface StatusUpdate {
    tasks: TaskState[];
    // updated_images: Image[];
    pluginLoaded?: boolean
    update: UpdateCounter
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
    missingImages: Instance[]
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
    id: string | number
    type: string
    groupId?: number
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
    data: Instance,
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
    groupId: number
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

export interface UpdateCounter {
    action: number;
    image: number;
}


// ================== Plugins ==================

export interface ParamDescription {
    id?: string
    name: string
    label?: string
    description?: string | null
    type: string
    defaultValue: any
    possibleValues?: any
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

export interface PluginAddPayload {
    path?: string
    gitUrl?: string
    pluginName: string
}

// ============= Actions ==============

export class FunctionDescription {
    id: string
    name: string
    label: string
    description: string
    params: ParamDescription[]
    hooks: string[]
}

export interface Actions {
    [id: string]: FunctionDescription
}

export interface ParamDefaults {
    [id: string]: any
}

export interface ActionParam {
    name: string
    value: string
}

export interface ActionContext {
    instanceIds?: number[]
    propertyIds?: number[]
    file?: string
    text?: string
    uiInputs?: { [key: string]: any }
}

export interface ExecuteActionPayload {
    function: string
    context: ActionContext
}

export interface GroupResult {
    ids?: number[]
    sha1s?: number[]
    scores?: ScoreList

    score?: Score
    name?: string
}

export interface ActionResult {
    instances?: GroupResult
    groups?: GroupResult[]

    properties?: number[]
    datas?: any[]
    urls?: string[]
    commit?: DbCommit

    notifs?: Notif[]
    errors?: string[]
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

// ========= Commit =================
export interface DbCommit {
    emptyInstances?: number[]
    emptyProperties?: number[]
    emptyTags?: number[]
    emptyInstanceValues? : InstancePropertyValue[]
    emptyImageValues?: ImagePropertyValue[]

    instances?: Instance[]
    properties?: Property[]
    tags?: Tag[]
    instanceValues?: InstancePropertyValue[]
    imageValues?: ImagePropertyValue[]

    undo?: boolean
    history?: CommitHistory
}

export interface CommitStat {
    timestamp: string
    tags: number
    values: number
}

export interface CommitHistory {
    undo: CommitStat[]
    redo: CommitStat[]
}

export interface Update {
    commits?: DbCommit[]
    plugins?: PluginDescription[]
    actions?: FunctionDescription[]
    status?: StatusUpdate
}

export interface ProjectSettings {
    imageSmallSize: number
    imageMediumSize: number
    imageLargeSize: number

    saveImageSmall: boolean
    saveImageMedium: boolean
    saveImageLarge: boolean

    saveFileRaw: boolean
}


// ========= Notifications =========

export enum NotifType {
    DEBUG = 'debug',
    INFO = 'info',
    WARNING = 'warning',
    ERROR = 'error'
}

export interface NotifFunction extends ExecuteActionPayload {
    message: string
    context: ActionContext
}

export interface Notif {
    type?: NotifType

    id?: number
    createdAt?: Date
    receivedAt?: Date
    name?: string
    message?: string
    data?: any

    functions?: NotifFunction[]

    read?: boolean
}

// =============== Scores ==========
export interface Score {
    value: number
    min: number
    max: number
    description: string
    maxIsBest: boolean
}

export interface ScoreList {
    values: number[]
    min: number
    max: number
    description: string
    maxIsBest: boolean
}

export interface GroupScoreList {
    valueIndex: ScoreIndex
    min: number
    max: number
    description: string
    maxIsBest: boolean
}

export interface ScoreIndex {
    [instanceId: number]: number
}

export interface IgnoredPlugins {
    [project: string]: string[]
}

export interface IngoredPluginPayload {
    project: string
    plugin: string
    value: boolean
}