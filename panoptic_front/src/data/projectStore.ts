/**
 * Main Store for Panoptic
 * Keeps all the raw data loaded from the Backend as a global truth
 * Main interface to modify data
 */

import { defineStore } from "pinia";
import { nextTick, reactive, ref, shallowRef } from "vue";
import { ActionFunctions, ExecuteActionPayload, FunctionDescription, ImportState, PluginDescription, ProjectSettings, ProjectVectorDescription, ScoreInterval, StatusUpdate, TabIndex, UiState, VectorDescription } from "./models";
import { apiUploadPropFile, apiGetPluginsInfo, apiSetPluginParams, apiGetActions, apiGetVectorInfo, apiSetDefaultVector, apiCallActions, apiGetUpdate, apiGetSettings, apiSetSettings, apiGetUIData, apiSetUIData } from "./api";
import { deepCopy, sleep } from "@/utils/utils";
import { useDataStore } from "./dataStore";
import { usePanopticStore } from "./panopticStore";
import { useTabStore } from "./tabStore";
import { useI18n } from 'vue-i18n';

export const test = shallowRef({ count: 0 })

export const softwareUiVersion = 2

export const useProjectStore = defineStore('projectStore', () => {

    let routine = 0

    const dataStore = useDataStore()
    const { locale } = useI18n();

    const showTutorial = ref(false)

    const data = reactive({
        tabs: {} as TabIndex,
        selectedTabId: undefined as number,
        plugins: [] as PluginDescription[],
        vectors: {} as ProjectVectorDescription,
        counter: 0,
        settings: {} as ProjectSettings,
        uiState: { similarityIntervals: {} } as UiState,
    })

    const status = reactive({
        loaded: false,
        projectNotOpen: false,
        changed: false,
        renderNb: 0,
        onUndo: 0,
        import: {} as ImportState,
    })

    const actions = ref({} as ActionFunctions)

    const backendStatus = ref<StatusUpdate>(null)

    // =======================
    // =======Functions=======
    // =======================

    async function init() {
        console.log('init')
        // Execute all async functions here before setting any data into the store
        // This avoids other UI elements to react to changes before the init function is finished
        // let folders = await apiGetFolders()
        // console.time('Request')
        // let dbState = await apiGetDbState()
        // console.timeEnd('Request')
        let plugins = await apiGetPluginsInfo()
        let apiActions = await apiGetActions()
        let vectors = await apiGetVectorInfo()
        // let tabs = await apiGetTabs()
        let settings = await apiGetSettings()

        backendStatus.value = (await apiGetUpdate()).status

        // data.folders = buildFolderNodes(folders)
        // console.time('commit')
        // applyCommit(dbState)
        // console.timeEnd('commit')


        data.plugins = plugins
        data.vectors = vectors
        actions.value = apiActions
        data.settings = settings

        routine += 1
        updateRoutine(routine)

        // computeTagCount()

        // TODO: put back
        // countImagePerFolder(data.folders, imageList.value)

        await loadUiState()

        if (localStorage.getItem('tutorialFinished') != 'true') {
            showTutorial.value = true
        }
        await dataStore.init()

        // await loadTabs(tabs)
        // verifyData()


        status.loaded = true
        // usePanopticStore().showModal(ModalId.TAG, {})
    }

    async function updateRoutine(i: number) {
        while (routine == i) {
            const update = await apiGetUpdate()
            if (routine != i) return
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
                        dataStore.applyCommit(commit)
                    }
                    useTabStore().getMainTab().update()
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
            plugins: [] as PluginDescription[],
            vectors: {} as ProjectVectorDescription,
            counter: 0,
            settings: {} as ProjectSettings,
            uiState: { similarityIntervals: {} } as UiState,
        })

        Object.assign(status, {
            loaded: false,
            projectNotOpen: false,
            changed: false,
            renderNb: 0,
            onUndo: 0,
            import: {} as ImportState
        })
        actions.value = {}
        backendStatus.value = null
        routine = 0
        dataStore.clear()
        useTabStore().clear()

    }

    async function applyStatusUpdate(update: StatusUpdate) {
        backendStatus.value = update
    }

    async function reload() {
        await nextTick()
        init()
    }

    function rerender() {
        status.renderNb += 1
    }

    async function uploadPropFile(file: any) {
        const res = await apiUploadPropFile(file)
        init()
        return res
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

    async function setDefaultVectors(vector: VectorDescription) {
        data.vectors = await apiSetDefaultVector(vector)
    }

    async function call(req: ExecuteActionPayload) {
        const res = await apiCallActions(req)
        if (!res) return
        if (res.notifs) {
            const panoptic = usePanopticStore()
            panoptic.notify(res.notifs)
        }
        if (res.commit) {
            dataStore.applyCommit(res.commit)
            if (res.commit.properties) {
                // TODO: see if need fix
                // res.commit.properties.forEach(p => getTab().visibleProperties[p.id] = true)
            }
        }
        return res
    }

    async function updateSettings(settings: ProjectSettings) {
        const res = await apiSetSettings(settings)
        data.settings = res
    }

    async function loadUiState() {
        const res = await apiGetUIData('uiState')
        if (res) {
            data.uiState = res

            if (data.uiState.lang) {
                locale.value = data.uiState.lang
            }
        }

        correctUiState()
    }

    function correctUiState() {

        if (!data.uiState.similarityIntervals) {
            data.uiState.similarityIntervals = {}
        }
        if (!data.uiState.similarityImageSize) {
            data.uiState.similarityImageSize = 70
        }
    }

    async function setLang(lang: string) {
        data.uiState.lang = lang
        await saveUiState()
    }

    async function saveUiState() {
        await apiSetUIData('uiState', data.uiState)
    }

    async function updateScoreInterval(funcId: string, interval: ScoreInterval) {
        data.uiState.similarityIntervals[funcId] = deepCopy(interval)
        await saveUiState()
    }

    return {
        // variables
        data, status,

        // functions
        init, clear, rerender,
        updateSettings,
        uploadPropFile, clearImport,
        updatePluginInfos, setPluginParams, saveUiState,
        call,
        actions,
        updateScoreInterval,
        // setActionFunctions, hasGroupFunction, hasSimilaryFunction,
        setDefaultVectors,
        backendStatus, reload,
        showTutorial, setLang
    }

})
