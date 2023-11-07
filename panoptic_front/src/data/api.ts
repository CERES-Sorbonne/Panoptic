/**
 * Fichier servant à regrouper les fonctions permettant de communiquer avec le serveur
 */

// à virer
import { Images, Property, PropertyMode, PropertyType, PropertyValue, PropertyValueUpdate, Tab, TabState, Tag } from './models'

import axios from 'axios'
import { saveFile } from '@/utils/api'

export const SERVER_PREFIX = (import.meta as any).env.VITE_API_ROUTE
axios.defaults.baseURL = SERVER_PREFIX


export const apiGetImages = async ():Promise<Images> => {
    const res = await axios.get(`/images`)
    const images = Object.fromEntries(Object.entries(res.data as Images).map(([k,v]) => [k, {...v, url: SERVER_PREFIX + '/small/images/' + v.sha1 + '.jpeg', fullUrl: SERVER_PREFIX + v.url}]))
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
    ):Promise<Tag> => {
    const res = await axios.post('/tags', {
        propertyId,
        value,
        color,
        parentId,
    })
    return res.data
}

export const apiAddTagParent = async (tagId: number, parentId: number) => {
    const res = await axios.post('tag/parent', {tagId, parentId})
    return res.data
}

export const apiAddProperty = async(name: string, type: PropertyType, mode: PropertyMode):Promise<Property> => {
    const res = await axios.post('/property', {name, type, mode})
    return res.data
}

export const apiSetPropertyValue = async(propertyId:number, imageIds: number[] | undefined, sha1s: string[] | undefined, value: any, mode: string = null):Promise<PropertyValueUpdate> => {
    // only arrays are tags lists
    if(Array.isArray(value)) {
        value = value.map(Number)
    }
    // console.log({imageIds, sha1s, propertyId, value})
    const res = await axios.post('/image_property', {imageIds, sha1s, propertyId, value, mode})
    // console.log(res.data)
    return res.data
}

export const apiUpdateTag = async(id: number, color?:number, parentId?: number, value?: any):Promise<Tag> => {
    const res = await axios.patch('/tags', {id, color, parentId, value})
    return res.data
}

export const apiDeleteTagParent = async(id: number, parentId: number):Promise<any> => {
    const res = await axios.delete('/tags/parent', {params:{tag_id: id, parent_id: parentId}})
    return res.data
}

export const apiAddFolder = async(folder: string) => {
    return await axios.post('/folders', {folder})
}

export const apiUpdateProperty = async(propertyId: number, name?: string):Promise<Property> => {
    return await axios.patch('/property', {id:propertyId, name})
}

export const apiDeleteProperty = async(propertyId: number) => {
    const res = await axios.delete(`/property/${propertyId}`)
    return res.data
}

export const apiGetFolders = async() => {
    let res = await axios.get('/folders')
    return res.data
}

export const apiImportFolder = async() => {
    let res = await axios.post('/folders')
    return res.data
}

export const apiGetTabs = async() => {
    let res = await axios.get('/tabs')
    return res.data
}

export const apiAddTab = async(tab: Tab) => {
    let res = await axios.post('/tab', tab)
    return res.data
}

export const apiUpdateTab = async(tab: Tab) => {
    const toSend = Object.assign({}, tab)
    toSend.data = Object.assign({}, tab.data)
    delete toSend.data.filterManager
    let res = await axios.patch('/tab', tab)
    return res.data
}

export const apiDeleteTab = async(tabId: number) => {
    let res = await axios.delete('/tab', {params: {tab_id: tabId}})
    return res.data
}

export const apiGetMLGroups = async(nbGroups=50, imageList: string[] = []) => {
    let res = await axios.post('/clusters', {imageList, nbGroups})
    return res.data
}

export const apiGetImportStatus = async() => {
    let res = await axios.get('/import_status')
    res.data.new_images = Object.entries(res.data.new_images as Images).map(([k,v]) => ({...v, url: SERVER_PREFIX + '/small/images/' + v.sha1 + '.jpeg', fullUrl: SERVER_PREFIX + v.url}))
    // console.log(res.data)
    return res.data
}

export const apiGetSimilarImages = async(sha1List: string[]) => {
    let res = await axios.post('/similar/image', {sha1List})
    return res.data
}

export const apiGetSimilarImagesFromText = async(inputText: string) => {
    let res = await axios.post('/similar/text', {inputText})
    return res.data
}

// TODO: remove this when fixed
export const apiStartPCA = async() => {
    return await axios.post('/pca')
}

export const apiUploadPropFile = async(file: any) => {
    let formData = new FormData();
      formData.append('file', file);
      axios.post('/property/file',
      formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      }
    )
}

export const apiExportProperties = async(images?: number[], properties?: number[]) => {
    let res = await axios.post('/export', {...(images && {images}), ...(properties && {properties})})
    saveFile(res, "panoptic_output.csv")
}