import { defineStore } from "pinia";
import { computed, ref, shallowRef, triggerRef } from "vue";
import { CommitHistory, DbCommit, Folder, FolderIndex, ImagePropertyValue, Instance, InstanceIndex, InstancePropertyValue, Property, PropertyIndex, PropertyMode, PropertyType, Sha1ToInstances, TabState, Tag, TagIndex } from "./models";
import { objValues } from "./builder";
import { SERVER_PREFIX, apiAddFolder, apiCommit, apiDeleteFolder, apiGetDbState, apiGetFolders, apiGetHistory, apiMergeTags, apiReImportFolder, apiRedo, apiUndo } from "./api";
import { buildFolderNodes, computeContainerRatio, setTagsChildren } from "./storeutils";
import { EventEmitter, deepCopy, getComputedValues, getTagChildren, getTagParents, isTag } from "@/utils/utils";
import { useProjectStore } from "./projectStore";

export const deletedID = -999999999
const deletedName = 'Deleted'

export const useDataStore = defineStore('dataStore', () => {

    const onChange = new EventEmitter()
    const dirtyInstances = new Set()
    let tmpIdCounter = -100

    const folders = ref<FolderIndex>({})
    const instances = shallowRef<InstanceIndex>({})
    const properties = ref<PropertyIndex>({})
    const tags = shallowRef<TagIndex>({})

    const history = ref<CommitHistory>({ undo: [], redo: [] })
    const sha1Index = shallowRef<Sha1ToInstances>({})

    const onUndo = ref(0)

    // =======================
    // =======Computed=======
    // =======================
    const folderRoots = computed(() => {
        return Object.values(folders.value).filter(f => f.parent == null) as Folder[]
    })
    const instanceList = computed(() => objValues(instances.value))
    const propertyList = computed(() => objValues(properties.value))
    const tagList = computed(() => objValues(tags.value).filter(t => t.id != deletedID))


    // =======================
    // =======Functions=======
    // =======================
    async function init() {
        // console.log('iniiit data')
        let dbFolders = await apiGetFolders()
        const folderIndex = buildFolderNodes(dbFolders)
        // for(let folder of objValues(folderIndex)) {
        //     if(folders.value[folder.id]) {
        //         folder.count = folders.value[folder.id].count
        //     }
        // }
        folders.value = folderIndex
        console.time('Request')
        let dbState = await apiGetDbState()
        console.timeEnd('Request')


        console.time('commit')
        applyCommit(dbState)
        console.timeEnd('commit')

        await getHistory()
    }

    function getTmpId() {
        tmpIdCounter -= 1
        return tmpIdCounter
    }

    function emitOnChange() {
        // console.log(dirtyInstances)
        onChange.emit(dirtyInstances)
        dirtyInstances.clear()
    }


    function importInstances(toImport: Instance[]) {
        for (let img of toImport) {
            const values = getComputedValues(img)
            
            img.urlSmall = SERVER_PREFIX + '/image/small/' + img.sha1
            img.urlMedium = SERVER_PREFIX + '/image/medium/' + img.sha1
            img.urlLarge = SERVER_PREFIX + '/image/large/' + img.sha1
            img.urlRaw = SERVER_PREFIX + '/image/raw/' + img.sha1

            img.containerRatio = computeContainerRatio(img)

            if (instances.value[img.id]) {
                img.properties = Object.assign(instances.value[img.id].properties, img.properties)
            }
            else {
                if (!Array.isArray(sha1Index.value[img.sha1])) {
                    sha1Index.value[img.sha1] = []
                }
                sha1Index.value[img.sha1].push(img)

            }
            for (let i = 0; i < values.length; i++) {
                img.properties[-i - 1] = values[i]
            }
            instances.value[img.id] = img
            dirtyInstances.add(img.id)
        }
    }

    function importProperties(toImport: Property[]) {
        const someNew = toImport.some(p => properties.value[p.id] == undefined)
        for (let property of toImport) {
            if (property.id in properties.value) {
                property.tags = properties.value[property.id].tags
            }
            properties.value[property.id] = property
        }
        if (someNew) {
            const project = useProjectStore()
            const tab = project.getTabManager()
            tab.verifyState()
        }
    }

    function importTags(toImport: Tag[]) {
        console.log(toImport)
        const updated = new Set<number>()
        for (let tag of toImport) {
            if(tag.id == deletedID) continue
            
            if(tags.value[tag.id]) {
                tag.count = tags.value[tag.id].count
                instanceList.value.forEach(i => dirtyInstances.add(i.id))
            } else {
                tag.count = 0
            }
            tag.parents = tag.parents.filter(p => p != 0)
            tags.value[tag.id] = tag
            if (!(tag.propertyId in properties.value)) {
                console.warn('Property ' + tag.propertyId + ' must be loaded before importing tags')
                continue
            }
            if (!properties.value[tag.propertyId].tags) {
                properties.value[tag.propertyId].tags = {}
            }
            properties.value[tag.propertyId].tags[tag.id] = tag
            updated.add(tag.propertyId)

        }
        for (let propId of updated) {
            setTagsChildren(properties.value[propId].tags)
        }
        for (let tag of objValues(tags.value)) {
            tag.allChildren = getTagChildren(tag, tags.value)
            tag.allChildren.splice(tag.allChildren.indexOf(tag.id), 1)
            tag.allParents = getTagParents(tag, tags.value)
        }
        triggerRef(tags)
    }

    async function mergeTags(tagIds: number[]) {
        const commit = await apiMergeTags(tagIds)
        applyCommit(commit)
    }

    function importInstanceValues(instanceValues: InstancePropertyValue[]) {
        for (let v of instanceValues) {
            if (v.value == undefined) continue
            if (isTag(properties.value[v.propertyId].type)) {
                updateTagCount(instances.value[v.instanceId].properties[v.propertyId], v.value)
            }
            instances.value[v.instanceId].properties[v.propertyId] = v.value
            dirtyInstances.add(v.instanceId)
        }
        triggerRef(instances)
    }

    function importImageValues(instanceValues: ImagePropertyValue[]) {
        for (let v of instanceValues) {
            if (v.value == undefined) continue
            if (sha1Index.value[v.sha1] == undefined) continue
            for (let img of sha1Index.value[v.sha1]) {
                if (isTag(properties.value[v.propertyId].type)) {
                    updateTagCount(instances.value[img.id].properties[v.propertyId], v.value)
                }
                instances.value[img.id].properties[v.propertyId] = v.value
                dirtyInstances.add(img.id)
            }
        }
        triggerRef(instances)
    }

    function applyCommit(commit: DbCommit, emit?: boolean) {
        updateFolderCount(commit.instances, commit.emptyInstances)


        if (commit.emptyImageValues) {
            commit.emptyImageValues.forEach(v => {
                sha1Index.value[v.sha1].forEach(i => {
                    if (isTag(properties.value[v.propertyId].type)) {
                        updateTagCount(instances.value[i.id].properties[v.propertyId], [])
                    }
                    delete instances.value[i.id].properties[v.propertyId]
                    dirtyInstances.add(i.id)
                })
            })
            triggerRef(instances)
        }
        if (commit.emptyInstanceValues) {
            commit.emptyInstanceValues.forEach(v => {
                if (isTag(properties.value[v.propertyId].type)) {
                    updateTagCount(instances.value[v.instanceId].properties[v.propertyId], [])
                }
                delete instances.value[v.instanceId].properties[v.propertyId]
                dirtyInstances.add(v.instanceId)
            })
            triggerRef(instances)
        }
        if (commit.emptyTags) {
            commit.emptyTags.forEach(i => {
                tags.value[i].id = deletedID
                tags.value[i].value = deletedName
            })
            triggerRef(tags)
        }
        if (commit.emptyProperties?.length) {
            commit.emptyProperties.forEach(i => {
                properties.value[i].id = deletedID
                properties.value[i].name = deletedName
            })
        }
        if (commit.emptyInstances) {
            commit.emptyInstances.forEach(i => {
                instances.value[i].id = deletedID
                dirtyInstances.add(i)
            })

        }

        if (commit.instances?.length) {
            importInstances(commit.instances)
        }
        if (commit.properties?.length) {
            importProperties(commit.properties)
        }
        if (commit.tags?.length) {
            importTags(commit.tags)
        }
        if (commit.instanceValues?.length) {
            importInstanceValues(commit.instanceValues)
        }
        if (commit.imageValues?.length) {
            importImageValues(commit.imageValues)
        }

        if (commit.history) {
            history.value = commit.history
        }
        emitOnChange()
    }

    function clear() {
        folders.value = {}
        instances.value = {}
        properties.value = {}
        tags.value = {}
        sha1Index.value = {}

        onChange.clear()
        dirtyInstances.clear()

        history.value = { undo: [], redo: [] }
        onUndo.value = 0
    }

    async function sendCommit(commit: DbCommit, undo?: boolean) {
        // console.log('send commit', commit)
        if (undo) {
            commit.undo = true
        }
        const res = await apiCommit(commit)
        applyCommit(res)
        return res
    }

    async function addTag(propertyId: number, tagValue: string, parentIds: number[] = undefined, color = -1): Promise<Tag> {
        const tag: Tag = { id: -1, propertyId: propertyId, value: tagValue, parents: parentIds ?? [], color: color }
        const res = await sendCommit({ tags: [tag] })
        return res.tags[0]
    }

    async function addTagParent(tagId: number, parentId: number) {
        const tag: Tag = Object.assign({}, tags.value[tagId])
        tag.parents.push(parentId)
        const res = await sendCommit({ tags: [tag] })
    }

    async function deleteTagParent(tagId: number, parentId: number) {
        const tag: Tag = Object.assign({}, tags.value[tagId])
        tag.parents = tag.parents.filter(p => p != parentId)
        await sendCommit({ tags: [tag] })
    }

    async function deleteTag(tagId: number, dontAsk?: boolean) {
        if (!dontAsk) {
            const tag = tags.value[tagId]
            let ok = confirm('Delete tag: ' + tag.value + ' (ID: ' + tagId + ') ?')
            if (!ok) return
        }
        sendCommit({ emptyTags: [tagId] })
        // await tabManager.collection.update()

    }

    async function addProperty(name: string, type: PropertyType, mode: PropertyMode) {
        const prop: Property = { id: -1, name: name, type: type, mode: mode }
        const res = await sendCommit({ properties: [prop] })
        return res.properties[0]
    }

    async function setPropertyValue(propertyId: number, images: Instance[] | Instance, value: any, dontEmit?: boolean) {
        if (!Array.isArray(images)) {
            images = [images]
        }
        const mode = properties.value[propertyId].mode
        const instanceValues: InstancePropertyValue[] = []
        const imageValues: ImagePropertyValue[] = []
        if (mode == PropertyMode.id) {
            const values = images.map(i => ({ propertyId: propertyId, instanceId: i.id, value: value } as InstancePropertyValue))
            instanceValues.push(...values)
        }
        if (mode == PropertyMode.sha1) {
            const values = images.map(i => ({ propertyId: propertyId, sha1: i.sha1, value: value } as ImagePropertyValue))
            imageValues.push(...values)
        }
        await sendCommit({ instanceValues: instanceValues, imageValues: imageValues }, true)
    }

    async function setPropertyValues(instanceValues: InstancePropertyValue[], imageValues: ImagePropertyValue[], dontEmit?: boolean) {
        await sendCommit({ instanceValues: instanceValues, imageValues: imageValues }, true)
    }

    async function setTagPropertyValue(propertyId: number, images: Instance[] | Instance, value: any, dontEmit?: boolean) {
        if (!Array.isArray(images)) {
            images = [images]
        }
        const currentValues = images.map(i => ({ value: i.properties[propertyId] ?? [], img: i }))
        if (properties.value[propertyId].mode == PropertyMode.id) {
            const values: InstancePropertyValue[] = currentValues.map(v => ({
                propertyId: propertyId,
                instanceId: v.img.id,
                value: Array.from(new Set([...v.value, ...value]))
            }))
            await sendCommit({ instanceValues: values })
        }
        else {
            const values: ImagePropertyValue[] = currentValues.map(v => ({
                propertyId: propertyId,
                sha1: v.img.sha1,
                value: Array.from(new Set([...v.value, ...value]))
            }))
            await sendCommit({ imageValues: values }, true)
        }
    }

    async function updateTag(tagId: number, value?: any, color?: number) {
        const tag = Object.assign({}, tags.value[tagId])
        if (value) {
            tag.value = value
        }
        if (color != undefined) {
            tag.color = color
        }
        await sendCommit({ tags: [tag] })
    }

    async function addFolder(folder: string) {
        await apiAddFolder(folder)
        const updated = await apiGetFolders()
        const updatedNodes = buildFolderNodes(updated)
        for (let f of objValues(updatedNodes)) {
            if (f.id in folders.value) {
                f.count = folders.value[f.id].count
            }
        }
        folders.value = updatedNodes
    }

    async function updateProperty(propertyId: number, name?: string) {
        const prop = deepCopy(properties.value[propertyId])
        prop.name = name
        sendCommit({ properties: [prop] })
        // TODO: verify
        // updatePropertyOptions()
    }

    async function deleteProperty(propertyId: number) {
        await sendCommit({ emptyProperties: [propertyId] })
        const project = useProjectStore()
        project.getTabManager().verifyState()
        project.getTabManager().collection.update()
    }

    function updateTagCount(oldTags: number[], newTags: number[]) {
        if (oldTags == undefined) {
            oldTags = []
        }
        if (newTags == undefined) {
            newTags = []
        }
        if(!Array.isArray(oldTags)) oldTags = [oldTags]
        if(!Array.isArray(newTags)) newTags = [newTags]
        
        const old = new Set(oldTags)
        const now = new Set(newTags)

        const added = newTags.filter(t => !old.has(t))
        const removed = oldTags.filter(t => !now.has(t))

        added.forEach(t => tags.value[t].count += 1)
        // added.forEach(t => tags.value[t].allParents.forEach((t2) => tags.value[t2].count += 1))
        removed.forEach(t => tags.value[t].count -= 1)
        // removed.forEach(t => tags.value[t].allParents.forEach((t2) => tags.value[t2].count -= 1))

        triggerRef(tags)
    }

    async function undo() {
        if (!history.value.undo.length) return
        const commit = await apiUndo()
        applyCommit(commit)
        onUndo.value++
    }

    async function redo() {
        if (!history.value.redo.length) return
        const commit = await apiRedo()
        applyCommit(commit)
        onUndo.value++
    }

    async function getHistory() {
        const res = await apiGetHistory()
        history.value = res
    }

    function reImportFolder(folderId: number) {
        apiReImportFolder(folderId)
    }


    async function deleteFolder(folderId: number) {
        await apiDeleteFolder(folderId)
        clear()
        await init()
    }

    function updateFolderCount(updatedInstances: Instance[], deletedInstances: number[]) {
        updatedInstances = updatedInstances ?? []
        deletedInstances = deletedInstances ?? []
        for (let instance of updatedInstances) {
            if (instances.value[instance.id] != undefined) continue
            let folder = folders.value[instance.folderId]
            folder.count += 1
            folder = folders.value[folder.parent]
            while (folder) {
                folder.count += 1
                folder = folders.value[folder.parent]
            }
        }
        for (let id of deletedInstances) {
            if (instances.value[id] == undefined) continue
            let folder = folders.value[id]
            folder.count -= 1
            folder = folders.value[folder.parent]
            while (folder) {
                folder.count -= 1
                folder = folders.value[folder.parent]
            }
        }
    }

    return {
        init, getTmpId,
        onChange,
        folders, instances, properties, tags, history,
        folderRoots, sha1Index, instanceList, propertyList, tagList,
        addFolder, reImportFolder, deleteFolder,
        addProperty, deleteProperty, updateProperty, setPropertyValue, setTagPropertyValue, setPropertyValues,
        addTag, deleteTagParent, updateTag, addTagParent, deleteTag, mergeTags,
        applyCommit, sendCommit, undo, redo, onUndo,
        clear
    }

})