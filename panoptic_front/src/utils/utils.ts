import { Folder, Group, Image, PropertyMode, PropertyRef, Tag, TreeTag, isTag } from "@/data/models"
import { globalStore } from "@/data/store"

export function hasProperty(image: Image, propertyId: number) {
    return image.properties[propertyId] && image.properties[propertyId].value !== undefined
}

export function getImageProperties(id: number) {
    const img = globalStore.images[id]
    let res = globalStore.propertyList.filter(p => p.mode == PropertyMode.id).map(p => {
        let propRef: PropertyRef = {
            propertyId: p.id,
            type: p.type,
            value: hasProperty(img, p.id) ? img.properties[p.id].value : undefined,
            imageId: img.id,
            mode: p.mode
        }
        return propRef
    })
    return res
}

export function getImageProperty(imgId: number, propId: number) {
    const img = globalStore.images[imgId]
    const p = globalStore.properties[propId]
    const propRef: PropertyRef = {
        propertyId: p.id,
        type: p.type,
        value: hasProperty(img, p.id) ? img.properties[p.id].value : undefined,
        imageId: img.id,
        mode: p.mode
    }
    return propRef
}

export function isImageGroup(group: Group) {
    return Array.isArray(group.images) && group.images.length > 0
}

export function isPileGroup(group: Group) {
    return Array.isArray(group.imagePiles) && group.imagePiles.length > 0
}


export function isTagId(propId: number) {
    return isTag(globalStore.properties[propId].type)
}

export function getTagChildren(tag: Tag) {
    const node = globalStore.tagNodes[tag.property_id][tag.id]
    // console.log(node)

    let children = new Set()
    const recursive = (t: TreeTag) => {
        children.add(t.id)
        if(!t.children) return
        t.children.forEach(c => children.add(c.id))
        t.children.forEach(c => recursive(c))
    }
    recursive(node)

    return children
}

export function getFolderAndParents(folder: Folder, parents: number[]=[]) {
    parents.push(folder.id)
    if(folder.parent != undefined) {
        parents = getFolderAndParents(globalStore.folders[folder.parent], parents)
    }
    return parents
}