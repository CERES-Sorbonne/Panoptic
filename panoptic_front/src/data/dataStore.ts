import { defineStore } from 'pinia'
import { computed, ref, shallowRef, triggerRef } from 'vue'
import {
    CommitHistory, DbCommit, FilePropertyValue, FileValuesArray, Folder, FolderIndex,
    ImagePropertyValue, ImageValuesArray, Instance, InstancePropertyValue, InstanceValuesArray,
    LoadResult, Property, PropertyGroup, PropertyGroupId, PropertyGroupIndex,
    PropertyGroupNode, PropertyGroupOrder, PropertyIndex, PropertyMode, PropertyType,
    Tag, TagIndex, UIDataKeys,
} from './models'
import { buildPropertyGroupOrder, objValues } from './builder'
import {
    apiAddFolder, apiCommitDelete, apiCommitUpsert, apiDeleteFolder,
    apiGetHistory, apiGetInitState, apiGetUIData, apiMergeTags,
    apiPostDeleteEmptyClones, apiReImportFolder, apiRedo, apiSetUIData,
    apiUndo,
} from './apiProjectRoutes'
import { buildFolderNodes, setTagsChildren } from './storeutils'
import {
    EventEmitter, deepCopy, getTagChildren, getTagParents,
    hasPropertyChanges, isTag,
} from '@/utils/utils'
import { useTabStore } from './tabStore'
import { usePanopticStore } from './panopticStore'
import { SERVER_PREFIX } from './apiPanopticRoutes'
import { useColumnStore } from './columnStore'
import { useInstanceStore } from './instanceStore'

export interface ChangePayload {
    propIds:     number[]
    instanceIds: number[]
}

export const deletedID   = -9999999
export const deletedName = 'Deleted'

