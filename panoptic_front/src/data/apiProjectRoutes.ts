/**
 * Fichier servant à regrouper les fonctions permettant de communiquer avec le serveur
 */

import axios from 'axios'
import { PluginKey, usePanopticStore } from './panopticStore'
import {
    DbCommit,
    Tag,
    UploadConfirm,
    ExecuteActionPayload,
    PluginDescription,
    ProjectVectorDescription,
    VectorDescription,
    ActionFunctions,
    TabState,
    TabData,
    ImageType,
    ImageStats,
    CommitHistory,
    ActionResult,
    Update,
    ProjectSettings,
    LoadResult,
    VectorType,
    VectorStats,
    ProjectState,
    PluginAddPayload,
    ApiRequestDescription,
    Notif,
    NotifType,
    ImportVerify,
    PointMap,
    ImageAtlas
} from './models'
import { deepCopy, keysToCamel, keysToSnake, sleep } from '@/utils/utils'

export const projectApi = axios.create({
    baseURL: (import.meta as any).env.VITE_API_ROUTE,
});

projectApi.interceptors.request.use(config => {
    const panoptic = usePanopticStore()
    const projectId = panoptic.connectionState?.connectedProject
    if (projectId) {
        config.url = `/projects/${projectId}${config.url}`
    } else {
        // TODO: maybe we should throw an error here?
        console.error("No project selected for API call")
    }
    if (panoptic.connectionState?.connectionId) {
        config.params = config.params || {};
        config.params.connection_id = panoptic.connectionState?.connectionId
    }
    return config
})

async function uploadFile(route: string, file) {
    let formData = new FormData()
    formData.append('file', file)
    const res = await projectApi.post(route,
        formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    })
    return res
}

// Define an interface for optional extra data fields
interface AdditionalData {
    [key: string]: string | number | boolean
}

async function uploadFileWithData(route: string, file: File, data: AdditionalData = {}) {
    let formData = new FormData()

    // 1. Append the file
    formData.append('file', file)

    // 2. Append additional data fields
    for (const key in data) {
        if (Object.prototype.hasOwnProperty.call(data, key)) {
            // Convert numbers/booleans to string before appending to FormData
            formData.append(key, String(data[key]))
        }
    }

    // Note: When using modern JS libraries (like Axios or Fetch) and FormData,
    // the browser usually sets the 'Content-Type': 'multipart/form-data' 
    // including the boundary automatically. While explicitly setting it often works, 
    // removing it often simplifies things and prevents boundary errors. 
    // I'll keep it simple here, assuming projectApi handles the multipart request.

    const res = await projectApi.post(route, formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    })
    return res
}

projectApi.interceptors.response.use(response => response, (error) => {
    const panoptic = usePanopticStore()

    const baseURL: string = error.config.baseURL
    const method = error.config.method
    const url = error.config.url
    const data = error.config.data
    const traceback = error.response?.data?.traceback
    const message = error.response?.data?.message
    const errorName = error.response?.data?.name

    const req: ApiRequestDescription = {
        method, baseURL, url, data
    }

    const notif: Notif = { type: NotifType.ERROR, name: 'BackendError: ' + errorName, message: message, request: req, unexpected: true, traceback: traceback }
    panoptic.notify(notif)
    return Promise.reject(error)
})

export async function apiGetProjectState() {
    const res = await projectApi.get('/project_state')
    return keysToCamel(res.data) as ProjectState
}

export async function apiGetDbState() {
    const res = await projectApi.get('/db_state')
    return keysToCamel(res.data) as DbCommit
}

export const apiGetTags = async () => {
    const res = await projectApi.get('/tags')
    return keysToCamel(res.data) as Tag[]
}

export async function apiMergeTags(tagIds: number[]) {
    const res = await projectApi.post('/tags/merge', { tag_ids: tagIds })
    return keysToCamel(res.data) as DbCommit
}

export const apiGetProperties = async () => {
    const res = await projectApi.get('/property')
    return keysToCamel(res.data)
}

export const apiAddFolder = async (folder: string) => {
    return await projectApi.post('/folders', { path: folder })
}

