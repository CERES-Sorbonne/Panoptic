import { defineStore } from "pinia";
import { computed, ref, shallowRef, triggerRef } from "vue";
import { CommitHistory, DbCommit, Folder, FolderIndex, ImagePropertyValue, Instance, InstanceIndex, InstancePropertyValue, LoadState, Property, PropertyGroup, PropertyGroupId, PropertyGroupIndex, PropertyGroupNode, PropertyGroupOrder, PropertyIndex, PropertyMode, PropertyType, Sha1ToInstances, Tag, TagIndex, UIDataKeys, VectorStats, VectorType } from "./models";
import { buildPropertyGroupOrder, objValues } from "./builder";
import { apiAddFolder, apiCommit, apiDeleteFolder, apiDeleteVectorType, apiGetFolders, apiGetHistory, apiGetUIData, apiGetVectorStats, apiGetVectorTypes, apiMergeTags, apiPostDeleteEmptyClones, apiReImportFolder, apiRedo, apiSetUIData, apiStreamLoadState, apiUndo } from "./apiProjectRoutes";
import { buildFolderNodes, computeContainerRatio, setTagsChildren } from "./storeutils";
import { EventEmitter, deepCopy, getComputedValues, getTagChildren, getTagParents, hasPropertyChanges, isFinished, isTag } from "@/utils/utils";
import { useTabStore } from "./tabStore";
import { usePanopticStore } from "./panopticStore";
import { SERVER_PREFIX } from "./apiPanopticRoutes";

export const deletedID = -999999999
const deletedName = 'Deleted'