export const useDataStore = defineStore('dataStore', () => {

    const columnStore   = useColumnStore()
    const instanceStore = useInstanceStore()

    const properties     = shallowRef<PropertyIndex>({})
    const tags           = shallowRef<TagIndex>({})
    const folders        = shallowRef<FolderIndex>({})
    const propertyGroups = shallowRef<PropertyGroupIndex>({})
    const propertyOrder  = shallowRef<PropertyGroupOrder>(buildPropertyGroupOrder())
    const propertyTree   = ref<PropertyGroupNode[]>([])
    const history        = ref<CommitHistory>({ undo: [], redo: [] })
    const baseImgUrl     = shallowRef('')
    const baseUrl        = shallowRef('')

    const dirtyInstances = new Set<number>()
    const dirtyPropIds   = new Set<number>()

    const isLoaded      = ref(false)
    const lastSequence  = ref<number>(0)

    const onUndo        = ref(0)
    const onChange      = new EventEmitter()

    const propertyList       = computed(() => Object.values(properties.value).filter(f => f.id != deletedID))
    const folderRoots        = computed(() => Object.values(folders.value).filter(f => f.parent == null) as Folder[])
    const tagList            = computed(() => objValues(tags.value).filter(t => t.id !== deletedID))
    const propertyGroupsList = computed(() => objValues(propertyGroups.value))

    function _systemKeyIndex(): Record<string, number> {
        const idx: Record<string, number> = {}
        for (const p of Object.values(properties.value)) {
            if (p.systemKey) idx[p.systemKey] = p.id
        }
        return idx
    }

    function importFolders(folderList: Folder[]) {
        const updatedNodes = buildFolderNodes(folderList)
        for (const f of objValues(updatedNodes)) {
            if (f.id in folders.value) f.count = folders.value[f.id].count
        }
        folders.value = updatedNodes
    }

    function importProperties(toImport: any[]) {
        for (const raw of toImport) {
            const property: Property = raw.dtype !== undefined ? { ...raw, type: raw.dtype } : raw
            if (property.id in properties.value) property.tags = properties.value[property.id].tags
            properties.value[property.id] = property
            columnStore.registerProperty(property.id, property.type)
        }
    }

    function _initColumnStore() {
        const sysKeys = _systemKeyIndex()
        const instanceId = sysKeys['id']
        const sha1Id     = sysKeys['sha1']
        const fileIdId   = sysKeys['file_id']
        if (instanceId !== undefined && sha1Id !== undefined && fileIdId !== undefined) {
            if (columnStore.systemProps.INSTANCE_ID === null) {
                columnStore.init(instanceId, sha1Id, fileIdId)
            }
        }
    }

    function importTags(toImport: any[]) {
        const updated = new Set<number>()
        for (const raw of toImport) {
            let tag: Tag = raw.listId !== undefined ? { ...raw, propertyId: raw.listId } : raw
            if (tag.id === deletedID) continue
            tag.count = tags.value[tag.id]?.count ?? 0
            tag.parents = tag.parents.filter(p => p !== 0)
            tags.value[tag.id] = tag
            if (!(tag.propertyId in properties.value)) {
                console.warn('Property ' + tag.propertyId + ' must be loaded before importing tags')
                continue
            }
            if (!properties.value[tag.propertyId].tags) properties.value[tag.propertyId].tags = {}
            properties.value[tag.propertyId].tags[tag.id] = tag
            updated.add(tag.propertyId)
        }
        for (const propId of updated) setTagsChildren(properties.value[propId].tags)
        for (const tag of objValues(tags.value)) {
            tag.allChildren = getTagChildren(tag, tags.value)
            tag.allChildren.splice(tag.allChildren.indexOf(tag.id), 1)
            tag.allParents = getTagParents(tag, tags.value)
        }
    }

    function importPropertyGroups(groups: PropertyGroup[]) {
        for (const group of groups) propertyGroups.value[group.id] = group
    }

    function triggerRefs() {
        triggerRef(properties)
        triggerRef(folders)
        triggerRef(tags)
        triggerRef(propertyGroups)

        if (dirtyInstances.size > 0 || dirtyPropIds.size > 0) {
            onChange.emit(Array.from(dirtyInstances))
            dirtyInstances.clear()
            dirtyPropIds.clear()
        }
    }

    function applyCommit(commit: DbCommit, disableTrigger?: boolean) {
        const props = properties.value

        // --- Execute Removals ---
        if (commit.emptyPropertyGroups) {
            for (const id of commit.emptyPropertyGroups) delete propertyGroups.value[id]
        }
        if (commit.emptyProperties?.length) {
            for (const id of commit.emptyProperties) {
                props[id].id = deletedID
                props[id].name = deletedName
            }
        }
        if (commit.emptyTags) {
            for (const id of commit.emptyTags) {
                tags.value[id].id = deletedID
                tags.value[id].value = deletedName
            }
        }
        if (commit.emptyInstances) {
            for (const id of commit.emptyInstances) {
                if (instanceStore.markDeleted) instanceStore.markDeleted(id)
                columnStore.markSlotDeleted(id)
                dirtyInstances.add(id)
            }
        }

        // --- Execute Imports ---
        if (commit.instances?.length) {
            for (const inst of commit.instances as any[]) {
                instanceStore.instanceData[inst.id] = inst
                dirtyInstances.add(inst.id)
            }
        }
        if (commit.propertyGroups?.length) importPropertyGroups(commit.propertyGroups)
        if (commit.properties?.length)     importProperties(commit.properties)
        if (commit.tags?.length)           importTags(commit.tags)

        if (commit.history) history.value = commit.history

        if (disableTrigger) return
        if (hasPropertyChanges(commit)) computePropertyTree()
        properties.value = props
        triggerRefs()
    }

    function applyMultipleCommits(commits: DbCommit[]) {
        let reloadGroupProp = false
        for (const commit of commits) {
            if (hasPropertyChanges(commit)) reloadGroupProp = true
            applyCommit(commit, true)
        }
        triggerRefs()
        if (reloadGroupProp) computePropertyTree()
    }

    async function applyDelta(delta: LoadResult) {
        const needsPropertyTree = delta.chunk ? hasPropertyChanges(delta.chunk) : false
        if (delta.chunk)           applyCommit(delta.chunk, true)

        await columnStore.updateFromLoadResult(delta)
        instanceStore.updateFromLoadResult(delta)

        // Mark affected instances dirty so onChange fires and collections re-evaluate
        delta.instanceValues?.forEach(chunk => chunk.ids?.forEach(id => dirtyInstances.add(id)))
        delta.imageValues?.forEach(chunk => chunk.sha1s?.forEach(sha1 => columnStore.getInstancesBySha1(sha1).forEach(id => dirtyInstances.add(id))))
        delta.fileValues?.forEach(chunk => chunk.fileIds?.forEach(fid => columnStore.getInstancesByFileId(fid).forEach(id => dirtyInstances.add(id))))

        if (delta.state?.maxSequence > lastSequence.value) lastSequence.value = delta.state.maxSequence
        triggerRefs()
        if (needsPropertyTree) computePropertyTree()
    }

    async function init() {
        const panopticStore = usePanopticStore()
        const projectId = panopticStore.connectionState?.connectedProject
        baseImgUrl.value = `${SERVER_PREFIX}/projects/${projectId}/image/`
        baseUrl.value    = `${SERVER_PREFIX}/projects/${projectId}/`

        const initData = await apiGetInitState()
        if (initData.folders?.length)    importFolders(initData.folders)
        if (initData.properties?.length) importProperties(initData.properties)
        if (initData.tags?.length)       importTags(initData.tags)
        lastSequence.value = initData.sequence ?? 0

        _initColumnStore()
        columnStore.markReady()

        const tabStore = useTabStore()
        await tabStore.init()
        triggerRefs()
        await computePropertyTree()
        isLoaded.value = true

        await getHistory()
    }

    function clear() {
        columnStore.clear()
        instanceStore.clear()

        properties.value     = {}
        tags.value           = {}
        folders.value        = {}
        propertyGroups.value = {}
        propertyOrder.value  = buildPropertyGroupOrder()
        history.value        = { undo: [], redo: [] }

        onChange.clear()
        dirtyInstances.clear()
        dirtyPropIds.clear()
        isLoaded.value     = false
        lastSequence.value = 0
        onUndo.value       = 0
    }

    async function sendCommit(commit: DbCommit): Promise<DbCommit> {
        const hasUpsert = !!(
            commit.properties?.length || commit.tags?.length ||
            commit.instanceValues?.length || commit.imageValues?.length ||
            commit.fileValues?.length || commit.propertyGroups?.length ||
            commit.instances?.length
        )
        const hasDelete = !!(
            commit.emptyInstances?.length || commit.emptyProperties?.length ||
            commit.emptyTags?.length || commit.emptyPropertyGroups?.length ||
            commit.emptyInstanceValues?.length || commit.emptyImageValues?.length ||
            commit.emptyFileValues?.length
        )
        let res: DbCommit = {}
        if (hasUpsert) res = await apiCommitUpsert(commit)
        if (hasDelete) await apiCommitDelete(commit)
        return res
    }

    async function addTag(propertyId: number, tagValue: string, parentIds?: number[], color = -1): Promise<Tag> {
        const tag: Tag = { id: -1, propertyId, value: tagValue, parents: parentIds ?? [], color }
        const res = await sendCommit({ tags: [tag] })
        return res.tags[0]
    }

    async function addTagParent(tagId: number, parentId: number) {
        const tag = Object.assign({}, tags.value[tagId])
        tag.parents.push(parentId)
        await sendCommit({ tags: [tag] })
    }

    async function deleteTagParent(tagId: number, parentId: number) {
        const tag = Object.assign({}, tags.value[tagId])
        tag.parents = tag.parents.filter(p => p !== parentId)
        await sendCommit({ tags: [tag] })
    }

    async function deleteTag(tagId: number, dontAsk?: boolean) {
        if (!dontAsk) {
            const tag = tags.value[tagId]
            if (!confirm('Delete tag: ' + tag.value + ' (ID: ' + tagId + ') ?')) return
        }
        await sendCommit({ emptyTags: [tagId] })
    }

    async function updateTag(tagId: number, value?: any, color?: number) {
        const tag = Object.assign({}, tags.value[tagId])
        if (value !== undefined) tag.value = value
        if (color !== undefined) tag.color = color
        await sendCommit({ tags: [tag] })
    }

    async function mergeTags(tagIds: number[]) {
        const commit = await apiMergeTags(tagIds)
        applyCommit(commit)
    }

    async function addProperty(name: string, type: PropertyType, mode: PropertyMode, group?: number): Promise<Property> {
        const prop: Property = { id: -1, name, type, mode, propertyGroupId: group ?? null }
        const res = await sendCommit({ properties: [prop] })
        return res.properties[0]
    }

    async function updateProperty(propertyId: number, name?: string, group?: number) {
        const prop = deepCopy(properties.value[propertyId])
        if (name !== undefined) prop.name = name
        if (group !== undefined) prop.propertyGroupId = group
        await sendCommit({ properties: [prop] })
        await useTabStore().getMainTab().update()
    }

    async function deleteProperty(propertyId: number) {
        await sendCommit({ emptyProperties: [propertyId] })
        const tabStore = useTabStore()
        const tab = tabStore.getMainTab()
        tab.verifyState()
        await tab.update()
    }

    async function setPropertyValue(propertyId: number, imgs: Instance[] | Instance, value: any) {
        if (!Array.isArray(imgs)) imgs = [imgs]
        const mode = properties.value[propertyId].mode
        const instanceValues: InstancePropertyValue[] = []
        const imageValues:    ImagePropertyValue[]    = []
        const fileValues:     FilePropertyValue[]     = []
        if (mode === PropertyMode.id) {
            instanceValues.push(...imgs.map(i => ({ propertyId, instanceId: i.id, value })))
        }
        if (mode === PropertyMode.sha1) {
            imageValues.push(...imgs.map(i => ({ propertyId, sha1: (i as any).sha1, value })))
        }
        if (mode === PropertyMode.file) {
            const seen = new Set<number>()
            for (const img of imgs) {
                const fileId = (img as any).fileId
                if (fileId != null && !seen.has(fileId)) {
                    seen.add(fileId)
                    fileValues.push({ propertyId, fileId, value })
                }
            }
        }
        await sendCommit({ instanceValues, imageValues, fileValues })
    }

    async function setPropertyValues(instanceValues: InstancePropertyValue[], imageValues: ImagePropertyValue[]) {
        await sendCommit({ instanceValues, imageValues })
    }

    async function setTagPropertyValue(propertyId: number, imgs: Instance[] | Instance, value: any) {
        if (!Array.isArray(imgs)) imgs = [imgs]
        const mode = properties.value[propertyId].mode
        if (mode === PropertyMode.id) {
            const values: InstancePropertyValue[] = imgs.map(i => {
                const slot = columnStore.slotMap.get(i.id)
                const current: number[] = (slot !== undefined ? columnStore.readSlot(propertyId, slot) : null) ?? []
                return { propertyId, instanceId: i.id, value: Array.from(new Set([...current, ...value])) }
            })
            await sendCommit({ instanceValues: values })
        } else {
            const values: ImagePropertyValue[] = imgs.map(i => {
                const slot = columnStore.slotMap.get(i.id)
                const current: number[] = (slot !== undefined ? columnStore.readSlot(propertyId, slot) : null) ?? []
                return { propertyId, sha1: (i as any).sha1, value: Array.from(new Set([...current, ...value])) }
            })
            await sendCommit({ imageValues: values })
        }
    }

    async function addPropertyGroup(name: string) {
        await sendCommit({ propertyGroups: [{ id: -1, name }] })
    }

    async function updatePropertyGroup(id: number, name: string) {
        await sendCommit({ propertyGroups: [{ id, name }] })
    }

    async function deletePropertyGroup(id: number) {
        await sendCommit({ emptyPropertyGroups: [id] })
    }

    async function addFolder(folder: string) {
        await apiAddFolder(folder)
    }

    async function reImportFolder(folderId: number) {
        const updated = await apiReImportFolder(folderId)
        const updatedNodes = buildFolderNodes(updated)
        for (const f of objValues(updatedNodes)) {
            if (f.id in folders.value) f.count = folders.value[f.id].count
        }
        folders.value = updatedNodes
    }

    async function deleteFolder(folderId: number) {
        await apiDeleteFolder(folderId)
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
        history.value = await apiGetHistory()
    }

    async function deleteEmptyClones() {
        const commit = await apiPostDeleteEmptyClones()
        applyCommit(commit)
    }

    async function getPropertyOrderFromStorage() {
        return (await apiGetUIData(UIDataKeys.PROPERTY_ORDER)) as PropertyGroupOrder
    }

    async function savePropertyOrderToStorage() {
        await apiSetUIData(UIDataKeys.PROPERTY_ORDER, propertyOrder.value)
    }

    function mergeOrder<T extends { id: number }>(items: T[], orderDict: Record<number, number>): Record<number, number> {
        const result: Record<number, number> = {}
        const baseOrder = Number.MAX_SAFE_INTEGER / 2
        for (const item of items) {
            result[item.id] = orderDict.hasOwnProperty(item.id)
                ? orderDict[item.id]
                : baseOrder + item.id
        }
        return result
    }

    async function computePropertyTree() {
        let save = await getPropertyOrderFromStorage()
        if (!save) save = buildPropertyGroupOrder()

        const props  = objValues(properties.value).filter(p => p.id !== deletedID)
        const groups = objValues(propertyGroups.value)

        const groupOrder = mergeOrder(groups, save.groups)
        const propsOrder = mergeOrder(props, save.properties)

        const tree: PropertyGroupNode[] = groups.map(g => ({ groupId: g.id, propertyIds: [] }))
        tree.sort((a, b) => groupOrder[a.groupId] - groupOrder[b.groupId])
        tree.push({ groupId: PropertyGroupId.DEFAULT,  propertyIds: [] })
        tree.push({ groupId: PropertyGroupId.COMPUTED, propertyIds: [] })

        const groupToProperties: { [groupId: number]: number[] } = {}
        tree.forEach(n => { groupToProperties[n.groupId] = [] })
        props.forEach(p => {
            if (p.computed) p.propertyGroupId = PropertyGroupId.COMPUTED
            if (p.propertyGroupId == undefined) p.propertyGroupId = PropertyGroupId.DEFAULT
            if (groupToProperties[p.propertyGroupId]) groupToProperties[p.propertyGroupId].push(p.id)
        })
        tree.forEach(n => {
            n.propertyIds = groupToProperties[n.groupId]
            n.propertyIds.sort((a, b) => propsOrder[a] - propsOrder[b])
        })

        propertyTree.value = tree
        propertyOrder.value.groups     = groupOrder
        propertyOrder.value.properties = propsOrder
        triggerRef(propertyOrder)
    }

    async function triggerPropertyTreeChange() {
        const groupOrder: Record<number, number> = {}
        const propOrder:  Record<number, number> = {}
        for (let i = 0; i < propertyTree.value.length; i++) {
            const val = propertyTree.value[i]
            if (val.groupId >= 0) groupOrder[val.groupId] = i
        }
        let i = 0
        for (const node of propertyTree.value) {
            for (const prop of node.propertyIds) { i++; propOrder[prop] = i }
        }
        propertyOrder.value.properties = propOrder
        propertyOrder.value.groups     = groupOrder
        await savePropertyOrderToStorage()
        triggerRef(properties)
    }

    function getSysField(instanceId: number, key: string): any {
        const propId = _systemKeyIndex()[key]
        if (propId === undefined) return undefined
        const slot = columnStore.slotMap.get(instanceId)
        if (slot === undefined) return undefined
        return columnStore.readSlot(propId, slot)
    }

    function getSysId(key: string) {
        const propId = _systemKeyIndex()[key]
        return propId
    }

    function getProperty(key: string) {
        return properties.value[getSysId(key)]
    }

    return {
        init, clear, isLoaded, lastSequence, applyDelta, applyCommit,
        applyMultipleCommits, sendCommit,

        folders, instances: instanceStore.instanceData, properties, tags, history,
        propertyGroups, propertyGroupsList, propertyTree, propertyOrder,

        folderRoots, tagList,

        onChange,
        get onSelectionChange() { return columnStore.onSelectionChange },

        onUndo, baseImgUrl, baseUrl,
        addFolder, reImportFolder, deleteFolder,
        addProperty, updateProperty, deleteProperty,
        setPropertyValue, setTagPropertyValue, setPropertyValues,
        addTag, addTagParent, deleteTagParent, updateTag, deleteTag, mergeTags,
        addPropertyGroup, updatePropertyGroup, deletePropertyGroup,
        deleteEmptyClones, undo, redo,
        triggerPropertyTreeChange, computePropertyTree,
        importFolders,
        propertyList, getProperty,

        getSysField, getSysId
    }
})