export const apiGetFolders = async () => {
    let res = await projectApi.get('/folders')
    return res.data
}

export const apiImportFolder = async () => {
    let res = await projectApi.post('/folders')
    return res.data
}

export async function apiDeleteFolder(folderId: number) {
    let res = await projectApi.delete('/folder', { params: { folder_id: folderId } })
    return keysToCamel(res.data)
}

export async function apiGetAllTabs(): Promise<TabData[]> {
    let res = await projectApi.get('/tabs')
    return (res.data ?? []) as TabData[]
}

export async function apiCreateTab(id: string, state: TabState, selection?: number[]) {
    await projectApi.post('/tabs', { id, state, selection: selection ?? null })
}

export async function apiUpdateTabState(id: string, state: TabState) {
    await projectApi.put(`/tabs/${id}`, { state })
}

export async function apiDeleteTab(id: string) {
    await projectApi.delete(`/tabs/${id}`)
}

export const apiUploadPropFile = async (file: any) => {
    let formData = new FormData()
    formData.append('file', file)
    const res = await projectApi.post('/property/file',
        formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    })
    return res
}

export async function apiUploadPropertyCsv(file) {
    const res = await uploadFile('/import/upload', file)
    console.log(res.data)
    return keysToCamel(res.data) as UploadConfirm
}

export async function apiUploadTagsCsv(file, propId) {
    const res = await uploadFileWithData('/import/tags', file, { property_id: propId })
    console.log(res.data)
    return keysToCamel(res.data) as UploadConfirm
}

export async function apiParseImport(options) {
    const res = await projectApi.post('/import/parse', options)
    return keysToCamel(res.data) as ImportVerify
}

export async function apiConfirmImport(params) {
    const res = await projectApi.post('/import/confirm', params)
    return keysToCamel(res.data) as DbCommit
}

export const apiExportProperties = async (name?: string, images?: number[], key?: string, properties?: number[], exportImages = false) => {
    let res = await projectApi.post('/export', { name, images, properties, exportImages, key })
}

