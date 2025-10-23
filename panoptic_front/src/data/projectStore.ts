/**
 * Main Store for Panoptic
 * Keeps all the raw data loaded from the Backend as a global truth
 * Main interface to modify data
 */

import { defineStore } from "pinia";
import { computed, nextTick, reactive, ref, shallowRef } from "vue";
import { ExecuteActionPayload, PluginDescription, ProjectSettings, ScoreInterval, StatusUpdate, UIDataKeys, UiState, ProjectState, TaskState } from "./models";
import { apiUploadPropFile, apiGetPluginsInfo, apiSetPluginParams, apiGetActions, apiCallActions, apiSetSettings, apiGetUIData, apiSetUIData, apiGetProjectState } from "./apiProjectRoutes";
import { deepCopy } from "@/utils/utils";
import { useDataStore } from "./dataStore";
import { usePanopticStore } from "./panopticStore";
import { useTabStore } from "./tabStore";
import { useI18n } from 'vue-i18n';
import { useActionStore } from "./actionStore";

export const test = shallowRef({ count: 0 })

export const softwareUiVersion = 2

export const useProjectStore = defineStore('projectStore', () => {
    const dataStore = useDataStore()
    const tabStore = useTabStore()
    const actionStore = useActionStore()
    const { locale } = useI18n();

    const loaded = ref(false)
    const showTutorial = ref(false)
    const state = ref<ProjectState>()
    const uiState = ref<UiState>()

    const isImportingImages = computed(() => {
        if (!state.value.tasks) return false
        return state.value.tasks.some(t => t.id.includes('ImportImageTask'))
    })

    // =======================
    // =======Functions=======
    // =======================

    async function init() {
        if(loaded.value) return
        console.log('init')

        const panoptic = usePanopticStore()
        if (!panoptic.isProjectLoaded) return
        const projectId = panoptic.clientState.connectedProject
        if (isNaN(projectId) || projectId < 0) return
        state.value = await apiGetProjectState()
        await loadUiState()

        if (localStorage.getItem('tutorialFinished') != 'true') {
            showTutorial.value = true
        }

        loaded.value = true
        await dataStore.init()
        await actionStore.init()


        // usePanopticStore().showModal(ModalId.TAG, {})
    }

    function importState(st: ProjectState) {
        state.value = st
        actionStore.init()
    }

    function clear() {
        loaded.value = false
        state.value = undefined
        uiState.value = undefined


        dataStore.clear()
        tabStore.clear()
        actionStore.clear()

    }

    async function reload() {
        await nextTick()
        init()
    }

    async function uploadPropFile(file: any) {
        const res = await apiUploadPropFile(file)
        init()
        return res
    }

    async function setPluginParams(plugin: string, params: any) {
        const plugins = await apiSetPluginParams(plugin, params)
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
    }

    async function loadUiState() {
        const res = await apiGetUIData(UIDataKeys.STATE)
        if (res) {
            uiState.value = res

            if (uiState.value.lang) {
                locale.value = uiState.value.lang
            }
        }

        correctUiState()
    }

    function correctUiState() {
        if(!uiState.value) {
            uiState.value = {similarityIntervals: {}, similarityImageSize: 0}
        }
        if (!uiState.value.similarityIntervals) {
            uiState.value.similarityIntervals = {}
        }
        if (!uiState.value.similarityImageSize) {
            uiState.value.similarityImageSize = 70
        }
    }

    async function setLang(lang: string) {
        uiState.value.lang = lang
        await saveUiState()
    }

    async function saveUiState() {
        await apiSetUIData(UIDataKeys.STATE, uiState.value)
    }

    async function updateScoreInterval(funcId: string, interval: ScoreInterval) {
        uiState.value.similarityIntervals[funcId] = deepCopy(interval)
        await saveUiState()
    }

    function importTasks(tasks: TaskState[]) {
        if(!state.value) return
        state.value.tasks = tasks
    }
    function importSettings(settings: ProjectSettings) {
        state.value.settings = settings
    }

    return {
        // variables
        state, uiState,
        // computed
        isImportingImages,
        // functions
        init, clear, importState, importSettings,
        updateSettings,
        uploadPropFile,
        setPluginParams, saveUiState,
        call, importTasks,
        updateScoreInterval,
        // setActionFunctions, hasGroupFunction, hasSimilaryFunction,
        reload,
        showTutorial, setLang, loaded
    }

})
