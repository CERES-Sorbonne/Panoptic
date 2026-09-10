import { getFolderAndParents, isTag } from "@/utils/utils"
import { deletedID, Folder, FolderIndex, Instance, TagIndex } from "./models"
import { GroupManager } from "@/core/GroupManager"
import { useDataStore } from "./dataStore"
import { useColumnStore } from "./columnStore"
import { useInstanceStore } from "./instanceStore"

export function buildFolderNodes(folders: Array<Folder>) {
    let res = {} as FolderIndex
    folders.forEach(f => {
        f.children = []
        res[f.id] = f
        f.count = 0
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
    const images = Object.values(useInstanceStore().instanceData)
    const properties = data.propertyList.filter(p => isTag(p.type))

    for(let tag of Object.values(tags)) {
        tag.count = 0
    }

    console.time('tag-count')

    for(let prop of properties) {
        for(let img of images) {
            if(img.properties[prop.id]) {
                for(let value of img.properties[prop.id]) {
                    tags[value].count += 1
                }
            }
        }
    }

    console.timeEnd('tag-count')
}

export function countImagePerFolder(folders: FolderIndex, images: Instance[]) {
    const data = useDataStore()
    const col = useColumnStore()
    const folderProp = Object.values(data.properties).find(p => p.systemKey === 'folder')
    const folderPropId = folderProp?.id
    const folderToParents: {[fId: number]: number[]} = {}
    const folderList = Object.values(folders) as Folder[]
    folderList.forEach(folder => {
        folderToParents[folder.id] = getFolderAndParents(folder)
        folder.count = 0
    })

    images.forEach(img => {
        if (folderPropId === undefined) return
        const slot = col.slotMap.get(img.id)
        const folderId: number = slot !== undefined ? col.readSlot(folderPropId, slot) : undefined
        if (folderId != null && folderToParents[folderId]) {
            folderToParents[folderId].forEach(id => folders[id].count += 1)
        }
    })
}

// The backend stores `tag.parents` verbatim: it never validates the hierarchy, so the raw
// edge set may contain cycles (two users concurrently making A a parent of B and B a parent
// of A), self-edges and dangling ids. Resolving that is the frontend's job, and it has to be
// *deterministic*: every client must derive the same tree from the same edge set, whatever
// order the tags arrived in. So we sort the edges (child id, then parent id) and add them
// greedily, skipping any edge that would close a loop. The skipped edges are kept in
// `ignoredParents` — `parents` stays the untouched source of truth, so the user can still
// remove a dropped edge, and it is what gets sent back on the next commit.
export function buildTagTree(tags: TagIndex) {
    const ids = Object.keys(tags).map(Number).filter(id => tags[id]?.id !== deletedID)
    ids.sort((a, b) => a - b)

    for (const id of ids) {
        const tag = tags[id]
        tag.children = []
        tag.effectiveParents = []
        tag.ignoredParents = []
    }

    // Is `from` reachable from `target` by walking accepted parent edges? Only ever called on
    // the already-acyclic accepted graph, so no visited set is needed to terminate — but the
    // graph is a DAG, not a tree, so we keep one to avoid re-walking shared ancestors.
    const reaches = (from: number, target: number) => {
        const stack = [from]
        const seen = new Set<number>()
        while (stack.length) {
            const cur = stack.pop()
            if (cur === target) return true
            if (seen.has(cur)) continue
            seen.add(cur)
            const parents = tags[cur]?.effectiveParents
            if (parents) stack.push(...parents)
        }
        return false
    }

    for (const id of ids) {
        const tag = tags[id]
        const parents = [...new Set(tag.parents)].sort((a, b) => a - b)
        for (const parentId of parents) {
            // Drop self-edges, the legacy 0 root, and ids pointing at nothing (a tag deleted
            // by another user, or an unresolved negative placeholder).
            if (parentId === id || parentId <= 0) continue
            const parent = tags[parentId]
            if (!parent || parent.id === deletedID) continue

            if (reaches(parentId, id)) {
                tag.ignoredParents.push(parentId)
                continue
            }
            tag.effectiveParents.push(parentId)
            parent.children.push(id)
        }
    }
}

// Would linking `childId` under `parentId` close a loop in the currently accepted tree?
// Lets the UI refuse the edge up front instead of committing one that buildTagTree would
// silently ignore afterwards.
export function wouldCreateTagCycle(tags: TagIndex, childId: number, parentId: number) {
    if (childId === parentId) return true
    // Walking `children` (the accepted edges) rather than the cached `allChildren` keeps this
    // usable on any index, including one buildTagTree has just rebuilt.
    const stack = [childId]
    const seen = new Set<number>()
    while (stack.length) {
        const cur = stack.pop()
        if (cur === parentId) return true
        if (seen.has(cur)) continue
        seen.add(cur)
        const children = tags[cur]?.children
        if (children) stack.push(...children)
    }
    return false
}