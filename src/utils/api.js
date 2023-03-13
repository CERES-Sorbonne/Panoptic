/**
 * Fichier servant à regrouper les fonctions permettant de communiquer avec le serveur
 */

// à virer
import { globalStore } from "../store"
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

export const apiAddTag = async (image, tag) => {
    // à compléter plus tard pour vraiment appeler l'api et en gérant les images comme un dico et pas comme un tableau pcke c'est chiant
    for(let simage of globalStore.images){
        if(simage.name === image.name){
            const newImage = {...simage, tags: [...simage.tags, tag]}
            return newImage
        }
    }
}

export const apiRemoveTag = async(image, tag) => {
    for(let simage of globalStore.images){
        if(simage.name === image){
            return {tags: [simage.tags.filter(t => t != tag)], ...simage}
        }
    }
}

// export const addPropertyTag