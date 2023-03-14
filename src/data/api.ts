/**
 * Fichier servant à regrouper les fonctions permettant de communiquer avec le serveur
 */

// à virer
import { Property, PropertyType, PropertyValue, Tag } from './models'

import axios from 'axios'

export const SERVER_PREFIX = "http://localhost:8000"
axios.defaults.baseURL = SERVER_PREFIX


export const apiGetImages = async () => {
    const res = await axios.get(`/images`)
    return res.data
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
    color?: string, 
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

export const apiAddProperty = async(name: string, type: PropertyType):Promise<Property> => {
    const res = await axios.post('/property', {name, type})
    return res.data
}

export const apiAddPropertyToImage = async(sha1: string, propertyId:number, value: any):Promise<PropertyValue> => {
    const res = await axios.post('/image_property', {sha1, propertyId, value})
    return res.data
}

export const apiUpdateTag = async(id: number, color?:string, parentId?: number, value?: any):Promise<Tag> => {
    const res = await axios.patch('/tags', {id, color, parentId, value})
    return res.data
}

export const apiAddFolder = async(folder: string) => {
    return await axios.post('/folders', {folder})
}

export const apiUpdateProperty = async(propertyId: number, type?: PropertyType, name?: string):Promise<Property> => {
    return await axios.patch('/property', {propertyId, type, name})
}

export const apiDeleteProperty = async(propertyId: number) => {
    return await axios.delete(`/property/${propertyId}`)
}