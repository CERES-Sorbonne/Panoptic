import { Folder } from "@/data/models"
import { useDataStore } from "@/data/stores/dataStore"

export function getFolderAndParents(folder: Folder) {
    const data = useDataStore()
    const res = []
    let current = folder
    while (current) {
        res.push(current.id)
        current = data.folders[current.parent]
    }
    return res
}

export function getFolderChildren(folderId: number) {
    const data = useDataStore()
    let res: Folder[] = []
    const recursive = (fId: number) => {
        const children = data.folders[fId].children
        res.push(...children)
        children.forEach(c => recursive(c.id))
    }
    recursive(folderId)
    return res
}
