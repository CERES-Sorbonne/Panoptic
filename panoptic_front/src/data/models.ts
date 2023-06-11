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
    checkbox = "checkbox",


    _ahash = "average hash",
    _sha1 = "sha1",
    _folders = "folders"
}

export enum PropertyMode {
    id = 'id',
    sha1 = 'sha1'
}

export const PropertyNames = {
    [PropertyType.string]: 'Texte',
    [PropertyType.number]: 'Numerique',
    [PropertyType.tag]: 'Tag unique',
    [PropertyType.multi_tags]: 'Tag multiples',
    [PropertyType.image_link]: 'Lien d\'image',
    [PropertyType.url]: 'URL',
    [PropertyType.date]: 'Date',
    [PropertyType.path]: 'Path',
    [PropertyType.color]: 'Couleur',
    [PropertyType.checkbox]: 'Case a cocher',
    [PropertyType._ahash]: 'Hash moyenne',
    [PropertyType._sha1]: 'Sha1',
    [PropertyType._folders]: 'Dossier',

}

export enum PropertyID {
    sha1 = -1,
    ahash = -2,
    folders = -3
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
    mode: string
}

export interface PropertyValue{
    propertyId: number
    // value: string | number | number[] | string[]
    value: any
}

export interface PropertyValueUpdate extends PropertyValue {
    updated_ids: number[]
}

export interface PropertyRef extends PropertyValue {
    type: PropertyType
    imageId: number
}

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
        [id:number]: PropertyValue
    }
    dist?: number
    containerRatio?: number
}

export interface Images {
    [id:number]: Image
}

export interface Folders {
    [id:number]: Folder
}

export interface Properties {
    [id:number]: Property
}

export interface Tabs {
    [id:number]: Tab
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
    images: Images
    importState: ImportState
    imageList: ComputedRef<{url: String, imageName: String}[]>
    folders: Folders
    tabs: Tabs
    fetchAllData: () => void
    [otherOptions: string]: any
}

export interface ReactiveStore{
    tags: Tags,
    tagTrees: TagsTree
    properties: Properties
    propertyList: Array<Property>
    folders: Folders
    tabs: Tabs
    images: Images
    importState: ImportState
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
        case PropertyType._ahash:
        case PropertyType._sha1:
            return [FilterOperator.equal, FilterOperator.equalNot]
            default:
            return []
    }
}

export function propertyDefault(type: PropertyType): any {
    switch(type) {
        case PropertyType.checkbox:
            return false
        case PropertyType.color:
            return '#aaaaaa'
        case PropertyType.date:
            return ''
        case PropertyType.number:
            return 0
        case PropertyType.string:
        case PropertyType.image_link:
        case PropertyType.path:
        case PropertyType._sha1:
        case PropertyType.url:
        case PropertyType._ahash:
            return ''
        case PropertyType.multi_tags:
        case PropertyType.tag:
            return []
        default:
            return ''
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

export interface Tab {
    id?: number
    name: string
    data: TabState
}

export interface TabState {
    name: string
    display: string
    filter: FilterGroup
    groups: Array<number>
    sortList: Array<Sort>
    imageSize: number
    visibleProperties: {[key: number]: boolean}
    visibleFolders: {[key: number]: boolean}
    selectedFolders: {[key: number]: boolean}
}

export interface TabRequest {

}

export interface Sort {
    property_id: number,
    ascending: boolean
}

export interface Group {
    id?: string
    name: string
    images: Array<Image>
    groups: Array<Group>
    children?: Array<string>
    parentId: string
    count: number
    propertyId?: number,
    depth: number,
    index?: number,
    closed?: boolean,
    isCluster?: boolean,
    getSimilarImages?: () => Array<Images>
    similarSha1sBlacklist?: Array<string>
    allSimilarSha1s?: Array<string>
}

export interface GroupIndex {[key: string]: Group}

export interface GroupData {
    root: Group,
    index: GroupIndex,
    order: Array<string>
}

export interface Folder {
    id: number
    name: string
    path: string
    parent: number
    children: Array<Folder>
    show?: boolean // frontend variable to know if exanded in view or not
    selected?: boolean // frontend variable for smart folder filter
}

export interface ImportState {
    to_import: number
    imported: number
    computed: number
    new_images?: Array<Image>
}

export interface ScrollerLine {
    id: number
    type: string
    groupId: string
    data: any
    index: number
    depth: number
    nbClusters: number
    isSimilarities?: boolean
}

export interface GroupLine extends ScrollerLine{
    data: Group
}

export interface RecomendedLine extends ScrollerLine {
    data: Array<Image>
}

export function buildTabState() {
    return {
        name: 'Tab',
        display: 'grid',
        filter: buildFilterGroup(),
        groups: [],
        sortList: [],
        imageSize: 100,
        visibleProperties: {},
        visibleFolders: {},
        selectedFolders: {},
    } as TabState
}

export function buildFilterGroup() {
    return { 
        depth: 0, 
        filters: [], 
        groupOperator: FilterOperator.and, 
        isGroup: true 
    } as FilterGroup
}