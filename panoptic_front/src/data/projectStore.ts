/**
 * Main Store for Panoptic
 * Keeps all the raw data loaded from the Backend as a global truth
 * Main interface to modify data
 */

import { defineStore } from "pinia";
import { computed, nextTick, reactive, ref, shallowRef, watch } from "vue";
import { Actions, CommitHistory, DbCommit, ExecuteActionPayload, Folder, FolderIndex, FunctionDescription, ImagePropertyValue, ImportState, Instance, InstanceIndex, InstancePropertyValue, PluginDescription, ProjectVectorDescription, Property, PropertyIndex, PropertyMode, PropertyType, Sha1ToInstances, StatusUpdate, TabIndex, TabState, Tag, TagIndex, VectorDescription } from "./models";
import { buildTabState, defaultPropertyOption, objValues } from "./builder";
import { apiAddFolder, apiGetFolders, apiGetTabs, apiReImportFolder, apiUploadPropFile, apiGetPluginsInfo, apiSetPluginParams, apiGetActions, apiGetVectorInfo, apiSetDefaultVector, apiSetTabs, apiUndo, apiRedo, apiGetHistory, apiCallActions, apiGetUpdate, SERVER_PREFIX, apiGetDbState, apiCommit, apiGetStatus, apiDeleteFolder } from "./api";
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
        plugins: [] as PluginDescription[],
        vectors: {} as ProjectVectorDescription,
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
    // =======Functions=======
    // =======================

    async function init() {


        console.log('init')
        if (!tabManager) {
            tabManager = new TabManager((data.tabs[data.selectedTabId]))
        }
        // Execute all async functions here before setting any data into the store
        // This avoids other UI elements to react to changes before the init function is finished
        // let folders = await apiGetFolders()
        // console.time('Request')
        // let dbState = await apiGetDbState()
        // console.timeEnd('Request')

        let plugins = await apiGetPluginsInfo()
        let apiActions = await apiGetActions()
        let vectors = await apiGetVectorInfo()
        let tabs = await apiGetTabs()

        backendStatus.value = (await apiGetUpdate()).status

        // data.folders = buildFolderNodes(folders)
        // console.time('commit')
        // applyCommit(dbState)
        // console.timeEnd('commit')


        data.plugins = plugins
        data.vectors = vectors
        actions.value = apiActions

        routine += 1
        updateRoutine(routine)
        updatePropertyOptions()

        // computeTagCount()

        // TODO: put back
        // countImagePerFolder(data.folders, imageList.value)

        if (localStorage.getItem('tutorialFinished') != 'true') {
            showTutorial.value = true
        }
        await dataStore.init()

        await loadTabs(tabs)
        verifyData()

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
                        await dataStore.applyCommit(commit)
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
            tabs: {} as TabIndex,
            selectedTabId: undefined as number,
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

        dataStore.clear()
    }

    // function applyCommit(commit: DbCommit) {
    //     if (commit.properties && getTab().visibleProperties) {
    //         commit.properties.forEach(p => {
    //             getTab().visibleProperties[p.id] = true
    //         })
    //         updatePropertyOptions()
    //     }
    //     tabManager.collection.setDirty()
    // }

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



    function rerender() {
        status.renderNb += 1
    }

    async function uploadPropFile(file: any) {
        const res = await apiUploadPropFile(file)
        init()
        return res
    }

   

    function getTabManager() {
        return tabManager
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



    async function call(req: ExecuteActionPayload) {
        const res = await apiCallActions(req)
        if (res.commit) {
            dataStore.applyCommit(res.commit)
            // applyCommit(res.commit)
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

        // functions
        init, clear, rerender,
        addTab, removeTab, updateTabs, selectTab, getTab, getTabManager,
        
        uploadPropFile, clearImport,
        updatePluginInfos, setPluginParams,
        call,
        actions,
        // setActionFunctions, hasGroupFunction, hasSimilaryFunction,
        setDefaultVectors,
        backendStatus, reload,
        showTutorial
    }

})