export const useDataStore = defineStore('dataStore', () => {

    const onChange = new EventEmitter()
    const dirtyInstances = new Set()
    let tmpIdCounter = -100

    const folders = shallowRef<FolderIndex>({})
    const instances = shallowRef<InstanceIndex>({})
    const properties = shallowRef<PropertyIndex>({})
    const propertyOrder = shallowRef<PropertyGroupOrder>(buildPropertyGroupOrder())
    const propertyTree = ref<PropertyGroupNode[]>([])
    const propertyGroups = shallowRef<PropertyGroupIndex>({})
    const tags = shallowRef<TagIndex>({})
    const vectorTypes = ref<VectorType[]>([])
    const vectorStats = ref<VectorStats>({ count: {}, sha1Count: 0 })

    const history = ref<CommitHistory>({ undo: [], redo: [] })
    const sha1Index = shallowRef<Sha1ToInstances>({})

    const loadState = ref<LoadState>(null)

    const onUndo = ref(0)

    // =======================
    // =======Computed=======
    // =======================
    const isLoaded = ref(false)
    const folderRoots = computed(() => {
        return Object.values(folders.value).filter(f => f.parent == null) as Folder[]
    })
    const instanceList = computed(() => objValues(instances.value).filter(i => i.id != deletedID))
    const propertyList = computed(() => objValues(properties.value).sort((a, b) => propertyOrder.value.properties[a.id] - propertyOrder.value.properties[b.id]))
    const tagList = computed(() => objValues(tags.value).filter(t => t.id != deletedID))
    const propertyGroupsList = computed(() => objValues(propertyGroups.value))


    // =======================
    // =======Functions=======
    // =======================
    async function init() {
        let dbFolders = await apiGetFolders()
        importFolders(dbFolders)
        // console.time('Request')
        // // let dbState = await apiGetDbState()
        // console.timeEnd('Request')


        const vecTypes = await apiGetVectorTypes()
        importVectorTypes(vecTypes)

        apiStreamLoadState(async (v) => {
            applyCommit(v.chunk, true)
            loadState.value = v.state

            if (isFinished(v.state)) {
                const tabStore = useTabStore()
                await tabStore.init()
                triggerRefs()
                await computePropertyTree()

                isLoaded.value = true
            }
        })

        // console.time('commit')
        // // applyCommit(dbState)
        // console.timeEnd('commit')

        await getHistory()
    }

    function getTmpId() {
        tmpIdCounter -= 1
        return tmpIdCounter
    }

    function emitOnChange() {
        onChange.emit(dirtyInstances)
        dirtyInstances.clear()
    }

    function importVectorTypes(types: VectorType[]) {
        vectorTypes.value = types
    }


    function importInstances(toImport: Instance[]) {
        const panopticStore = usePanopticStore()
        const projectId = panopticStore.clientState.connectedProject

        for (let img of toImport) {
            const values = getComputedValues(img)

            img.urlSmall = `${SERVER_PREFIX}/projects/${projectId}/image/small/${img.sha1}`
            img.urlMedium = `${SERVER_PREFIX}/projects/${projectId}/image/medium/${img.sha1}`
            img.urlLarge = `${SERVER_PREFIX}/projects/${projectId}/image/large/${img.sha1}`
            img.urlRaw = `${SERVER_PREFIX}/projects/${projectId}/image/raw/${img.sha1}`

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
            // const tabStore = useTabStore()
            // const tab = tabStore.getTab(tabStore.mainTab)
            // tab.verifyState()
        }
    }

    function importTags(toImport: Tag[]) {
        const updated = new Set<number>()
        for (let tag of toImport) {
            if (tag.id == deletedID) continue

            if (tags.value[tag.id]) {
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
    }

    function importPropertyGroups(groups: PropertyGroup[]) {
        for (let group of groups) {
            propertyGroups.value[group.id] = group
        }
    }

    function applyMultipleCommits(commits: DbCommit[]) {
        let reloadGroupProp = false
        for(let commit of commits) {
            if(hasPropertyChanges(commit)) {
                reloadGroupProp = true
            }
            applyCommit(commit, true)
        }
        triggerRefs()
        if(reloadGroupProp) {
            computePropertyTree()
        }
    }

    function applyCommit(commit: DbCommit, disableTrigger?: boolean) {
        updateFolderCount(commit.instances, commit.emptyInstances)
        const props = properties.value

        if (commit.emptyImageValues) {
            commit.emptyImageValues.forEach(v => {
                sha1Index.value[v.sha1].forEach(i => {
                    if (props[v.propertyId] && isTag(props[v.propertyId].type)) {
                        updateTagCount(instances.value[i.id].properties[v.propertyId], [])
                    }
                    if (instances.value[i.id]) {
                        delete instances.value[i.id].properties[v.propertyId]
                        dirtyInstances.add(i.id)
                    }
                })
            })

        }
        if (commit.emptyInstanceValues) {
            commit.emptyInstanceValues.forEach(v => {
                if (props[v.propertyId] && isTag(props[v.propertyId].type)) {
                    updateTagCount(instances.value[v.instanceId].properties[v.propertyId], [])
                }
                if (instances.value[v.instanceId]) {
                    delete instances.value[v.instanceId].properties[v.propertyId]
                    dirtyInstances.add(v.instanceId)
                }

            })

        }
        if (commit.emptyTags) {
            commit.emptyTags.forEach(i => {
                tags.value[i].id = deletedID
                tags.value[i].value = deletedName
            })

        }
        if (commit.emptyPropertyGroups) {
            for (let id of commit.emptyPropertyGroups) {
                delete propertyGroups.value[id]
            }
        }
        if (commit.emptyProperties?.length) {
            commit.emptyProperties.forEach(i => {
                props[i].id = deletedID
                props[i].name = deletedName
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
        if (commit.propertyGroups?.length) {
            importPropertyGroups(commit.propertyGroups)
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

        if (!disableTrigger && hasPropertyChanges(commit)) {
            computePropertyTree()
        }

        if (disableTrigger) return
        console.log('trigger refss')

        properties.value = props
        triggerRefs()
    }

    function clear() {
        folders.value = {}
        instances.value = {}
        properties.value = {}
        propertyOrder.value = buildPropertyGroupOrder()
        tags.value = {}
        sha1Index.value = {}
        vectorTypes.value = []
        vectorStats.value = { count: {}, sha1Count: 0 }

        onChange.clear()
        dirtyInstances.clear()

        history.value = { undo: [], redo: [] }
        onUndo.value = 0
        isLoaded.value = false
    }

    async function sendCommit(commit: DbCommit, undo?: boolean, disableTrigger?: boolean) {
        // console.log('send commit', commit)
        // TODO: verify. disable trigger need as is should now be handled by socket route this function has now no control over this
        if (undo) {
            commit.undo = true
        }
        const res = await apiCommit(commit)
        // applyCommit(res, disableTrigger)
        return res
    }

    function triggerRefs() {
        triggerRef(properties)
        triggerRef(folders)
        triggerRef(instances)
        triggerRef(sha1Index)
        triggerRef(tags)
        triggerRef(propertyGroups)
        emitOnChange()
    }

    async function addTag(propertyId: number, tagValue: string, parentIds: number[] = undefined, color = -1): Promise<Tag> {
        const tag: Tag = { id: -1, propertyId: propertyId, value: tagValue, parents: parentIds ?? [], color: color }
        const res = await sendCommit({ tags: [tag] }, true, true)
        triggerRef(tags)
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

    async function setTagPropertyValue(propertyId: number, images: Instance[] | Instance, value: any) {
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
            await sendCommit({ imageValues: values })
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
        // const updated = await apiGetFolders()
        // const updatedNodes = buildFolderNodes(updated)
        // for (let f of objValues(updatedNodes)) {
        //     if (f.id in folders.value) {
        //         f.count = folders.value[f.id].count
        //     }
        // }
        // folders.value = updatedNodes
    }

    async function importFolders(folderList: Folder[]) {
        const updatedNodes = buildFolderNodes(folderList)
        for (let f of objValues(updatedNodes)) {
            if (f.id in folders.value) {
                f.count = folders.value[f.id].count
            }
        }
        folders.value = updatedNodes
    }

    async function updateProperty(propertyId: number, name?: string, group?: number) {
        const prop = deepCopy(properties.value[propertyId])
        prop.name = name
        if (group !== undefined) {
            prop.propertyGroupId = group
        }
        sendCommit({ properties: [prop] })
        useTabStore().getMainTab().update()
    }

    async function deleteProperty(propertyId: number) {
        await sendCommit({ emptyProperties: [propertyId] })
        const tabStore = useTabStore()
        const tab = tabStore.getMainTab()
        tab.verifyState()
        tab.update()
    }

    function updateTagCount(oldTags: number[], newTags: number[]) {
        if (oldTags == undefined) {
            oldTags = []
        }
        if (newTags == undefined) {
            newTags = []
        }
        if (!Array.isArray(oldTags)) oldTags = [oldTags]
        if (!Array.isArray(newTags)) newTags = [newTags]

        const old = new Set(oldTags)
        const now = new Set(newTags)

        const added = newTags.filter(t => !old.has(t))
        const removed = oldTags.filter(t => !now.has(t))
        added.forEach(t => tags.value[t].count += 1)
        // added.forEach(t => tags.value[t].allParents.forEach((t2) => tags.value[t2].count += 1))
        removed.forEach(t => tags.value[t].count -= 1)
        // removed.forEach(t => tags.value[t].allParents.forEach((t2) => tags.value[t2].count -= 1))
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

    async function reImportFolder(folderId: number) {
        const updated = await apiReImportFolder(folderId)
        const updatedNodes = buildFolderNodes(updated)
        for (let f of objValues(updatedNodes)) {
            if (f.id in folders.value) {
                f.count = folders.value[f.id].count
            }
        }
        folders.value = updatedNodes
    }

    async function deleteFolder(folderId: number) {
        await apiDeleteFolder(folderId)
        // location.reload()
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
            const instance = instances.value[id]
            let folder = folders.value[instance.folderId]
            folder.count -= 1
            folder = folders.value[folder.parent]
            while (folder) {
                folder.count -= 1
                folder = folders.value[folder.parent]
            }
        }
    }

    async function addPropertyGroup(name: string) {
        await sendCommit({ propertyGroups: [{ id: -1, name }] }, false, false)
    }

    async function updatePropertyGroup(id: number, name: string) {
        await sendCommit({ propertyGroups: [{ id: id, name: name }] }, false, false)
    }

    async function deletePropertyGroup(id: number) {
        await sendCommit({ emptyPropertyGroups: [id] })
    }

    async function deleteEmptyClones() {
        const commit = await apiPostDeleteEmptyClones()
        applyCommit(commit)
    }

    async function getPropertyOrderFromStorage() {
        const res = await apiGetUIData(UIDataKeys.PROPERTY_ORDER)
        return res as PropertyGroupOrder
    }

    async function savePropertyOrderToStorage() {
        await apiSetUIData(UIDataKeys.PROPERTY_ORDER, propertyOrder.value)
    }

    function mergeOrder<T extends { id: number }>(items: T[], orderDict: Record<number, number>): Record<number, number> {
        const result: Record<number, number> = {};
        const baseOrder = Number.MAX_SAFE_INTEGER / 2;

        for (const item of items) {
            if (orderDict.hasOwnProperty(item.id)) {
                result[item.id] = orderDict[item.id];
            } else {
                result[item.id] = baseOrder + item.id;
            }
        }
        return result;
    }

    async function computePropertyTree() {
        console.log('compute prop tree')
        let save = await getPropertyOrderFromStorage()
        if (!save) {
            save = buildPropertyGroupOrder()
        }

        const props = objValues(properties.value).filter(p => p.id != deletedID)
        const groups = objValues(propertyGroups.value)

        const groupOrder = mergeOrder(groups, save.groups)
        const propsOrder = mergeOrder(props, save.properties)

        const tree: PropertyGroupNode[] = groups.map(g => ({ groupId: g.id, propertyIds: [] }))
        tree.sort((a, b) => groupOrder[a.groupId] - groupOrder[b.groupId])
        tree.push({ groupId: PropertyGroupId.DEFAULT, propertyIds: [] })
        tree.push({ groupId: PropertyGroupId.COMPUTED, propertyIds: [] })

        const groupToProperties: { [groupId: number]: number[] } = {}
        tree.forEach(n => {
            groupToProperties[n.groupId] = []
        })
        props.forEach(p => {
            if (p.computed) {
                p.propertyGroupId = PropertyGroupId.COMPUTED
            }
            if (p.propertyGroupId == undefined) {
                p.propertyGroupId = PropertyGroupId.DEFAULT
            }
            if (groupToProperties[p.propertyGroupId]) {
                groupToProperties[p.propertyGroupId].push(p.id)
            }

        })

        tree.forEach(n => {
            n.propertyIds = groupToProperties[n.groupId]
            n.propertyIds.sort((a, b) => propsOrder[a] - propsOrder[b])
        })

        propertyTree.value = tree
        propertyOrder.value.groups = groupOrder
        propertyOrder.value.properties = propsOrder

    }

    async function triggerPropertyTreeChange() {
        const groupOrder = {}
        const propOrder = {}

        for (let i = 0; i < propertyTree.value.length; i++) {
            const val = propertyTree.value[i]
            if (val.groupId >= 0) {
                groupOrder[val.groupId] = i
            }
        }

        let i = 0
        for (let node of propertyTree.value) {
            for (let prop of node.propertyIds) {
                i += 1
                propOrder[prop] = i
            }
        }

        propertyOrder.value.properties = propOrder
        propertyOrder.value.groups = groupOrder

        await savePropertyOrderToStorage()
        triggerRef(properties)
    }

    async function updateVectorTypes() {
        vectorTypes.value = await apiGetVectorTypes()
    }

    async function deleteVectorType(id: number) {
        await apiDeleteVectorType(id)
        await updateVectorTypes()
    }

    async function updateVectorStats() {
        vectorStats.value = await apiGetVectorStats()
    }

    return {
        init, getTmpId, loadState, isLoaded,
        onChange,
        folders, instances, properties, tags, history, vectorTypes, vectorStats,
        folderRoots, sha1Index, instanceList, propertyList, tagList,
        propertyTree, triggerPropertyTreeChange,
        addFolder, reImportFolder, deleteFolder,
        addProperty, deleteProperty, updateProperty, setPropertyValue, setTagPropertyValue, setPropertyValues,
        addTag, deleteTagParent, updateTag, addTagParent, deleteTag, mergeTags, deleteEmptyClones,
        applyCommit, sendCommit, undo, redo, onUndo,
        addPropertyGroup, propertyGroups, propertyGroupsList, updatePropertyGroup, deletePropertyGroup,
        updateVectorTypes, deleteVectorType, updateVectorStats,
        clear,
        importFolders, importVectorTypes, applyMultipleCommits
    }

})