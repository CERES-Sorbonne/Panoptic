import { defineStore } from "pinia";
import { computed, ref, shallowRef, triggerRef } from "vue";
import { CommitHistory, DbCommit, Folder, FolderIndex, ImagePropertyValue, Instance, InstanceIndex, InstancePropertyValue, Property, PropertyIndex, PropertyMode, PropertyType, Sha1ToInstances, TabState, Tag, TagIndex } from "./models";
import { objValues } from "./builder";
import { SERVER_PREFIX, apiAddFolder, apiCommit, apiDeleteFolder, apiGetDbState, apiGetFolders, apiGetHistory, apiReImportFolder, apiRedo, apiUndo } from "./api";
import { buildFolderNodes, computeContainerRatio, setTagsChildren } from "./storeutils";
import { deepCopy, getComputedValues, getTagChildren, getTagParents, isTag } from "@/utils/utils";

const deletedID = -999999999
const deletedName = 'Deleted'

export const useDataStore = defineStore('dataStore', () => {

    const folders = ref<FolderIndex>({})
    const instances = shallowRef<InstanceIndex>({})
    const properties = ref<PropertyIndex>({})
    const tags = shallowRef<TagIndex>({})

    const history = ref<CommitHistory>({undo: [], redo: []})
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


    // =======================
    // =======Functions=======
    // =======================
    async function init() {
        clear()
        let dbFolders = await apiGetFolders()
        folders.value = buildFolderNodes(dbFolders)
        console.time('Request')
        let dbState = await apiGetDbState()
        console.timeEnd('Request')

        
        console.time('commit')
        applyCommit(dbState)
        console.timeEnd('commit')

        await getHistory()
    }


    function importInstances(toImport: Instance[]) {
        for (let img of toImport) {
            const values = getComputedValues(img)
            img.fullUrl = SERVER_PREFIX + '/images/' + img.url
            img.url = SERVER_PREFIX + '/small/images/' + img.sha1 + '.jpeg'
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
        }
    }

    function importProperties(toImport: Property[]) {
        for (let property of toImport) {
            if (property.id in properties.value) {
                property.tags = properties.value[property.id].tags
            }
            properties.value[property.id] = property
        }
    }

    function importTags(toImport: Tag[]) {
        const updated = new Set<number>()
        for (let tag of toImport) {
            tag.count = 0
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
        for (let tag of toImport) {
            tag.allChildren = getTagChildren(tag, tags.value)
            tag.allChildren.splice(tag.allChildren.indexOf(tag.id), 1)
            tag.allParents = getTagParents(tag, tags.value)
        }
    }

    function importInstanceValues(instanceValues: InstancePropertyValue[]) {
        for (let v of instanceValues) {
            if (v.value == undefined) continue
            if (isTag(properties.value[v.propertyId].type)) {
                updateTagCount(instances.value[v.instanceId].properties[v.propertyId], v.value)
            }
            instances.value[v.instanceId].properties[v.propertyId] = v.value
        }
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
            }
        }
    }

    function applyCommit(commit: DbCommit) {
        updateFolderCount(commit.instances, commit.emptyInstances)


        if (commit.emptyImageValues) {
            commit.emptyImageValues.forEach(v => {
                sha1Index.value[v.sha1].forEach(i => {
                    if (isTag(properties.value[v.propertyId].type)) {
                        updateTagCount(instances.value[i.id].properties[v.propertyId], [])
                    }
                    delete instances.value[i.id].properties[v.propertyId]
                })
            })
        }
        if (commit.emptyInstanceValues) {
            commit.emptyInstanceValues.forEach(v => {
                if (isTag(properties.value[v.propertyId].type)) {
                    updateTagCount(instances.value[v.instanceId].properties[v.propertyId], [])
                }
                delete instances.value[v.instanceId].properties[v.propertyId]
            })
        }
        if (commit.emptyTags) {
            commit.emptyTags.forEach(i => {
                tags.value[i].id = deletedID
                tags.value[i].value = deletedName
            })
        }
        if (commit.emptyProperties?.length) {
            commit.emptyProperties.forEach(i => {
                properties.value[i].id = deletedID
                properties.value[i].name = deletedName
            })
        }
        if (commit.emptyInstances) {
            // TODO: ??
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
        triggerRef(instances)

        if (commit.history) {
            history.value = commit.history
        }
    }

    function clear() {
        instances.value = {}
        properties.value = {}
        tags.value = {}
        sha1Index.value = {}
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
            let ok = confirm('Delete tag: ' + tagId)
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
        if (color) {
            tag.color = color
        }
        await sendCommit({ tags: [tag] })
    }

    async function addFolder(folder: string) {
        await apiAddFolder(folder)
        init()
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
        delete properties.value[propertyId]

        // TODO: verify
        // Object.values(data.tabs).forEach((t: TabState) => {
        //     Object.keys(t.visibleProperties).map(Number).forEach(k => {
        //         if (properties.value[k] == undefined) {
        //             delete t.visibleProperties[k]
        //         }
        //     })
        // })
        // verifyData()
        // tabManager.collection.update()
        // rerender()
    }

    function updateTagCount(oldTags: number[], newTags: number[]) {
        if (oldTags == undefined) {
            oldTags = []
        }
        const old = new Set(oldTags)
        const now = new Set(newTags)

        const added = newTags.filter(t => !old.has(t))
        const removed = oldTags.filter(t => !now.has(t))

        added.forEach(t => tags.value[t].count += 1)
        removed.forEach(t => tags.value[t].count -= 1)

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

        for(let instance of updatedInstances) {
            if(instances.value[instance.id] != undefined) continue
            folders.value[instance.folderId].count += 1
        }
        for(let id of deletedInstances) {
            if(instances.value[id] == undefined) continue
            folders.value[id].count -= 1
        }
    }

    return {
        init,
        folders, instances, properties, tags, history,
        folderRoots, sha1Index, instanceList, propertyList,
        addFolder, reImportFolder, deleteFolder,
        addProperty, deleteProperty, updateProperty, setPropertyValue, setTagPropertyValue, setPropertyValues,
        addTag, deleteTagParent, updateTag, addTagParent, deleteTag,
        applyCommit, sendCommit, undo, redo,
        clear
    }

})