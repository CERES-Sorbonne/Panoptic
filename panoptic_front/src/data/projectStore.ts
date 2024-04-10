/**
 * Main Store for Panoptic
 * Keeps all the raw data loaded from the Backend as a global truth
 * Main interface to modify data
 */

import { defineStore } from "pinia";
import { computed, nextTick, reactive, ref, watch } from "vue";
import { ActionDescription, ActionParam, Colors, Folder, FolderIndex, Image, ImageIndex, ImportState, InstancePropertyValue, ModalId, PluginDefaultParams, PluginDescription, ProjectVectorDescription, Property, PropertyID, PropertyIndex, PropertyMode, PropertyType, PropertyValue, Sha1ToImages, StatusUpdate, SyncResult, TabIndex, TabState, Tag, TagIndex, UpdateCounter, VectorDescription } from "./models";
import { buildTabState, defaultPropertyOption, objValues, propertyDefault } from "./builder";
import { ApiTab, apiAddFolder, apiAddProperty, apiAddTab, apiAddTag, apiAddTagParent, apiDeleteProperty, apiDeleteTab, apiDeleteTag, apiDeleteTagParent, apiGetFolders, apiGetImages, apiGetStatusUpdate, apiGetProperties, apiGetTabs, apiGetTags, apiReImportFolder, apiSetPropertyValue, apiUpdateProperty, apiUpdateTab, apiUpdateTag, apiUploadPropFile, apiGetPluginsInfo, apiSetPluginDefaults, apiGetActions, apiSetActions, apiGetVectorInfo, apiSetDefaultVector, apiSetTagPropertyValue } from "./api";
import { buildFolderNodes, computeContainerRatio, computeTagCount, countImagePerFolder, setTagsChildren } from "./storeutils";
import { TabManager } from "@/core/TabManager";
import { usePanopticStore } from "./panopticStore";
import { sleep } from "@/utils/utils";

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

    const actions = ref([] as ActionDescription[])

    const backendStatus = ref<StatusUpdate>(null)

    // =======================
    // =======Computed=======
    // =======================

    const propertyList = computed(() => Object.values(data.properties) as Property[])
    const imageList = computed(() => Object.values(data.images) as Image[])
    const folderRoots = computed(() => {
        return Object.values(data.folders).filter(f => f.parent == null) as Folder[]
    })
    const hasSimilaryFunction = computed(() => {
        const action = actions.value.find(a => a.name == 'find_similar')
        if(!action) return false
        return action.selectedFunction != undefined
    })
    const hasGroupFunction = computed(() => {
        const action = actions.value.find(a => a.name == 'group')
        if(!action) return false
        return action.selectedFunction != undefined
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

        // properties[PropertyID.id] = { id: PropertyID.id, name: '', type: 'id', mode: PropertyMode.computed }
        // properties[PropertyID.sha1] = { id: PropertyID.sha1, name: 'sha1', type: PropertyType._sha1, mode: PropertyMode.computed }
        // properties[PropertyID.ahash] = { id: PropertyID.ahash, name: 'average hash', type: PropertyType._ahash, mode: PropertyMode.computed }
        // properties[PropertyID.folders] = { id: PropertyID.folders, name: 'folders', type: PropertyType._folders, mode: PropertyMode.computed }
        // properties[PropertyID.width] = { id: PropertyID.width, name: 'width', type: PropertyType._width, mode: PropertyMode.computed }
        // properties[PropertyID.height] = { id: PropertyID.height, name: 'height', type: PropertyType._height, mode: PropertyMode.computed }


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
        tabs.filter(t => t.data.version == softwareUiVersion)
        await loadTabs(tabs)
        verifySelectedTab()
        verifyData()
        // console.timeEnd('tab state')

        // console.log('UI Version:', softwareUiVersion)

        data.plugins = plugins
        data.vectors = vectors
        actions.value = apiActions
        status.loaded = true

        // tabManager.collection.update(data.images)
        if(localStorage.getItem('tutorialFinished') != 'true') {
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

    function importProperties(properties: Property[]) {
        properties.forEach(p => data.properties[p.id] = p)
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
        let tab = await apiAddTab({ data: state })
        tab.data.id = tab.id
        data.tabs[tab.id] = tab.data
        await selectTab(tab.id)
    }

    async function removeTab(tabId: number) {
        if (objValues(data.tabs).length == 1) {
            await addTab('Tab1')
        }
        await apiDeleteTab(tabId)
        delete data.tabs[tabId]
        verifySelectedTab()
    }

    async function updateTab(tab: TabState) {
        await apiUpdateTab({ id: tab.id, data: tab })
    }

    async function selectTab(tabId: number) {
        data.selectedTabId = tabId
        await tabManager.load(data.tabs[data.selectedTabId])
        updatePropertyOptions()
    }

    async function loadTabs(tabs: ApiTab[]) {
        tabs.forEach(t => {
            t.data.id = t.id
            data.tabs[t.id] = t.data
        })

        if (tabs.length == 0) {
            await addTab('Tab1')
        } else {
            await selectTab(tabs[0].id)
        }
        verifySelectedTab()
        updatePropertyOptions()
    }

    function verifySelectedTab() {
        if (getTab() != undefined) {
            return
        }
        data.selectedTabId = Number(Object.keys(data.tabs)[0])
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
        computeTagCount(imageList.value, data.properties)
    }

    async function addProperty(name: string, type: PropertyType, mode: PropertyMode) {
        const newProperty: Property = await apiAddProperty(name, type, mode)
        importProperties([newProperty])
        updatePropertyOptions()
        getTab().visibleProperties[newProperty.id] = true
    }

    async function setPropertyValue(propertyId: number, images: Image[] | Image, value: any, dontEmit?: boolean) {
        if (!Array.isArray(images)) {
            images = [images]
        }

        const imageIds = images.map(i => i.id)
        const values = await apiSetPropertyValue(propertyId, imageIds, value)

        importPropertyValues(values)

        if (data.properties[propertyId].tags != undefined) {
            computeTagCount(imageList.value, data.properties)
        }

        if (!dontEmit) tabManager.collection.update()
    }

    async function setTagPropertyValue(propertyId: number, images: Image[] | Image, value: any, mode: string, dontEmit?: boolean) {
        if (!Array.isArray(images)) {
            images = [images]
        }

        const imageIds = images.map(i => i.id)
        const values = await apiSetTagPropertyValue(propertyId, imageIds, value, mode)
        importPropertyValues(values)
        computeTagCount(imageList.value, data.properties)

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

    async function setPluginDefaults(defaults: PluginDefaultParams) {
        const updated = await apiSetPluginDefaults(defaults)
        const plugin = data.plugins.find(p => p.name == updated.name)
        plugin.defaults = updated
    }

    async function setActionFunctions(updates: ActionParam[]) {
        actions.value = await apiSetActions(updates)
    }

    async function setDefaultVectors(vector: VectorDescription) {
        data.vectors = await apiSetDefaultVector(vector)
    }

    return {
        // variables
        data, status,

        // computed
        propertyList, imageList, folderRoots,

        // functions
        init, clear, rerender, addFolder, reImportFolder,
        addProperty, deleteProperty, updateProperty, setPropertyValue, setTagPropertyValue,
        addTab, removeTab, updateTab, selectTab, getTab, getTabManager,
        addTag, deleteTagParent, updateTag, addTagParent, deleteTag,
        uploadPropFile, clearImport,
        updatePluginInfos, setPluginDefaults,
        actions, setActionFunctions, hasGroupFunction, hasSimilaryFunction,
        setDefaultVectors,
        backendStatus, reload,
        showTutorial
    }

})
