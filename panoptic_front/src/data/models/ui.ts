import { ActionContext } from "./plugin"

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
    NOTIF = "notif",
    FILESOURCE = "filesource",
    SELECTION = "selection",
    LEGACY = "legacy"
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

export enum UIDataKeys {
    STATE = 'uiState',
    PROPERTY_ORDER = 'propertyOrder'
}

export interface TextQuery {
    type: string
    text?: string
    ctx?: ActionContext
}

export interface SelectOption {
    value: string | number
    label?: string
    description?: string
    disabled?: boolean
    icon?: string
}
