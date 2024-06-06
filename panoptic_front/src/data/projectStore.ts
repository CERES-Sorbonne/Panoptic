/**
 * Main Store for Panoptic
 * Keeps all the raw data loaded from the Backend as a global truth
 * Main interface to modify data
 */

import { defineStore } from "pinia";
import { computed, nextTick, reactive, ref, shallowRef, watch } from "vue";
import { Actions, CommitHistory, DbCommit, ExecuteActionPayload, Folder, FolderIndex, FunctionDescription, ImagePropertyValue, ImportState, Instance, InstanceIndex, InstancePropertyValue, PluginDescription, ProjectVectorDescription, Property, PropertyIndex, PropertyMode, PropertyType, Sha1ToInstances, StatusUpdate, TabIndex, TabState, Tag, TagIndex, VectorDescription } from "./models";
import { buildTabState, defaultPropertyOption, objValues } from "./builder";
import { apiAddFolder, apiGetFolders, apiGetTabs, apiReImportFolder, apiUploadPropFile, apiGetPluginsInfo, apiSetPluginParams, apiGetActions, apiGetVectorInfo, apiSetDefaultVector, apiSetTabs, apiUndo, apiRedo, apiGetHistory, apiCallActions, apiGetUpdate, SERVER_PREFIX, apiGetDbState, apiCommit, apiGetStatus } from "./api";
import { buildFolderNodes, computeTagCount } from "./storeutils";
import { TabManager } from "@/core/TabManager";
import { deepCopy, sleep } from "@/utils/utils";
import { useDataStore } from "./dataStore";

let tabManager: TabManager = undefined

export const test = shallowRef({ count: 0 })

export const softwareUiVersion = 2

