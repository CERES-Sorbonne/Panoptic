/**
 * Fichier servant à regrouper les fonctions permettant de communiquer avec le serveur
 */

// à virer
import { globalStore } from "../store"

export const SERVER_PREFIX = "https://ceres.huma-num.fr/panoptic-back/"

export const apiGetImages = async () => {
    const res = await fetch(SERVER_PREFIX + `images/`)
    const images = await res.json()
    return images
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