/**
 * Fichier servant à regrouper les fonctions permettant de communiquer avec le serveur
 */

import axios from 'axios'
import { ActionContext, DirInfo, ImageIndex, Property, PropertyMode, PropertyType, PropertyValueUpdate, StatusUpdate, TabState, Tag } from './models'
import { SelectionStatus } from './panopticStore'

export const SERVER_PREFIX = (import.meta as any).env.VITE_API_ROUTE
axios.defaults.baseURL = SERVER_PREFIX

export interface ApiTab {
    id?: number,
    data: TabState
}

axios.interceptors.response.use()

export const apiGetImages = async (): Promise<ImageIndex> => {
    const res = await axios.get(`/images`)
    const images = Object.fromEntries(Object.entries(res.data as ImageIndex).map(([k, v]) => [k, { ...v, url: SERVER_PREFIX + '/small/images/' + v.sha1 + '.jpeg', fullUrl: SERVER_PREFIX + v.url }]))
    return images
}

export const apiGetTags = async () => {
    const res = await axios.get('/tags')
    return res.data
}

export const apiGetProperties = async () => {
    const res = await axios.get('/property')
    return res.data
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
    return res.data
}

export const apiAddTagParent = async (tagId: number, parentId: number) => {
    const res = await axios.post('tag/parent', { tagId, parentId })
    return res.data
}

export const apiAddProperty = async (name: string, type: PropertyType, mode: PropertyMode): Promise<Property> => {
    const res = await axios.post('/property', { name, type, mode })
    return res.data
}

export const apiSetPropertyValue = async (propertyId: number, imageIds: number[] | undefined, sha1s: string[] | undefined, value: any, mode: string = null): Promise<PropertyValueUpdate> => {
    // only arrays are tags lists
    if (Array.isArray(value)) {
        value = value.map(Number)
    }
    // console.log({imageIds, sha1s, propertyId, value})
    const res = await axios.post('/image_property', { imageIds, sha1s, propertyId, value, mode })
    // console.log(res.data)
    return res.data
}

export const apiUpdateTag = async (id: number, color?: number, parentId?: number, value?: any): Promise<Tag> => {
    const res = await axios.patch('/tags', { id, color, parent_id: parentId, value })
    return res.data
}

export const apiDeleteTagParent = async (id: number, parentId: number): Promise<any> => {
    const res = await axios.delete('/tags/parent', { params: { tag_id: id, parent_id: parentId } })
    return res.data
}

export const apiDeleteTag = async (tag_id: number): Promise<any> => {
    const res = await axios.delete('/tags', { params: { tag_id} })
    return res.data
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
    let res = await axios.post('/similar/image', context)
    return res.data
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

export const apiExportProperties = async (name?: string, images?: number[], properties?: number[], exportImages = false) => {
    let res = await axios.post('/export', {name, images, properties, exportImages})
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
    let res = await axios.post('/delete_project', {path})
    return res.data as SelectionStatus
}

export async function apiCreateProject(path: string, name: string) {
    let res = await axios.post('/create_project', {path, name})
    return res.data as SelectionStatus
}

export async function apiImportProject(path: string) {
    let res = await axios.post('/import_project', {path})
    return res.data as SelectionStatus
}

export async function apiReImportFolder(folderId: number) {
    let res = await axios.post('/reimport_folder', {id: folderId})
    return res.data
}

export async function apiSetUiVersion(version: string) {
    let res = await axios.post('/version/ui', {value: version})
    return res.data
}

export async function apiGetUiVersion() {
    let res = await axios.get('/version/ui')
    return res.data as string
}