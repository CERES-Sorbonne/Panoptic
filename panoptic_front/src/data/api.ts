/**
 * Fichier servant à regrouper les fonctions permettant de communiquer avec le serveur
 */

import axios from 'axios'
import { ActionContext, ActionDescription, ActionParam, DeleteTagResult, DirInfo, ExecuteActionPayload, ImageIndex, InstancePropertyValue, PluginDefaultParams, PluginDescription, ProjectVectorDescription, Property, PropertyDescription, PropertyMode, PropertyType, PropertyValueUpdate, SearchResult, StatusUpdate, TabState, Tag, VectorDescription } from './models'
import { SelectionStatus } from './panopticStore'
import { keysToCamel } from '@/utils/utils'
import {createReadStream} from 'fs'

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

export interface ApiTab {
    id?: number,
    data: TabState
}

// axios.interceptors.response.use()

export const apiGetImages = async (): Promise<ImageIndex> => {
    const res = await axios.get(`/images`)
    // console.log(res.data)
    const images = Object.fromEntries(Object.entries(res.data as ImageIndex).map(([k, v]) => [k, { ...v, url: SERVER_PREFIX + '/small/images/' + v.sha1 + '.jpeg', fullUrl: SERVER_PREFIX + '/images/' + v.url }]))
    return keysToCamel(images)
}

export const apiGetTags = async () => {
    const res = await axios.get('/tags')
    return keysToCamel(res.data) as Tag[]
}

export const apiGetProperties = async () => {
    const res = await axios.get('/property')
    return keysToCamel(res.data)
}

export const apiAddTag = async (
    propertyId: number,
    value: string,
    color?: number,
    parentId?: number
): Promise<Tag> => {
    const res = await axios.post('/tags', {
        propertyId,
        value,
        color,
        parentId,
    })
    return keysToCamel(res.data)
}

export const apiAddTagParent = async (tagId: number, parentId: number) => {
    const res = await axios.post('tag/parent', { tagId, parentId })
    return keysToCamel(res.data)
}

export const apiAddProperty = async (name: string, type: PropertyType, mode: PropertyMode): Promise<Property> => {
    const res = await axios.post('/property', { name, type, mode })
    return keysToCamel(res.data)
}

export const apiSetPropertyValue = async (propertyId: number, instanceIds: number[], value: any): Promise<InstancePropertyValue[]> => {
    // only arrays are tags lists
    if (Array.isArray(value)) {
        value = value.map(Number)
    }
    // console.log({imageIds, sha1s, propertyId, value})
    const res = await axios.post('/image_property', { instanceIds, propertyId, value })
    // console.log(res.data)
    return keysToCamel(res.data)
}

export const apiSetTagPropertyValue = async (propertyId: number, instanceIds: number[], value: any, mode): Promise<InstancePropertyValue[]> => {
    if (Array.isArray(value)) {
        value = value.map(Number)
    }
    const res = await axios.post('/set_tag_property_value', { instanceIds, propertyId, value, mode })
    return keysToCamel(res.data)
}



export const apiUpdateTag = async (id: number, color?: number, parentId?: number, value?: any): Promise<Tag> => {
    const res = await axios.patch('/tags', { id, color, parent_id: parentId, value })
    return keysToCamel(res.data)
}

export const apiDeleteTagParent = async (id: number, parentId: number): Promise<any> => {
    const res = await axios.delete('/tags/parent', { params: { tag_id: id, parent_id: parentId } })
    return keysToCamel(res.data)
}

export const apiDeleteTag = async (tag_id: number): Promise<DeleteTagResult> => {
    const res = await axios.delete('/tags', { params: { tag_id } })
    return keysToCamel(res.data)
}

export const apiAddFolder = async (folder: string) => {
    return await axios.post('/folders', { path: folder })
}

export const apiUpdateProperty = async (propertyId: number, name?: string): Promise<Property> => {
    return await axios.patch('/property', { id: propertyId, name })
}

export const apiDeleteProperty = async (propertyId: number) => {
    const res = await axios.delete(`/property/${propertyId}`)
    return res.data
}

export const apiGetFolders = async () => {
    let res = await axios.get('/folders')
    return res.data
}

export const apiImportFolder = async () => {
    let res = await axios.post('/folders')
    return res.data
}

export const apiGetTabs = async () => {
    let res = await axios.get('/tabs')
    return res.data as ApiTab[]
}

export const apiAddTab = async (tab: ApiTab) => {
    let res = await axios.post('/tab', tab)
    return res.data as ApiTab
}

export const apiUpdateTab = async (tab: ApiTab) => {
    let res = await axios.patch('/tab', tab)
    return res.data as TabState
}

export const apiDeleteTab = async (tabId: number) => {
    let res = await axios.delete('/tab', { params: { tab_id: tabId } })
    return res.data
}

export const apiGetMLGroups = async (context: ActionContext) => {
    let res = await axios.post('/clusters', context)
    return res.data
}

export const apiGetStatusUpdate = async () => {
    let res = await axios.get('/import_status')
    // res.data.new_images = Object.entries(res.data.new_images as ImageIndex).map(([k, v]) => ({ ...v, url: SERVER_PREFIX + '/small/images/' + v.sha1 + '.jpeg', fullUrl: SERVER_PREFIX + v.url }))
    // console.log(res.data)
    return res.data as StatusUpdate
}

export const apiGetSimilarImages = async (context: ActionContext) => {
    let req: ExecuteActionPayload = {action: 'find_similar', context: context}
    let res = await apiCallActions(req)
    return res as SearchResult
}

export const apiGetSimilarImagesFromText = async (context: ActionContext) => {
    let res = await axios.post('/similar/text', context)
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
    const res = await uploadFile('/upload_file', file)
    return res.data as PropertyDescription[]
}

export async function apiImportFile(options) {
    const res = await axios.post('/import_file', {options})
    return res.data
}

export const apiExportProperties = async (name?: string, images?: number[], properties?: number[], exportImages = false) => {
    let res = await axios.post('/export', { name, images, properties, exportImages })
}

export async function apiGetFilesystemInfo() {
    let res = await axios.get('/filesystem/info')
    return res.data as { partitions: DirInfo[], fast: DirInfo[] }
}

export async function apiGetFilesystemLs(path: string) {
    let res = await axios.get('/filesystem/ls' + '/' + path)
    return res.data as { directories: DirInfo[], images: [] }
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
    return res.data as string[]
}

export async function apiAddPlugin(path: string) {
    let res = await axios.post('/plugins', { path })
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

export async function apiSetPluginDefaults(defaults: PluginDefaultParams) {
    let res = await axios.post('/plugins_params', defaults)
    return res.data as PluginDefaultParams
}

export async function apiGetActions() {
    let res = await axios.get('/actions_description')
    return res.data as ActionDescription[]
}

export async function apiSetActions(actionUpdates: ActionParam[]) {
    console.log(actionUpdates)
    let res = await axios.post('/actions_functions', { updates: actionUpdates })
    return res.data as ActionDescription[]
}

export async function apiCallActions(req: ExecuteActionPayload) {
    let res = await axios.post('/action_execute', req)
    return res.data
}

export async function apiGetVectorInfo() {
    let res = await axios.get('/vectors_info')
    return res.data as ProjectVectorDescription
}

export async function apiSetDefaultVector(vector: VectorDescription) {
    let res = await axios.post('/default_vectors', vector)
    return res.data as ProjectVectorDescription
}