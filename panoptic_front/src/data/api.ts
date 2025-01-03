/**
 * Fichier servant à regrouper les fonctions permettant de communiquer avec le serveur
 */

import axios from 'axios'
import { DirInfo, ExecuteActionPayload, PluginDescription, ProjectVectorDescription, Tag, VectorDescription, Actions, TabIndex, DbCommit, CommitHistory, ActionResult, Update, ProjectSettings, PluginAddPayload, Notif, NotifType, IngoredPluginPayload } from './models'
import { PluginKey, SelectionStatus, usePanopticStore } from './panopticStore'
import { deepCopy, keysToCamel, keysToSnake } from '@/utils/utils'

export const SERVER_PREFIX = (import.meta as any).env.VITE_API_ROUTE
axios.defaults.baseURL = SERVER_PREFIX

async function uploadFile(route: string, file) {
    let formData = new FormData();
    formData.append('file', file)
    const res = await axios.post(route,
        formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    })
    return res
}
axios.interceptors.response.use(response => response, (error) => {
    const panoptic = usePanopticStore()

    const baseURL = error.config.baseURL
    const method = error.config.method
    const url = error.config.url
    const data = error.config.data

    const notif: Notif = {type: NotifType.ERROR, name: 'BackendError', message: 'Unexpected Error during backend call', data: {method, baseURL, url, data}}
    panoptic.notify(notif)
})

export async function apiGetDbState() {
    const res = await axios.get('/db_state')
    return keysToCamel(res.data) as DbCommit
}

export const apiGetTags = async () => {
    const res = await axios.get('/tags')
    return keysToCamel(res.data) as Tag[]
}

export async function apiMergeTags(tagIds: number[]) {
    const res = await axios.post('/tags/merge', {tag_ids: tagIds})
    return keysToCamel(res.data) as DbCommit
}

export const apiGetProperties = async () => {
    const res = await axios.get('/property')
    return keysToCamel(res.data)
}

export const apiAddFolder = async (folder: string) => {
    return await axios.post('/folders', { path: folder })
}

export const apiGetFolders = async () => {
    let res = await axios.get('/folders')
    return res.data
}

export const apiImportFolder = async () => {
    let res = await axios.post('/folders')
    return res.data
}

export async function apiDeleteFolder(folderId: number) {
    let res = await axios.delete('/folder', { params: { folder_id: folderId } })
    return res.data
}

export async function apiGetTabs() {
    let res = await apiGetUIData('tabs')
    if (!res) {
        return {} as TabIndex
    }
    return res as TabIndex
}

export async function apiSetTabs(tabs: TabIndex) {
    let res = await apiSetUIData('tabs', tabs)
    return res.data
}

export const apiUploadPropFile = async (file: any) => {
    let formData = new FormData();
    formData.append('file', file);
    const res = await axios.post('/property/file',
        formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    })
    return res
}

export async function apiUploadPropertyCsv(file) {
    const res = await uploadFile('/import/upload', file)
    return res.data
}

export async function apiParseImport(options) {
    const res = await axios.post('/import/parse', options)
    return keysToCamel(res.data)
}

export async function apiConfirmImport() {
    const res = await axios.post('/import/confirm')
    return keysToCamel(res.data) as DbCommit
}

export const apiExportProperties = async (name?: string, images?: number[], key?: string, properties?: number[], exportImages = false) => {
    let res = await axios.post('/export', { name, images, properties, exportImages, key })
}

export async function apiGetFilesystemInfo() {
    let res = await axios.get('/filesystem/info')
    return res.data as { partitions: DirInfo[], fast: DirInfo[] }
}

export async function apiGetFilesystemLs(path: string) {
    let res = await axios.get('/filesystem/ls' + '/' + path)
    return res.data as { directories: DirInfo[], images: [] }
}

export async function apiGetFilesystemCount(path: string) {
    let res = await axios.get('/filesystem/count' + '/' + path)
    return res.data as { path: string, count: number }
}


export async function apiGetStatus() {
    let res = await axios.get('/status')
    return res.data as SelectionStatus
}

