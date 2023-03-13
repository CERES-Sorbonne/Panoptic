/**
 * Fichier servant à regrouper les fonctions permettant de communiquer avec le serveur
 */

// à virer
import { Property, PropertyType, Tag } from './models'

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
    tagValue: string, 
    color?: string, 
    parentId?: number
    ):Promise<Tag> => {
    const res = await axios.post('/tags', {
        propertyId,
        value: tagValue,
        ...(color && {color}),
        ...(parentId && {parentId})
    })
    return res.data
}

export const apiAddProperty = async(name: string, type: PropertyType):Promise<Property> => {
    const res = await axios.post('/property', {name, type})
    return res.data
}