export const useProjectStore = defineStore('projectStore', () => {

    let routine = 0

    const dataStore = useDataStore()

    const showTutorial = ref(false)
    // const images = shallowRef({} as ImageIndex)
    const images = shallowRef({})

    const data = reactive({
        tabs: {} as TabIndex,
        selectedTabId: undefined as number,
        folders: {} as FolderIndex,
        plugins: [] as PluginDescription[],
        vectors: {} as ProjectVectorDescription,
        history: {} as CommitHistory,
        counter: 0
    })

    const status = reactive({
        loaded: false,
        projectNotOpen: false,
        changed: false,
        renderNb: 0,
        onUndo: 0,
        import: {} as ImportState
    })

    const actions = ref({} as Actions)

    const backendStatus = ref<StatusUpdate>(null)

    // =======================
    // =======Computed=======
    // =======================

    const folderRoots = computed(() => {
        return Object.values(data.folders).filter(f => f.parent == null) as Folder[]
    })

    // =======================
    // =======Functions=======
    // =======================

    async function init() {


        console.log('init')
        if (!tabManager) {
            tabManager = new TabManager((data.tabs[data.selectedTabId]))
        }
        // Execute all async functions here before setting any data into the store
        // This avoids other UI elements to react to changes before the init function is finished
        let folders = await apiGetFolders()
        console.time('Request')
        let dbState = await apiGetDbState()
        console.timeEnd('Request')

        let plugins = await apiGetPluginsInfo()
        let apiActions = await apiGetActions()
        let vectors = await apiGetVectorInfo()
        let tabs = await apiGetTabs()

        backendStatus.value = (await apiGetUpdate()).status

        data.folders = buildFolderNodes(folders)
        console.time('commit')
        applyCommit(dbState)
        console.timeEnd('commit')


        data.plugins = plugins
        data.vectors = vectors
        actions.value = apiActions

        routine += 1
        updateRoutine(routine)
        updatePropertyOptions()

        computeTagCount()

        // TODO: put back
        // countImagePerFolder(data.folders, imageList.value)

        if (localStorage.getItem('tutorialFinished') != 'true') {
            showTutorial.value = true
        }

        await loadTabs(tabs)
        verifyData()
        await getHistory()
        status.loaded = true
    }

    async function updateRoutine(i: number) {
        while (routine == i) {
            const update = await apiGetUpdate()
            // console.log(update)
            if (update) {
                if (update.status) {
                    await applyStatusUpdate(update.status)
                }
                if (update.actions) {
                    importActions(update.actions)
                }
                if (update.plugins) {
                    importPlugins(update.plugins)
                }
                if (update.commits) {
                    for (let commit of update.commits) {
                        await applyCommit(commit)
                    }
                    tabManager.collection.update()
                }
            }
            await sleep(1000)
        }
    }

    function importActions(actionList: FunctionDescription[]) {
        actions.value = {}
        actionList.forEach(a => actions.value[a.id] = a)
    }

    function importPlugins(plugins: PluginDescription[]) {
        data.plugins = plugins
    }

    function clear() {
        Object.assign(data, {
            images: {} as InstanceIndex,
            sha1Index: {} as Sha1ToInstances,
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
            onUndo: 0,
            import: {} as ImportState
        })
        tabManager = undefined
    }

    function applyCommit(commit: DbCommit) {
        dataStore.applyCommit(commit)
        if (commit.history) {
            data.history = commit.history
        }
        if (commit.properties && getTab().visibleProperties) {
            commit.properties.forEach(p => {
                getTab().visibleProperties[p.id] = true
            })
            updatePropertyOptions()
        }
        tabManager.collection.setDirty()
    }

    function verifyData() {
        tabManager.verifyState()
    }

    async function applyStatusUpdate(update: StatusUpdate) {
        backendStatus.value = update
    }

    async function reload() {
        nextTick(() => init())
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
        Object.assign(data.tabs[data.selectedTabId], tabManager.state)
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

    async function sendCommit(commit: DbCommit, undo?: boolean) {
        console.log('send commit', commit)
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
        const tag: Tag = Object.assign({}, dataStore.tags[tagId])
        tag.parents.push(parentId)
        const res = await sendCommit({ tags: [tag] })
    }

    async function deleteTagParent(tagId: number, parentId: number) {
        const tag: Tag = Object.assign({}, dataStore.tags[tagId])
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
        const prop = dataStore.properties[propertyId]
        // if(prop.type == PropertyType.date) {
        //     if(value) {
        //         value = (value as Date).toISOString()
        //     }
        // }
        const mode = dataStore.properties[propertyId].mode
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

        if (dataStore.properties[propertyId].tags != undefined) {
            computeTagCount()
        }
    }

    async function setPropertyValues(instanceValues: InstancePropertyValue[], imageValues: ImagePropertyValue[], dontEmit?: boolean) {
        await sendCommit({ instanceValues: instanceValues, imageValues: imageValues }, true)

        const propIds = new Set<number>()
        instanceValues.forEach(v => propIds.add(v.propertyId))
        imageValues.forEach(v => propIds.add(v.propertyId))

        const tagProps = Array.from(propIds).filter(p => dataStore.properties[p].type)
        if (tagProps.length) {
            computeTagCount()
        }
    }

    async function setTagPropertyValue(propertyId: number, images: Instance[] | Instance, value: any, dontEmit?: boolean) {
        if (!Array.isArray(images)) {
            images = [images]
        }
        const currentValues = images.map(i => ({ value: i.properties[propertyId] ?? [], img: i }))
        if (dataStore.properties[propertyId].mode == PropertyMode.id) {
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
        computeTagCount()
    }

    async function updateTag(tagId: number, value?: any, color?: number) {
        const tag = Object.assign({}, dataStore.tags[tagId])
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
        const prop = deepCopy(dataStore.properties[propertyId])
        prop.name = name
        sendCommit({ properties: [prop] })
        updatePropertyOptions()
    }

    async function deleteProperty(propertyId: number) {
        await sendCommit({ emptyProperties: [propertyId] })
        delete dataStore.properties[propertyId]

        Object.values(data.tabs).forEach((t: TabState) => {
            Object.keys(t.visibleProperties).map(Number).forEach(k => {
                if (dataStore.properties[k] == undefined) {
                    delete t.visibleProperties[k]
                }
            })
        })
        verifyData()
        // tabManager.collection.update()
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
            for (let propId in dataStore.properties) {
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
        if (!data.history.undo.length) return
        const commit = await apiUndo()
        applyCommit(commit)
        status.onUndo++
        getTabManager().collection.update()
    }

    async function redo() {
        if (!data.history.redo.length) return
        const commit = await apiRedo()
        applyCommit(commit)
        status.onUndo++
        getTabManager().collection.update()
    }

    async function getHistory() {
        const res = await apiGetHistory()
        data.history = res
    }

    async function call(req: ExecuteActionPayload) {
        const res = await apiCallActions(req)
        if (res.commit) {
            applyCommit(res.commit)
            //console.log(res.commit)
            if (res.commit.properties) {
                res.commit.properties.forEach(p => getTab().visibleProperties[p.id] = true)
            }
        }
        return res
    }

    return {
        // variables
        data, status,
        images,
        // computed
        folderRoots,

        // functions
        init, clear, rerender, addFolder, reImportFolder,
        addProperty, deleteProperty, updateProperty, setPropertyValue, setTagPropertyValue, setPropertyValues,
        addTab, removeTab, updateTabs, selectTab, getTab, getTabManager,
        addTag, deleteTagParent, updateTag, addTagParent, deleteTag,
        uploadPropFile, clearImport,
        updatePluginInfos, setPluginParams,
        undo, redo, call,
        actions, sendCommit,
        // setActionFunctions, hasGroupFunction, hasSimilaryFunction,
        setDefaultVectors,
        backendStatus, reload,
        showTutorial
    }

})
