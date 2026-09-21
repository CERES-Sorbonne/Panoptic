import { DbCommit } from "./commit"
import { Notif } from "./notif"
import { Score, ScoreList } from "./vector"

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
    label?: string
    description?: string | null
    params: ParamDescription[]
    hooks: string[]
    // Read by PluginSettings to group functions; not sent by the current backend.
    action?: string
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
    // False when the plugin is enabled for the project but stopped or failed to load
    running: boolean
}

export interface PluginDefaultParams {
    name: string
    base: { [param: string]: any }
    functions: { [func: string]: { [param: string]: any } }
}

export enum PluginType {
    PIP = "pip",
    GIT = "git",
    LOCAL = "path"
}

export interface PluginKey {
    id: string
    sourcePath: string
    sourceType: PluginType
    installPath?: string
}

export interface PluginAddPayload {
    source: string
    name: string
    type: PluginType
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
    groupName?: string
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

export interface IgnoredPlugins {
    [project: string]: string[]
}

export interface IngoredPluginPayload {
    project: string
    plugin: string
    value: boolean
}