export async function apiLoadProject(path: string) {
    let res = await axios.post('/load', { path })
    return res.data as SelectionStatus
}

export async function apiCloseProject() {
    let res = await axios.post('/close')
    return res.data as SelectionStatus
}

export async function apiDeleteProject(path: string) {
    let res = await axios.post('/delete_project', { path })
    return res.data as SelectionStatus
}

export async function apiCreateProject(path: string, name: string) {
    let res = await axios.post('/create_project', { path, name })
    return res.data as SelectionStatus
}

export async function apiImportProject(path: string) {
    let res = await axios.post('/import_project', { path })
    return res.data as SelectionStatus
}

export async function apiReImportFolder(folderId: number) {
    let res = await axios.post('/reimport_folder', { id: folderId })
    return res.data
}

export async function apiGetPlugins() {
    let res = await axios.get('/plugins')
    return keysToCamel(res.data) as PluginKey[]
}

export async function apiAddPlugin(payload: PluginAddPayload) {
    let res = await axios.post('/plugins', payload)
    return res.data as string[]
}

export async function apiDelPlugin(path: string) {
    let res = await axios.delete('/plugins', { params: { path } })
    return res.data as string[]
}

export async function apiGetPluginsInfo() {
    let res = await axios.get('/plugins_info')
    return res.data as PluginDescription[]
}

export async function apiSetPluginParams(plugin: string, params: any) {
    let res = await axios.post('/plugin_params', { plugin, params })
    return res.data as PluginDescription[]
}

export async function apiGetActions() {
    let res = await axios.get('/actions')
    return res.data as Actions
}

export async function apiCallActions(req: ExecuteActionPayload) {
    let res = await axios.post('/action_execute', keysToSnake(req))
    if(!res) return
    const ares: ActionResult = res.data
    if (ares.commit) ares.commit = keysToCamel(ares.commit)
    if (ares.groups) ares.groups = keysToCamel(ares.groups)
    return ares
}

export async function apiGetVectorInfo() {
    let res = await axios.get('/vectors_info')
    return res.data as ProjectVectorDescription
}

export async function apiSetDefaultVector(vector: VectorDescription) {
    let res = await axios.post('/default_vectors', vector)
    return res.data as ProjectVectorDescription
}

export async function apiGetUIData(key: string) {
    let res = await axios.get('/ui_data/' + key)
    return res.data as any
}

export async function apiSetUIData(key: string, data: any) {
    let res = await axios.post('/ui_data', { key, data })
    return res.data as any
}

export async function apiUndo() {
    const res = await axios.post('/undo')
    return keysToCamel(res.data) as DbCommit
}

export async function apiRedo() {
    const res = await axios.post('/redo')
    return keysToCamel(res.data) as DbCommit
}

export async function apiCommit(commit: DbCommit) {
    const fixed: any = keysToSnake(deepCopy(commit))
    if (commit.instances) fixed.instances = commit.instances.map(i => keysToSnake(i))
    if (commit.properties) fixed.properties = commit.properties.map(p => keysToSnake(p))
    if (commit.tags) fixed.tags = commit.tags.map(t => keysToSnake(t))
    if (commit.instanceValues) fixed.instance_values = commit.instanceValues.map(v => keysToSnake(v))
    if (commit.imageValues) fixed.image_values = commit.imageValues.map(v => keysToSnake(v))

    // console.log(fixed)
    const res = await axios.post('/commit', fixed)
    return keysToCamel(res.data) as DbCommit
}

export async function apiGetHistory() {
    const res = await axios.get('/history')
    return res.data as CommitHistory
}

export async function apiGetUpdate() {
    const res = await axios.get('/update')
    return keysToCamel(res.data) as Update
}

export async function apiGetSettings() {
    const res = await axios.get('/settings')
    return keysToCamel(res.data) as ProjectSettings
}

export async function apiSetSettings(settings: ProjectSettings) {
    const res = await axios.post('/settings', keysToSnake(settings))
    return keysToCamel(res.data)
}

export async function apiSetIgnoredPlugin(data: IngoredPluginPayload) {
    const res = await axios.post('/ignored_plugin', keysToSnake(data))
    return keysToCamel(res.data)
}