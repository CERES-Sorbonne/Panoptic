/**
 * Main Store for Panoptic
 * Keeps all the raw data loaded from the Backend as a global truth
 * Main interface to modify data
 */

import { defineStore } from "pinia";
import { computed, nextTick, reactive, ref } from "vue";
import { Actions, Colors, DbCommit, Folder, FolderIndex, Image, ImageIndex, ImagePropertyValue, ImportState, InstancePropertyValue, PluginDescription, ProjectVectorDescription, Property, PropertyIndex, PropertyMode, PropertyType, Sha1ToImages, StatusUpdate, SyncResult, TabIndex, TabState, Tag, TagIndex, VectorDescription } from "./models";
import { buildTabState, defaultPropertyOption, objValues } from "./builder";
import { apiAddFolder, apiAddProperty, apiAddTag, apiAddTagParent, apiDeleteProperty, apiDeleteTag, apiDeleteTagParent, apiGetFolders, apiGetImages, apiGetStatusUpdate, apiGetProperties, apiGetTabs, apiGetTags, apiReImportFolder, apiUpdateProperty, apiUpdateTag, apiUploadPropFile, apiGetPluginsInfo, apiSetPluginParams, apiGetActions, apiGetVectorInfo, apiSetDefaultVector, apiSetTagPropertyValue, apiSetTabs, apiSetPropertyValues, apiUndo, apiRedo } from "./api";
import { buildFolderNodes, computeContainerRatio, computeTagCount, countImagePerFolder, setTagsChildren } from "./storeutils";
import { TabManager } from "@/core/TabManager";
import { getTagChildren, getTagParents, sleep } from "@/utils/utils";

let tabManager: TabManager = undefined

export const softwareUiVersion = 1

