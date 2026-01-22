import { FilterState } from "@/core/FilterManager"
import { Group, GroupState, ImageIterator } from "@/core/GroupManager"
import { SortState } from "@/core/SortManager"
import { PluginKey } from "./panopticStore"

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
    containerMaxRatio?: number

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
    propertyGroupId?: number
    computed?: boolean
    tags?: TagIndex
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

export interface ImageValuesArray {
    propertyId: number
    sha1s: string[]
    values: any[]
}

export interface InstanceValuesArray {
    propertyId: number
    ids: string[]
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

export interface CollectionState {
    autoReload: boolean,
    instances?: number[],
    filterBySelection?: boolean
}

export interface ScoreInterval {
    min: number
    max: number
    maxIsBest: boolean
    values: number[]
    description: string
}

export interface TabState {
    version: number
    id: number
    name: string
    display: string
    selected?: boolean

    collectionState: CollectionState
    filterState: FilterState
    sortState: SortState,
    groupState: GroupState,

    imageSize: number
    visibleProperties: { [key: number]: boolean }
    visibleFolders: { [key: number]: boolean }
    selectedFolders: { [key: number]: boolean }
    propertyOptions: { [key: number]: PropertyOption }
    mapOptions: MapOptions

    isSelection?: boolean
}

export interface MapOptions {
    showImages: boolean
    showPoints: boolean
    showBoxes: boolean
    selectedMap: number
    groupOption: string,
}

export interface TabData {
    version: number
    id: number
    name: string
    display: string

    filterState: FilterState
    sortState: SortState,
    groupState: GroupState,



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
    { name: 'orange', color: '#ffa94d' }
]

export const greyColor = { name: 'grey', color: '#808080'}

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
    vectorType: number;
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
    source: string
    type: string
    baseParams: PluginBaseParamsDescription
    registeredFunctions: FunctionDescription[]
    defaults: PluginDefaultParams
}

export interface PluginDefaultParams {
    name: string
    base: { [param: string]: any }
    functions: { [func: string]: { [param: string]: any } }
}

export enum PluginType {
    PIP = "pip",
    GIT = "git",
    LOCAL = "local"
}

export interface PluginAddPayload {
    source: string
    name: string
    type: PluginType
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

export interface ActionFunctions {
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
    sha1s?: string[]
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
    value?: any
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

export interface VectorType {
    id: number
    source: string
    params: any
}

export interface VectorStats {
    count: { [id: number]: number }
    sha1Count: number
}

// ========= Commit =================
export interface DbCommit {
    emptyInstances?: number[]
    emptyPropertyGroups?: number[]
    emptyProperties?: number[]
    emptyTags?: number[]
    emptyInstanceValues?: InstancePropertyValue[]
    emptyImageValues?: ImagePropertyValue[]

    instances?: Instance[]
    propertyGroups?: PropertyGroup[]
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

export interface UiState {
    activeTab?: number
    lang?: string
    similarityIntervals: { [key: string]: ScoreInterval },
    similarityImageSize: number
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

export interface ApiRequestDescription {
    method: string,
    baseURL: string,
    url: string,
    data: any
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
    unexpected?: boolean
    traceback?: string[]

    request?: ApiRequestDescription
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
    COMPUTED = -2
}

export interface LoadResult {
    chunk?: DbCommit
    state: LoadState
    instanceValues?: InstanceValuesArray[]
    imageValues?: ImageValuesArray[]
}

export interface LoadState {
    finishedProperty?: boolean
    finishedInstance?: boolean
    finishedTags?: boolean
    finishedInstanceValues?: boolean
    finishedImageValues?: boolean
    finishedPropertyGroups?: boolean

    counterInstance: number
    counterInstanceValue: number
    counterImageValue: number

    maxInstance: number
    maxInstanceValue: number
    maxImageValue: number
}

export enum UploadError {
    no_key = 'no_key',
    invalid_type = 'invalid_type'
}

export interface UploadConfirm {
    key: string
    colToProperty: { [key: number]: Property }
    errors: { [key: number]: UploadError }
}

export interface ImportVerify {
    missingRows: number[]
    newInstancesCount: number[]
}

export enum UIDataKeys {
    STATE = 'uiState',
    PROPERTY_ORDER = 'propertyOrder'
}

// ========= Panoptic State =========

export interface ProjectId {
    id: number;
    name?: string;
    path?: string;
}

export interface ProjectRef extends ProjectId {
    isOpen: boolean
    ignoredPlugins: string[]
}


export interface User {
    id: number
    name: string
}

export interface UserState extends User {
    connectedTo?: string
}

export interface PanopticServerState {
    version: string
    projects: ProjectRef[]
    plugins: PluginKey[]
    users: User[]
    askUser: boolean
}

export interface PanopticClientState {
    connectionId: string
    connectedProject?: number
    connectedAt: string; // datetime
    user: UserState
}


export interface PanopticState {
    server: PanopticServerState
    client: PanopticClientState
}

export interface ProjectState {
    id: number
    name: string
    path: string
    tasks: TaskState[]
    plugins: PluginDescription[]
    settings: ProjectSettings
}

export interface TextQuery {
    type: string
    text?: string
    ctx?: ActionContext
}

export interface PointMap {
    id: number
    source: string
    name: string
    key: string
    count: number
    data?: any[]
}

export interface MapIndex {
    [mapId: number]: PointMap
}

export interface BoundingBox {
    minX: number
    minY: number
    maxX: number
    maxY: number 
    color: string
}

export interface MapGroup {
    id: number
    name: string
    color: string
    count: number
    points: PointData[]
    box: BoundingBox
}

// Atlas
export interface ImageAtlas {
    id: number
    atlasNb: number
    width: number
    height: number
    cellWidth: number
    cellHeight: number
    sha1Mapping: Record<string, [number, number]>
}

export interface ZoomParams {
    h: number
    z1: number
    z2: number
}

export interface PointData {
    x: number
    y: number
    z: number
    color: string
    tint?: string,
    tintAlpha: number
    sha1: string
    ratio: number,
    id?: number,
    border?: number
    borderColor?: string
    order: number
}

export interface PointIndex { [pointId: number]: PointData }