export async function apiReImportFolder(folderId: number) {
    let res = await projectApi.post('/reimport_folder', { id: folderId })
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

export async function apiDelPlugin(name: string) {
    let res = await axios.delete('/plugins', { params: { name } })
    return res.data as string[]
}

export async function apiUpdatePlugin(name: string) {
    let res = await axios.post('/plugin/update', { name })
    return res.data as boolean
}

export async function apiGetPluginsInfo() {
    let res = await projectApi.get('/plugins_info')
    return keysToCamel(res.data) as PluginDescription[]
}

export async function apiSetPluginParams(plugin: string, params: any) {
    let res = await projectApi.post('/plugin_params', { plugin, params })
    return keysToCamel(res.data) as PluginDescription[]
}

export async function apiGetActions() {
    let res = await projectApi.get('/actions')
    const raw = res.data
    const result: ActionFunctions = {}
    for (const key in raw) {
        result[key] = keysToCamel(raw[key])
    }
    return result as ActionFunctions
}

export async function apiCallActions(req: ExecuteActionPayload) {
    let res = await projectApi.post('/action_execute', keysToSnake(req)).catch((err) => console.log(err.response))
    if (!res) return
    const ares: ActionResult = res.data
    if (ares.commit) ares.commit = keysToCamel(ares.commit)
    if (ares.groups) ares.groups = keysToCamel(ares.groups)
    return ares
}

export async function apiGetVectorInfo() {
    let res = await projectApi.get('/vectors_info')
    return res.data as ProjectVectorDescription
}

export function mapVectorType(p: any[]): VectorType {
    return { id: p[0], source: p[1], params: p[2] }
}

export async function apiGetVectorTypes() {
    let res = await projectApi.get('/vector_types')
    return (res.data as any[]).map(mapVectorType) as VectorType[]
}

export async function apiGetVectorStats() {
    let res = await projectApi.get('/vector_stats')
    return keysToCamel(res.data) as VectorStats
}

export async function apiDeleteVectorType(id: number) {
    let res = await projectApi.post('/delete_vector_type', { id })
}

export async function apiSetDefaultVector(vector: VectorDescription) {
    let res = await projectApi.post('/default_vectors', vector)
    return res.data as ProjectVectorDescription
}

export async function apiGetUIData(key: string) {
    let res = await projectApi.get('/ui_data/' + key)
    return res.data as any
}

export async function apiGetAllUIData() {
    let res = await projectApi.get('/ui_data')
    return res.data as Record<string, any>
}

export async function apiSetUIData(key: string, data: any) {
    let res = await projectApi.post('/ui_data', { key, data })
    return res.data as any
}

export async function apiSetUIDataBulk(data: Record<string, any>) {
    let res = await projectApi.post('/ui_data_bulk', data)
    return res.data as any
}

export async function apiListMaps() {
    const res = await projectApi.get('/list_maps');
    return keysToCamel(res.data) as PointMap[]
}

export async function apiGetMap(mapId: number) {
    const res = await projectApi.get(`/map/${mapId}`);
    return keysToCamel(res.data) as PointMap;
}

export async function apiDeleteMap(mapId: number) {
    const res = await projectApi.delete('/map', {
        params: {
            map_id: mapId
        }
    });
    return keysToCamel(res.data);
}

export async function apiUndo() {
    const res = await projectApi.post('/undo')
    return keysToCamel(res.data) as DbCommit
}

export async function apiRedo() {
    const res = await projectApi.post('/redo')
    return keysToCamel(res.data) as DbCommit
}

export async function apiAllocateTags(n: number): Promise<number[]> {
    const res = await projectApi.get('/allocate/tags', { params: { n } })
    return res.data as number[]
}

export async function apiCommitUpsert(commit: DbCommit): Promise<DbCommit> {
    const fixed: any = {}
    if (commit.properties?.length) fixed.properties = commit.properties.map(p => keysToSnake(p))
    if (commit.tags?.length) fixed.tags = commit.tags.map(t => keysToSnake(t))
    if (commit.instanceValues?.length) fixed.instance_values = commit.instanceValues.map(v => keysToSnake(v))
    if (commit.imageValues?.length) fixed.image_values = commit.imageValues.map(v => keysToSnake(v))
    if (commit.fileValues?.length) fixed.file_values = commit.fileValues.map(v => keysToSnake(v))
    if (commit.propertyGroups?.length) fixed.property_groups = commit.propertyGroups.map(g => keysToSnake(g))
    if (commit.instances?.length) fixed.instances = commit.instances.map(i => keysToSnake(i))
    const res = await projectApi.post('/commit/upsert', fixed)
    return keysToCamel(res.data) as DbCommit
}

export async function apiCommitDelete(commit: DbCommit): Promise<void> {
    const fixed: any = {}
    if (commit.emptyInstances?.length) fixed.empty_instances = commit.emptyInstances
    if (commit.emptyProperties?.length) fixed.empty_properties = commit.emptyProperties
    if (commit.emptyTags?.length) fixed.empty_tags = commit.emptyTags
    if (commit.emptyPropertyGroups?.length) fixed.empty_property_groups = commit.emptyPropertyGroups
    if (commit.emptyInstanceValues?.length) fixed.empty_instance_values = commit.emptyInstanceValues.map(v => keysToSnake(v))
    if (commit.emptyImageValues?.length) fixed.empty_image_values = commit.emptyImageValues.map(v => keysToSnake(v))
    if (commit.emptyFileValues?.length) fixed.empty_file_values = commit.emptyFileValues.map(v => keysToSnake(v))
    await projectApi.post('/commit/delete', fixed)
}

export async function apiGetHistory() {
    const res = await projectApi.get('/history')
    return res.data as CommitHistory
}

export async function apiGetImageTypes(): Promise<ImageType[]> {
    const res = await projectApi.get('/image_types')
    return keysToCamel(res.data) as ImageType[]
}

export async function apiUpsertImageType(type: ImageType): Promise<ImageType> {
    const res = await projectApi.post('/image_types', keysToSnake(type))
    return keysToCamel(res.data) as ImageType
}

export async function apiDeleteImageType(typeId: number) {
    await projectApi.delete(`/image_types/${typeId}`)
}

export async function apiGetImageStats(): Promise<ImageStats> {
    const res = await projectApi.get('/image_stats')
    return keysToCamel(res.data) as ImageStats
}

export async function apiGetSettings() {
    const res = await projectApi.get('/settings')
    return keysToCamel(res.data) as ProjectSettings
}

export async function apiSetSettings(settings: ProjectSettings) {
    const res = await projectApi.post('/settings', keysToSnake(settings))
    return keysToCamel(res.data)
}

async function _streamNdjson<T>(url: string, callback: (data: T) => void | Promise<void>) {
    const response = await fetch(url, { method: 'GET' })
    if (!response.ok) throw new Error('Failed to fetch data from the stream')
    const reader = response.body?.getReader()
    if (!reader) throw new Error('No reader available')

    const decoder = new TextDecoder()
    let buffer = ''
    try {
        while (true) {
            const { done, value } = await reader.read()
            if (done) {
                if (buffer.trim()) {
                    try { await callback(keysToCamel(JSON.parse(buffer))) }
                    catch (e) { console.error('Failed to parse final chunk:', buffer, e) }
                }
                break
            }
            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''
            for (const line of lines) {
                const trimmed = line.trim()
                if (!trimmed) continue
                try { await callback(keysToCamel(JSON.parse(trimmed))) }
                catch (e) { console.error('Failed to parse line:', trimmed, e) }
            }
            if (lines.length > 0) await new Promise(r => requestAnimationFrame(r))
        }
    } finally {
        reader.releaseLock()
    }
}

export async function apiStreamSlimState(callback: (data: LoadResult) => void) {
    const projectId = usePanopticStore().connectionState?.connectedProject
    await _streamNdjson(
        `${(import.meta as any).env.VITE_API_ROUTE}/projects/${projectId}/db_state_slim`,
        callback
    )
}

export async function apiStreamLoadState(callback: (data: LoadResult) => void) {
    const projectId = usePanopticStore().connectionState?.connectedProject
    await _streamNdjson(
        `${(import.meta as any).env.VITE_API_ROUTE}/projects/${projectId}/db_state_stream`,
        callback
    )
}

export type InstanceBaseBatch = {
    ids: number[]
    sha1s: (string | null)[]
    fileIds: (number | null)[]
}

export async function apiStreamInstanceBase(callback: (batch: InstanceBaseBatch) => void | Promise<void>) {
    const projectId = usePanopticStore().connectionState?.connectedProject
    await _streamNdjson<InstanceBaseBatch>(
        `${(import.meta as any).env.VITE_API_ROUTE}/projects/${projectId}/instances/base`,
        callback,
    )
}

export async function apiGetInitState() {
    const res = await projectApi.get('/init_state')
    return keysToCamel(res.data)
}

export async function apiPostDeleteEmptyClones() {
    const res = await projectApi.post('/delete_empty_clones')
    return keysToCamel(res.data)
}

export async function apiBenchmark() {
    console.log('start bench')
    let old = performance.now()
    const res = await projectApi.get('/benchmark')
    console.log((performance.now()-old) / 1000)
    console.log(res.data)
    return res.data
}

export async function apiGetAtlas(atlasId: number) {
    const res = await projectApi.get('/atlas/' + String(atlasId))
    return keysToCamel(res.data) as ImageAtlas
}

export async function apiGetDelta(
    since: number,
    opts?: { fullPropIds?: number[]; pointPropIds?: number[]; instanceIds?: number[] }
): Promise<LoadResult> {
    const params: Record<string, string> = { since: String(since) }
    if (opts?.fullPropIds?.length)  params.full_prop_ids  = opts.fullPropIds.join(',')
    if (opts?.pointPropIds?.length) params.point_prop_ids = opts.pointPropIds.join(',')
    if (opts?.instanceIds?.length)  params.instance_ids   = opts.instanceIds.join(',')
    const res = await projectApi.get('/delta', { params })
    return keysToCamel(res.data) as LoadResult
}