export const useProjectStore = defineStore('projectStore', () => {

    let routine = 0

    const showTutorial = ref(false)

    const data = reactive({
        images: {} as ImageIndex,
        sha1Index: {} as Sha1ToImages,
        properties: {} as PropertyIndex,
        tabs: {} as TabIndex,
        selectedTabId: undefined as number,
        folders: {} as FolderIndex,
        plugins: [] as PluginDescription[],
        vectors: {} as ProjectVectorDescription,
        tags: {} as TagIndex
    })

    const status = reactive({
        loaded: false,
        projectNotOpen: false,
        changed: false,
        renderNb: 0,
        import: {} as ImportState,
        syncResult: {} as SyncResult
    })

    const actions = ref({} as Actions)

    const backendStatus = ref<StatusUpdate>(null)

    // =======================
    // =======Computed=======
    // =======================

    const propertyList = computed(() => Object.values(data.properties) as Property[])
    const imageList = computed(() => Object.values(data.images) as Image[])
    const folderRoots = computed(() => {
        return Object.values(data.folders).filter(f => f.parent == null) as Folder[]
    })

    // =======================
    // =======Functions=======
    // =======================

    async function init() {
        if (!tabManager) {
            tabManager = new TabManager(data.tabs[data.selectedTabId])
        }
        // Execute all async functions here before setting any data into the store
        // This avoids other UI elements to react to changes before the init function is finished
        let images = await apiGetImages()
        let tags = await apiGetTags()
        let properties = await apiGetProperties()
        let folders = await apiGetFolders()
        let plugins = await apiGetPluginsInfo()
        let apiActions = await apiGetActions()
        let vectors = await apiGetVectorInfo()

        importProperties(properties)
        objValues(images).forEach((i) => importImage(i))


        importTags(tags)

        data.folders = buildFolderNodes(folders)

        backendStatus.value = await apiGetStatusUpdate()

        routine += 1
        updateRoutine(routine)
        updatePropertyOptions()

        // computeTagCount(imageList.value, properties)

        countImagePerFolder(data.folders, imageList.value)

        // console.time('tab state')
        let tabs = await apiGetTabs()
        await loadTabs(tabs)
        verifyData()
        // console.timeEnd('tab state')

        // console.log('UI Version:', softwareUiVersion)

        data.plugins = plugins
        data.vectors = vectors
        actions.value = apiActions
        status.loaded = true

        // tabManager.collection.update(data.images)
        if (localStorage.getItem('tutorialFinished') != 'true') {
            showTutorial.value = true
        }
    }

    async function updateRoutine(i: number) {
        while (routine == i) {
            const status = await apiGetStatusUpdate()
            if (!status) return

            applyStatusUpdate(status)
            await sleep(1000)
        }
    }

    function clear() {
        Object.assign(data, {
            images: {} as ImageIndex,
            sha1Index: {} as Sha1ToImages,
            properties: {} as PropertyIndex,
            tabs: {} as TabIndex,
            selectedTabId: undefined as number,
            folders: {} as FolderIndex,
        })

        Object.assign(status, {
            loaded: false,
            projectNotOpen: false,
            changed: false,
            renderNb: 0,
            import: {} as ImportState
        })
        tabManager = undefined
    }

    function applyCommit(commit: DbCommit) {
        if (commit.emptyImageValues) {
            commit.emptyImageValues.forEach(v => {
                data.sha1Index[v.sha1].forEach(i => {
                    delete data.images[i.id].properties[v.propertyId]
                })
            })
        }
        if (commit.emptyInstanceValues) {
            commit.emptyInstanceValues.forEach(v => {
                delete data.images[v.instanceId].properties[v.propertyId]
            })
        }
        if (commit.emptyTags) {
            commit.emptyTags.forEach(i => {
                delete data.tags[i]
            })
        }
        if (commit.emptyProperties) {
            commit.emptyProperties.forEach(i => {
                delete data.properties[i]
            })
        }
        if (commit.emptyInstances) {
            commit.emptyInstances.forEach(i => {
                delete data.images[i]
            })
        }

        if (commit.instances) {
            commit.instances.forEach(i => importImage(i))
        }
        if (commit.properties) {
            importProperties(commit.properties)
        }
        if (commit.tags) {
            importTags(commit.tags)
        }
        if (commit.instanceValues) {
            importInstanceValues(commit.instanceValues)
        }
        if (commit.imageValues) {
            importImageValues(commit.imageValues)
        }
    }

    function importProperties(properties: Property[]) {
        properties.forEach(p => data.properties[p.id] = p)
    }

    function importInstanceValues(instanceValues: InstancePropertyValue[]) {
        for (let v of instanceValues) {
            if (v.value == undefined) continue

            if (data.properties[v.propertyId].type == PropertyType.date) {
                v.value = new Date(v.value)
            }
            const value = { propertyId: v.propertyId, instanceId: v.instanceId, value: v.value } as InstancePropertyValue
            data.images[v.instanceId].properties[v.propertyId] = value
        }
    }

    function importImageValues(instanceValues: ImagePropertyValue[]) {
        for (let v of instanceValues) {
            if (v.value == undefined) continue

            if (data.properties[v.propertyId].type == PropertyType.date) {
                v.value = new Date(v.value)
            }
            for (let img of data.sha1Index[v.sha1]) {
                const value = { propertyId: v.propertyId, instanceId: img.id, value: v.value } as InstancePropertyValue
                data.images[img.id].properties[v.propertyId] = value
            }

        }
    }

    function verifyData() {
        tabManager.verifyState()
    }

    async function applyStatusUpdate(update: StatusUpdate) {
        // console.log(update)
        if (!status.loaded) return
        // console.log(update.update)
        const old = backendStatus.value
        const actionChanged = update.update.action > old.update.action
        const imageChanged = update.update.image > old.update.image

        backendStatus.value = update

        if (imageChanged) {
            // console.log('init again')
            nextTick(() => init())
        }

        // const newLoaded = backendStatus.value && !backendStatus.value.pluginLoaded && update.pluginLoaded

        if (actionChanged) {
            await updateActions()
        }
    }

    async function reload() {
        nextTick(() => init())
    }

    async function updateActions() {
        let plugins = await apiGetPluginsInfo()
        let apiActions = await apiGetActions()
        data.plugins = plugins
        actions.value = apiActions
    }

    function getTab() {
        return getTabManager().state
    }

    async function addTab(tabName: string) {
        let state = buildTabState()
        state.name = tabName
        const id = Math.max(-1, ...Object.keys(data.tabs).map(Number)) + 1
        state.id = id
        data.tabs[id] = state
        apiSetTabs(data.tabs)
        await selectTab(id)
    }

    async function removeTab(tabId: number) {
        if (objValues(data.tabs).length == 1) {
            await addTab('Tab1')
        } else {
            let index = objValues(data.tabs).sort((a, b) => a.id - b.id).findIndex(t => t.id == tabId)
            index = index != 0 ? index - 1 : 1
            await selectTab(objValues(data.tabs)[index].id)
        }
        delete data.tabs[tabId]
        await apiSetTabs(data.tabs)
    }

    async function updateTabs() {
        await apiSetTabs(data.tabs)
    }

    async function selectTab(tabId: number) {
        objValues(data.tabs).forEach(t => {
            if (t.id == tabId) t.selected = true
            else t.selected = false
        })
        data.selectedTabId = tabId
        await tabManager.load(data.tabs[data.selectedTabId])
        updatePropertyOptions()
    }

    async function loadTabs(tabs: TabIndex) {
        for (let tab of Object.values(tabs) as TabState[]) {
            if (tab.version != softwareUiVersion) continue
            data.tabs[tab.id] = tab
        }
        if (Object.keys(data.tabs).length == 0) {
            await addTab('Tab1')
        } else {
            const selected = objValues(data.tabs).find(t => t.selected)
            if (selected) {
                await selectTab(selected.id)
            } else {
                await selectTab(tabs[0].id)
            }
        }
        updatePropertyOptions()
    }

    function importImage(img: Image) {
        // Object.keys(img.properties).forEach(pId => img.properties[pId] = Object.assign({ propertyId: Number(pId) }, { value: img.properties[pId] }))
        // TODO: FILL THIS DATA SERVER SERVER SIDE TO MAKE IT AVAILABLE TO PLUGINS AUTOMATICALY
        // img.properties[PropertyID.id] = { propertyId: PropertyID.id, value: img.id }
        // img.properties[PropertyID.sha1] = { propertyId: PropertyID.sha1, value: img.sha1 }
        // img.properties[PropertyID.ahash] = { propertyId: PropertyID.ahash, value: img.ahash }
        // img.properties[PropertyID.folders] = { propertyId: PropertyID.folders, value: img.folder_id }
        // img.properties[PropertyID.width] = { propertyId: PropertyID.width, value: img.width }
        // img.properties[PropertyID.height] = { propertyId: PropertyID.height, value: img.height }

        for (let pId in img.properties) {
            const propValue = img.properties[pId]
            if (propValue.value == undefined) continue

            const property = data.properties[pId]
            if (!property) continue
            if (property.type == PropertyType.date) {
                const date = new Date(propValue.value)
                propValue.value = date
            }
        }

        img.containerRatio = computeContainerRatio(img)

        if (!data.images[img.id]) {
            if (!Array.isArray(data.sha1Index[img.sha1])) {
                data.sha1Index[img.sha1] = []
            }
            data.sha1Index[img.sha1].push(img)
        }
        // TODO: verify it doesnt break link with the sha1Index
        data.images[img.id] = img
    }

    async function addTag(propertyId: number, tagValue: string, parentId?: number, color?: number): Promise<Tag> {
        if (color == undefined) {
            let r = Math.round(Math.random() * (Colors.length - 1))
            color = r
        }
        const newTag: Tag = await apiAddTag(propertyId, tagValue, color, parentId)
        // newTag.count = 0
        importTags([newTag])
        // if (!data.properties[propertyId].tags) {
        //     data.properties[propertyId].tags = {}
        // }
        // data.properties[propertyId].tags[newTag.id] = newTag
        return newTag
    }

    async function addTagParent(tagId: number, parentId: number) {
        const tag = await apiAddTagParent(tagId, parentId) as Tag
        Object.assign(data.properties[tag.propertyId].tags[tag.id], tag)
        const parent = data.properties[tag.propertyId].tags[parentId]
        if (!parent || parent.children.indexOf(tagId) >= 0) return
        parent.children.push(tagId)
    }

    async function deleteTagParent(tagId: number, parentId: number, dontAsk?: boolean) {
        if (parentId == 0) throw new TypeError('UI should not use this function to delete tag from root')
        if (!dontAsk) {
            let ok = confirm('Delete tag: ' + tagId)
            if (!ok) return
        }
        const tag = await apiDeleteTagParent(tagId, parentId)
        Object.assign(data.properties[tag.propertyId].tags[tag.id], tag)
        const parent = data.properties[tag.propertyId].tags[parentId]
        if (!parent) return
        const childrenIndex = parent.children.indexOf(tagId)
        if (childrenIndex < 0) return
        parent.children.splice(childrenIndex, 1)
    }

    async function deleteTag(tagId: number, dontAsk?: boolean) {
        if (!dontAsk) {
            let ok = confirm('Delete tag: ' + tagId)
            if (!ok) return
        }
        const res = await apiDeleteTag(tagId)
        importPropertyValues(res.updatedValues)
        importTags(res.updatedTags)
        data.tags[tagId].deleted = true

        await tabManager.collection.update()

    }

    function importPropertyValues(values: InstancePropertyValue[]) {
        for (let val of values) {
            const props = data.properties[val.propertyId]
            const ids = props.mode == PropertyMode.id ? [val.instanceId] : data.sha1Index[data.images[val.instanceId].sha1].map(i => i.id)
            if (val.value !== undefined) {
                ids.forEach(i => data.images[i].properties[val.propertyId] = val)
            } else {
                ids.forEach(i => delete data.images[i].properties[val.propertyId])
            }
        }
    }

    function importTags(tags: Tag[]) {
        const updated = new Set<number>()
        for (let tag of tags) {
            data.tags[tag.id] = tag
            if (!(tag.propertyId in data.properties)) {
                console.warn('Property ' + tag.propertyId + ' must be loaded before importing tags')
                continue
            }
            if (!data.properties[tag.propertyId].tags) {
                data.properties[tag.propertyId].tags = {}
            }
            data.properties[tag.propertyId].tags[tag.id] = tag
            updated.add(tag.propertyId)

        }
        for (let propId of updated) {
            setTagsChildren(data.properties[propId].tags)
        }
        for(let tag of tags) {
            tag.allChildren = getTagChildren(tag)
            tag.allChildren.splice(tag.allChildren.indexOf(tag.id), 1)
            tag.allParents = getTagParents(tag)
        }
        computeTagCount()
    }

    async function addProperty(name: string, type: PropertyType, mode: PropertyMode) {
        const newProperty: Property = await apiAddProperty(name, type, mode)
        importProperties([newProperty])
        updatePropertyOptions()
        getTab().visibleProperties[newProperty.id] = true
        return newProperty
    }

    async function setPropertyValue(propertyId: number, images: Image[] | Image, value: any, dontEmit?: boolean) {
        if (!Array.isArray(images)) {
            images = [images]
        }
        const mode = data.properties[propertyId].mode
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
        const commit = await apiSetPropertyValues(instanceValues, imageValues)
        applyCommit(commit)

        if (data.properties[propertyId].tags != undefined) {
            computeTagCount()
        }

        if (!dontEmit) tabManager.collection.update()
    }

    async function setPropertyValues(instanceValues: InstancePropertyValue[], imageValues: ImagePropertyValue[], dontEmit?: boolean) {
        const commit = await apiSetPropertyValues(instanceValues, imageValues)
        applyCommit(commit)

        // if (data.properties[propertyId].tags != undefined) {
        //     computeTagCount(imageList.value, data.properties)
        // }

        if (!dontEmit) tabManager.collection.update()
    }

    async function setTagPropertyValue(propertyId: number, images: Image[] | Image, value: any, mode: string, dontEmit?: boolean) {
        if (!Array.isArray(images)) {
            images = [images]
        }

        const imageIds = images.map(i => i.id)
        const values = await apiSetTagPropertyValue(propertyId, imageIds, value, mode)
        importPropertyValues(values)
        computeTagCount()

        if (!dontEmit) tabManager.collection.update()
    }

    async function updateTag(propId: number, tagId: number, color?: number, parentId?: number, value?: any) {
        const newTag = await apiUpdateTag(tagId, color, parentId, value)
        Object.assign(data.properties[newTag.propertyId].tags[newTag.id], newTag)
    }

    async function addFolder(folder: string) {
        await apiAddFolder(folder)
        init()
    }

    async function updateProperty(propertyId: number, name?: string) {
        await apiUpdateProperty(propertyId, name)
        data.properties[propertyId].name = name
        updatePropertyOptions()
    }

    async function deleteProperty(propertyId: number) {
        await apiDeleteProperty(propertyId)
        delete data.properties[propertyId]

        Object.values(data.tabs).forEach((t: TabState) => {
            Object.keys(t.visibleProperties).map(Number).forEach(k => {
                if (data.properties[k] == undefined) {
                    delete t.visibleProperties[k]
                }
            })
        })
        verifyData()
        tabManager.collection.update()
        // rerender()
    }

    function rerender() {
        status.renderNb += 1
    }

    async function uploadPropFile(file: any) {
        const res = await apiUploadPropFile(file)
        init()
        return res
    }

    function updatePropertyOptions() {
        for (let tabId in data.tabs) {
            const tab = data.tabs[tabId]
            if (tab.propertyOptions == undefined) {
                tab.propertyOptions = {}
            }
            for (let propId in data.properties) {
                tab.propertyOptions[propId] = Object.assign(defaultPropertyOption(), tab.propertyOptions[propId])
            }
        }
    }

    function getTabManager() {
        return tabManager
    }

    function reImportFolder(folderId: number) {
        apiReImportFolder(folderId)
    }

    function clearImport() {
        status.import.to_import = undefined
    }

    async function updatePluginInfos() {
        data.plugins = await apiGetPluginsInfo()
        actions.value = await apiGetActions()
    }

    async function setPluginParams(plugin: string, params: any) {
        const plugins = await apiSetPluginParams(plugin, params)
        data.plugins = plugins
    }

    // async function setActionFunctions(updates: ActionParam[]) {
    //     actions.value = await apiSetActions(updates)
    // }

    async function setDefaultVectors(vector: VectorDescription) {
        data.vectors = await apiSetDefaultVector(vector)
    }

    async function undo() {
        const commit = await apiUndo()
        applyCommit(commit)
        getTabManager().collection.update()
    }

    async function redo() {
        const commit = await apiRedo()
        applyCommit(commit)
        getTabManager().collection.update()
    }

    return {
        // variables
        data, status,

        // computed
        propertyList, imageList, folderRoots,

        // functions
        init, clear, rerender, addFolder, reImportFolder,
        addProperty, deleteProperty, updateProperty, setPropertyValue, setTagPropertyValue, setPropertyValues,
        addTab, removeTab, updateTabs, selectTab, getTab, getTabManager,
        addTag, deleteTagParent, updateTag, addTagParent, deleteTag,
        uploadPropFile, clearImport,
        updatePluginInfos, setPluginParams,
        undo, redo,
        actions,
        // setActionFunctions, hasGroupFunction, hasSimilaryFunction,
        setDefaultVectors,
        backendStatus, reload,
        showTutorial
    }

})
