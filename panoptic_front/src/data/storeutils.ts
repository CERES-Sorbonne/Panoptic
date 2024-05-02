import { getFolderAndParents } from "@/utils/utils"
import { Folder, FolderIndex, Image, Property, PropertyIndex, PropertyValue, Tag, TagIndex } from "./models"

export function computeContainerRatio(img: Image) {
    let ratio = img.width / img.height
    return Math.max(Math.min(2, ratio), 1)
}

export function buildFolderNodes(folders: Array<Folder>) {
    let res = {} as FolderIndex
    folders.forEach(f => {
        f.children = []
        res[f.id] = f
    })

    let parentMap = {} as { [key: number]: Array<Folder> }
    folders.forEach(f => {
        if (!f.parent) {
            return
        }
        if (parentMap[f.parent] == undefined) {
            parentMap[f.parent] = []
        }
        parentMap[f.parent].push(f)
    })
    Object.keys(parentMap).forEach((parentId: any) => {
        if (parentId == undefined) {
            return
        }
        parentMap[parentId].forEach(f => {
            res[parentId].children.push(f)
        })
    })
    return res
}

export function computeTagCount(images: Image[], properties: PropertyIndex) {
    for(let property of Object.values(properties) as Property[]) {
        if(!property.tags) continue
        for(let tag of Object.values(property.tags) as Tag[]) {
            tag.count = 0
        }
    }

    for(let img of images) {
        for(let propValue of Object.values(img.properties) as PropertyValue[]) {
            const property = properties[propValue.propertyId]
            if(!property) continue
            if(!property.tags) continue
            if(!propValue.value || !Array.isArray(propValue.value)) continue

            for(let tagId of propValue.value) {
                if(!property.tags[tagId]) continue
                property.tags[tagId].count += 1
            }
        }
    }
}

export function countImagePerFolder(folders: FolderIndex, images: Image[]) {
    const folderToParents: {[fId: number]: number[]} = {} 
    const folderList = Object.values(folders) as Folder[]
    folderList.forEach(folder => {
        folderToParents[folder.id] = getFolderAndParents(folder)
        folder.count = 0
    })

    images.forEach(img => folderToParents[img.folderId].forEach(id => folders[id].count += 1))
}

export function setTagsChildren(tags: TagIndex) {
    for(let tagId in tags) {
        const tag = tags[tagId]
        tag.children = []
    }

    for(let tagId in tags) {
        const tag = tags[tagId]
        tag.parents.filter(tId => tId > 0).forEach(tId => tags[tId].children.push(tag.id))
    }
}