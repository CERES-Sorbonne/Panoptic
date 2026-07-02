import { defineStore } from 'pinia'
import { computed, ref, shallowRef, triggerRef } from 'vue'
import {
    CommitHistory, DbCommit, FilePropertyValue, FileSource, FileSourceIndex, FileValuesArray, Folder, FolderNode, FolderIndex,
    ImagePropertyValue, ImageValuesArray, Instance, InstancePropertyValue, InstanceValuesArray,
    LoadResult, Property, PropertyGroup, PropertyGroupId, PropertyGroupIndex,
    PropertyGroupNode, PropertyGroupOrder, PropertyIndex, PropertyMode, PropertyType,
    RootNode, SourceNode, Tag, TagIndex, UIDataKeys,
} from './models'
import { buildPropertyGroupOrder, objValues } from './builder'
import {
    apiAddFolder, apiImportIiif, apiAllocatePropertyGroups, apiCommitDelete, apiCommitUpsert, apiDeleteFolder, apiDeleteFileSource,
    apiGetFolders, apiGetFileSources, apiGetFolderCounts, apiGetHistory, apiGetInitState, apiGetTagCounts, apiGetUIData, apiMergeTags,
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
    const fileSources   = shallowRef<FileSourceIndex>({})
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

    const rootNodes = computed<RootNode[]>(() => {
        const result: RootNode[] = []

        // Add file sources with their top-level folders
        for (const source of Object.values(fileSources.value)) {
            const childFolders = Object.values(folders.value).filter(
                f => f.sourceId === source.id && f.parent == null
            ) as Folder[]
            result.push({
                id: source.id,
                name: source.name || `Source ${source.id}`,
                type: 'file_source',
                children: childFolders,
            })
        }

        // Add top-level folders not belonging to any file source
        for (const folder of Object.values(folders.value)) {
            if (folder.parent == null && !(folder.sourceId != null && fileSources.value[folder.sourceId!])) {
                result.push({
                    id: folder.id,
                    name: folder.name || `Folder ${folder.id}`,
                    type: 'folder',
                    children: (folder.children || []) as Folder[],
                })
            }
        }

        return result
    })

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

    function importFileSources(sourceList: FileSource[]) {
        const index: FileSourceIndex = {}
        for (const fs of sourceList) index[fs.id] = fs
        fileSources.value = index
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
        // Removed property values (e.g. a commit that wrote a value was disabled): clear the
        // affected (property, instance) cells so the grid drops the stale value instead of
        // waiting for a full reload.
        const clearValueCell = (propId: number, instanceId: number) => {
            console.log('[delta] clearValueCell', { propId, instanceId, knownInstance: !!instanceStore.instanceData[instanceId] })
            columnStore.clearCell(propId, instanceId)
            const inst = instanceStore.instanceData[instanceId]
            if (inst?.properties) delete inst.properties[propId]
            if (inst?.propertyStatus) delete inst.propertyStatus[propId]
            dirtyInstances.add(instanceId)
        }
        if (commit.emptyInstanceValues?.length) {
            for (const v of commit.emptyInstanceValues) clearValueCell(v.propertyId, v.instanceId)
        }
        if (commit.emptyImageValues?.length) {
            for (const v of commit.emptyImageValues) {
                const ids = columnStore.getInstancesBySha1(v.sha1)
                console.log('[delta] emptyImageValue -> instances', { propId: v.propertyId, sha1: v.sha1, ids })
                for (const id of ids) clearValueCell(v.propertyId, id)
            }
        }
        if (commit.emptyFileValues?.length) {
            for (const v of commit.emptyFileValues) {
                const ids = columnStore.getInstancesByFileId(v.fileId)
                console.log('[delta] emptyFileValue -> instances', { propId: v.propertyId, fileId: v.fileId, ids })
                for (const id of ids) clearValueCell(v.propertyId, id)
            }
        }

        // --- Execute Imports ---
        if (commit.instances?.length) {
            const newIds: number[] = [], newSha1s: string[] = [], newFileIds: number[] = []
            for (const inst of commit.instances as any[]) {
                // Instances pushed via commit only carry id/sha1/fileId — merge onto the
                // existing entry (if any) so properties/propertyStatus survive, and give a
                // brand-new entry the full InstanceEntry shape so later property writes
                // don't hit an undefined `properties`/`propertyStatus`.
                const existing = instanceStore.instanceData[inst.id]
                if (existing) {
                    Object.assign(existing, inst)
                } else {
                    instanceStore.instanceData[inst.id] = {
                        properties: {},
                        propertyStatus: {},
                        selected: false,
                        imageUrl: `${baseImgUrl.value}by_size/${inst.sha1}`,
                        ...inst,
                    }
                }
                dirtyInstances.add(inst.id)
                newIds.push(inst.id); newSha1s.push(inst.sha1); newFileIds.push(inst.fileId)
            }
            // Register new instances as column-store slots so the grid/grouping sees them.
            columnStore.addInstances(newIds, newSha1s, newFileIds)
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
        const c = delta.chunk
        console.log('[delta] received', {
            maxSequence: delta.state?.maxSequence,
            lastSequence: lastSequence.value,
            hasChunk: !!c,
            chunk: c ? {
                properties: c.properties?.length ?? 0,
                tags: c.tags?.length ?? 0,
                instances: c.instances?.length ?? 0,
                emptyProperties: c.emptyProperties?.length ?? 0,
                emptyTags: c.emptyTags?.length ?? 0,
                emptyInstances: c.emptyInstances?.length ?? 0,
                emptyInstanceValues: c.emptyInstanceValues?.length ?? 0,
                emptyImageValues: c.emptyImageValues?.length ?? 0,
                emptyFileValues: c.emptyFileValues?.length ?? 0,
            } : null,
            instanceValueChunks: delta.instanceValues?.map(v => ({ propertyId: v.propertyId, n: (v as any).ids?.length ?? 0 })),
            imageValueChunks: delta.imageValues?.map(v => ({ propertyId: v.propertyId, n: v.sha1s?.length ?? 0 })),
            fileValueChunks: delta.fileValues?.map(v => ({ propertyId: v.propertyId, n: v.fileIds?.length ?? 0 })),
        })
        if (c?.emptyInstanceValues?.length) console.log('[delta] emptyInstanceValues', JSON.parse(JSON.stringify(c.emptyInstanceValues)))
        if (c?.emptyImageValues?.length) console.log('[delta] emptyImageValues', JSON.parse(JSON.stringify(c.emptyImageValues)))
        if (c?.emptyFileValues?.length) console.log('[delta] emptyFileValues', JSON.parse(JSON.stringify(c.emptyFileValues)))

        const needsPropertyTree = delta.chunk ? hasPropertyChanges(delta.chunk) : false
        if (delta.chunk)           applyCommit(delta.chunk, true)

        await columnStore.updateFromLoadResult(delta)
        instanceStore.updateFromLoadResult(delta)

        // Mark affected instances dirty so onChange fires and collections re-evaluate
        delta.instanceValues?.forEach(chunk => chunk.ids?.forEach(id => dirtyInstances.add(id)))
        delta.imageValues?.forEach(chunk => chunk.sha1s?.forEach(sha1 => columnStore.getInstancesBySha1(sha1).forEach(id => dirtyInstances.add(id))))
        delta.fileValues?.forEach(chunk => chunk.fileIds?.forEach(fid => columnStore.getInstancesByFileId(fid).forEach(id => dirtyInstances.add(id))))

        // When tags are modified (e.g. reparented), their allChildren sets may
        // have changed, affecting any instance whose tag filter value includes
        // the affected tags. Re-filter all non-deleted instances.
        if (c?.tags?.length) {
            const count = columnStore.slotCount()
            const delMask = columnStore.deletedMask()
            const ids = columnStore.instanceIds()
            for (let s = 0; s < count; s++) {
                if (!delMask[s]) dirtyInstances.add(ids[s])
            }
        }

        if (delta.state?.maxSequence > lastSequence.value) lastSequence.value = delta.state.maxSequence
        triggerRefs()
        if (needsPropertyTree) computePropertyTree()

        // Re-fetch all tag counts if any tag property had value changes
        const allChunks = (delta.instanceValues ?? []).concat(delta.imageValues ?? [])
        for (let i = 0; i < allChunks.length; i++) {
            if (isTag(properties.value[allChunks[i].propertyId]?.type)) {
                fetchTagCounts()
                break
            }
        }
    }

    function applyTagCounts(counts: { tag_id: number; instance_count: number; sha1_count: number }[]) {
        for (const { tag_id, instance_count, sha1_count } of counts) {
            if (tags.value[tag_id]) tags.value[tag_id].count = instance_count + sha1_count
        }
        triggerRef(tags)
    }

    function applyFolderCounts(counts: Record<string, number>) {
        for (const [id, count] of Object.entries(counts)) {
            const folderId = Number(id)
            if (folders.value[folderId]) folders.value[folderId].count = count
        }
        triggerRef(folders)
    }

    async function fetchTagCounts(propertyId?: number) {
        try {
            const counts = await apiGetTagCounts(propertyId)
            applyTagCounts(counts)
        } catch {}
    }

    async function fetchFolderCounts() {
        try {
            const counts = await apiGetFolderCounts()
            applyFolderCounts(counts)
        } catch {}
    }

    // Re-fetch the full folder tree (to surface newly imported folders) and refresh counts.
    // Folders and file sources are structural and not delta-synced, so this is triggered
    // around imports.
    async function reloadFolders() {
        try {
            const folderList = await apiGetFolders()
            importFolders(folderList)
            await fetchFolderCounts()
        } catch {}
        try {
            const sourceList = await apiGetFileSources()
            importFileSources(sourceList)
        } catch {}
    }

    async function init() {
        const panopticStore = usePanopticStore()
        const projectId = panopticStore.connectionState?.connectedProject
        baseImgUrl.value = `${SERVER_PREFIX}/projects/${projectId}/image/`
        baseUrl.value    = `${SERVER_PREFIX}/projects/${projectId}/`

        const initData = await apiGetInitState()
        if (initData.fileSources?.length) importFileSources(initData.fileSources)
        if (initData.folders?.length)        importFolders(initData.folders)
        if (initData.properties?.length)     importProperties(initData.properties)
        if (initData.propertyGroups?.length) importPropertyGroups(initData.propertyGroups)
        if (initData.tags?.length)           importTags(initData.tags)
        lastSequence.value = initData.sequence ?? 0

        _initColumnStore()

        const tabStore = useTabStore()
        await tabStore.init()
        triggerRefs()
        await computePropertyTree()
        isLoaded.value = true

        await getHistory()

        // Non-blocking: populate counts after the app is usable
        fetchTagCounts()
        fetchFolderCounts()
    }

    function clear() {
        columnStore.clear()
        instanceStore.clear()

        properties.value     = {}
        tags.value           = {}
        folders.value        = {}
        fileSources.value    = {}
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

    function applyValuesToColumnStore(
        instanceValues?: InstancePropertyValue[],
        imageValues?: ImagePropertyValue[],
        fileValues?: FilePropertyValue[],
    ) {
        const col = columnStore
        // Also write straight into instanceStore's per-instance `properties` snapshot:
        // DBInput.loadValue() reads that snapshot right after this resolves, and it's
        // otherwise only refreshed by the next websocket delta — without this, the cell
        // races the delta and can snap back to the pre-edit value.
        instanceValues?.forEach(v => {
            const slot = col.slotMap.get(v.instanceId)
            if (slot !== undefined) {
                col.writeSlot(v.propertyId, slot, v.value)
                dirtyInstances.add(v.instanceId)
            }
            if (instanceStore.instanceData[v.instanceId]) {
                instanceStore.instanceData[v.instanceId].properties[v.propertyId] = v.value
            }
        })
        imageValues?.forEach(v => {
            col.getInstancesBySha1(v.sha1).forEach(id => {
                const slot = col.slotMap.get(id)
                if (slot !== undefined) {
                    col.writeSlot(v.propertyId, slot, v.value)
                    dirtyInstances.add(id)
                }
                if (instanceStore.instanceData[id]) {
                    instanceStore.instanceData[id].properties[v.propertyId] = v.value
                }
            })
        })
        fileValues?.forEach(v => {
            col.getInstancesByFileId(v.fileId).forEach(id => {
                const slot = col.slotMap.get(id)
                if (slot !== undefined) {
                    col.writeSlot(v.propertyId, slot, v.value)
                    dirtyInstances.add(id)
                }
                if (instanceStore.instanceData[id]) {
                    instanceStore.instanceData[id].properties[v.propertyId] = v.value
                }
            })
        })
        if (dirtyInstances.size > 0) triggerRefs()
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
        if (hasUpsert) {
            res = await apiCommitUpsert(commit)
            // The response carries server-assigned ids (e.g. a newly created tag's real
            // id) and full entity data. Merge it in now instead of waiting on the next
            // websocket delta, otherwise newly created tags/properties are invisible
            // (data.tags[id] undefined) until that delta happens to arrive.
            applyCommit(res)
        }
        if (hasDelete) {
            const delRes = await apiCommitDelete(commit)
            // Instance (structural) deletes are not delta-synced → full reload.
            if (delRes?.reload) location.reload()
        }
        return res
    }

    async function addTag(propertyId: number, tagValue: string, parentIds?: number[], color = -1): Promise<Tag> {
        if (color === -1) color = Math.floor(Math.random() * 12)
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
        applyValuesToColumnStore(commit.instanceValues, commit.imageValues)
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
        await useTabStore().getMainTab()?.update()
    }

    async function deleteProperty(propertyId: number) {
        await sendCommit({ emptyProperties: [propertyId] })
        const tab = useTabStore().getMainTab()
        if (tab) {
            tab.verifyState()
            await tab.update()
        }
    }

    // Optimistically writes `value` to every affected instance in instanceStore (the only
    // store UI inputs/display should read from), marking it 'pending'. Returns the previous
    // values so the caller can roll back if the commit fails. columnStore is intentionally
    // left untouched here — it only ever holds backend-confirmed values (used for
    // filter/sort/group).
    function _optimisticWrite(propertyId: number, ids: number[], value: any): Map<number, any> {
        const previous = new Map(ids.map(id => [id, instanceStore.instanceData[id]?.properties[propertyId]]))
        for (const id of ids) instanceStore.setLocalValue(id, propertyId, value, 'pending')
        return previous
    }

    function _rollback(propertyId: number, previous: Map<number, any>) {
        for (const [id, value] of previous) instanceStore.setLocalValue(id, propertyId, value, 'error')
    }

    async function setPropertyValue(propertyId: number, imgs: Instance[] | Instance, value: any) {
        if (!Array.isArray(imgs)) imgs = [imgs]
        const mode = properties.value[propertyId].mode
        const instanceValues: InstancePropertyValue[] = []
        const imageValues:    ImagePropertyValue[]    = []
        const fileValues:     FilePropertyValue[]     = []
        const affectedIds = new Set<number>()

        if (mode === PropertyMode.id) {
            for (const i of imgs) {
                instanceValues.push({ propertyId, instanceId: i.id, value })
                affectedIds.add(i.id)
            }
        }
        if (mode === PropertyMode.sha1) {
            for (const i of imgs) {
                imageValues.push({ propertyId, sha1: (i as any).sha1, value })
                for (const id of columnStore.getInstancesBySha1((i as any).sha1)) affectedIds.add(id)
            }
        }
        if (mode === PropertyMode.file) {
            const seen = new Set<number>()
            for (const img of imgs) {
                const fileId = (img as any).fileId
                if (fileId != null && !seen.has(fileId)) {
                    seen.add(fileId)
                    fileValues.push({ propertyId, fileId, value })
                    for (const id of columnStore.getInstancesByFileId(fileId)) affectedIds.add(id)
                }
            }
        }

        const ids = Array.from(affectedIds)
        const previous = _optimisticWrite(propertyId, ids, value)
        try {
            await sendCommit({ instanceValues, imageValues, fileValues })
            applyValuesToColumnStore(instanceValues, imageValues, fileValues)
            instanceStore.markConfirmed(ids, [propertyId])
        } catch (e) {
            _rollback(propertyId, previous)
            throw e
        }
    }

    async function setPropertyValues(instanceValues: InstancePropertyValue[], imageValues: ImagePropertyValue[]) {
        const previousByProp = new Map<number, Map<number, any>>()
        const idsByProp = new Map<number, Set<number>>()

        const writeOne = (propertyId: number, id: number, value: any) => {
            if (!idsByProp.has(propertyId)) idsByProp.set(propertyId, new Set())
            idsByProp.get(propertyId)!.add(id)
            if (!previousByProp.has(propertyId)) previousByProp.set(propertyId, new Map())
            const prevMap = previousByProp.get(propertyId)!
            if (!prevMap.has(id)) prevMap.set(id, instanceStore.instanceData[id]?.properties[propertyId])
            instanceStore.setLocalValue(id, propertyId, value, 'pending')
        }

        for (const v of instanceValues) writeOne(v.propertyId, v.instanceId, v.value)
        for (const v of imageValues) {
            for (const id of columnStore.getInstancesBySha1(v.sha1)) writeOne(v.propertyId, id, v.value)
        }

        try {
            await sendCommit({ instanceValues, imageValues })
            applyValuesToColumnStore(instanceValues, imageValues)
            for (const [propertyId, ids] of idsByProp) instanceStore.markConfirmed(Array.from(ids), [propertyId])
        } catch (e) {
            for (const [propertyId, previous] of previousByProp) _rollback(propertyId, previous)
            throw e
        }
    }

    async function setTagPropertyValue(propertyId: number, imgs: Instance[] | Instance, value: any) {
        if (!Array.isArray(imgs)) imgs = [imgs]
        const mode = properties.value[propertyId].mode

        await instanceStore.ensureValues(imgs.map(i => i.id), [propertyId])

        if (mode === PropertyMode.id) {
            const values: InstancePropertyValue[] = imgs.map(i => {
                const current: number[] = instanceStore.instanceData[i.id]?.properties[propertyId] ?? []
                return { propertyId, instanceId: i.id, value: Array.from(new Set([...current, ...value])) }
            })
            const ids = values.map(v => v.instanceId)
            const previous = new Map(ids.map(id => [id, instanceStore.instanceData[id]?.properties[propertyId]]))
            for (const v of values) instanceStore.setLocalValue(v.instanceId, propertyId, v.value, 'pending')
            try {
                await sendCommit({ instanceValues: values })
                applyValuesToColumnStore(values)
                instanceStore.markConfirmed(ids, [propertyId])
            } catch (e) {
                _rollback(propertyId, previous)
                throw e
            }
        } else {
            const values: ImagePropertyValue[] = imgs.map(i => {
                const current: number[] = instanceStore.instanceData[i.id]?.properties[propertyId] ?? []
                return { propertyId, sha1: (i as any).sha1, value: Array.from(new Set([...current, ...value])) }
            })
            const affectedIds = new Set<number>()
            for (const v of values) for (const id of columnStore.getInstancesBySha1(v.sha1)) affectedIds.add(id)
            const ids = Array.from(affectedIds)
            const previous = new Map(ids.map(id => [id, instanceStore.instanceData[id]?.properties[propertyId]]))
            for (const v of values) {
                for (const id of columnStore.getInstancesBySha1(v.sha1)) instanceStore.setLocalValue(id, propertyId, v.value, 'pending')
            }
            try {
                await sendCommit({ imageValues: values })
                applyValuesToColumnStore(undefined, values)
                instanceStore.markConfirmed(ids, [propertyId])
            } catch (e) {
                _rollback(propertyId, previous)
                throw e
            }
        }
    }

    async function addPropertyGroup(name: string) {
        const [id] = await apiAllocatePropertyGroups(1)
        importPropertyGroups([{ id, name }])
        triggerRef(propertyGroups)
        await sendCommit({ propertyGroups: [{ id, name }] })
        await computePropertyTree()
    }

    async function updatePropertyGroup(id: number, name: string) {
        if (propertyGroups.value[id]) propertyGroups.value[id] = { id, name }
        triggerRef(propertyGroups)
        await sendCommit({ propertyGroups: [{ id, name }] })
    }

    async function deletePropertyGroup(id: number) {
        delete propertyGroups.value[id]
        triggerRef(propertyGroups)
        await sendCommit({ emptyPropertyGroups: [id] })
        await computePropertyTree()
    }

    async function addFolder(folder: string) {
        await apiAddFolder(folder)
    }

    async function importIiif(url: string) {
        await apiImportIiif(url)
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
        const res = await apiDeleteFolder(folderId)
        // Structural deletes are not delta-synced (they would corrupt the incremental
        // state); the server asks for a full reload instead.
        if (res?.reload) location.reload()
    }

    async function deleteFileSource(sourceId: number) {
        const res = await apiDeleteFileSource(sourceId)
        if (res?.reload) location.reload()
    }

    async function undo() {
        if (!history.value.undo.length) return
        const commit = await apiUndo()
        applyCommit(commit)
        await getHistory()
        onUndo.value++
    }

    async function redo() {
        if (!history.value.redo.length) return
        const commit = await apiRedo()
        applyCommit(commit)
        await getHistory()
        onUndo.value++
    }

    async function getHistory() {
        history.value = await apiGetHistory()
    }

    async function deleteEmptyClones() {
        const res = await apiPostDeleteEmptyClones()
        // Dedup hard-deletes instances (structural) → full reload rather than delta.
        if (res?.reload) location.reload()
        else applyCommit(res)
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
        tree.push({ groupId: PropertyGroupId.METADATA, propertyIds: [] })

        const groupToProperties: { [groupId: number]: number[] } = {}
        tree.forEach(n => { groupToProperties[n.groupId] = [] })
        props.forEach(p => {
            if (p.systemKey) p.propertyGroupId = PropertyGroupId.METADATA
            if (p.propertyGroupId == undefined || !groupToProperties[p.propertyGroupId]) {
                p.propertyGroupId = PropertyGroupId.DEFAULT
            }
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
        fetchTagCounts, fetchFolderCounts, reloadFolders,

        folders, fileSources, rootNodes, instances: instanceStore.instanceData, properties, tags, history,
        propertyGroups, propertyGroupsList, propertyTree, propertyOrder,

        folderRoots, tagList,

        onChange,
        get onSelectionChange() { return columnStore.onSelectionChange },

        onUndo, baseImgUrl, baseUrl,
        addFolder, importIiif, reImportFolder, deleteFolder, deleteFileSource,
        addProperty, updateProperty, deleteProperty,
        setPropertyValue, setTagPropertyValue, setPropertyValues,
        addTag, addTagParent, deleteTagParent, updateTag, deleteTag, mergeTags,
        addPropertyGroup, updatePropertyGroup, deletePropertyGroup,
        deleteEmptyClones, undo, redo,
        triggerPropertyTreeChange, computePropertyTree,
        importFolders, importFileSources,
        propertyList, getProperty,

        getSysField, getSysId
    }
})