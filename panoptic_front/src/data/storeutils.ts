import { getFolderAndParents, isTag } from "@/utils/utils"
import { Folder, FolderIndex, Instance, TagIndex } from "./models"
import { GroupManager } from "@/core/GroupManager"
import { useDataStore } from "./dataStore"

export function computeContainerRatio(img: Instance) {
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

export function computeTagCount() {
    const data = useDataStore()
    const tags = data.tags
    const images = data.instanceList
    const properties = data.propertyList.filter(p => isTag(p.type))

    for(let prop of properties) {
        const grouper = new GroupManager()
        grouper.setGroupOption(prop.id)
        grouper.group(images)
        const root = grouper.result.root
        for(let group of root.children) {
            let value = group.meta.propertyValues[0].value
            if(value == undefined) continue
            tags[value].count = group.images.length
        }
    }
}

export function countImagePerFolder(folders: FolderIndex, images: Instance[]) {
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