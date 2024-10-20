import { defineStore } from "pinia"
import { computed, nextTick, reactive, ref } from "vue"
import { apiAddPlugin, apiCloseProject, apiCreateProject, apiDelPlugin, apiDeleteProject, apiGetPlugins, apiGetStatus, apiImportProject, apiLoadProject } from "./api"
import router from "@/router"
import { useProjectStore } from "./projectStore"
import { ModalId, PluginAddPayload } from "./models"

export interface Project {
    path: string
    name: string
}

export interface PluginKey {
    name: string
    path: string
}

export interface SelectionStatus {
    isLoaded: boolean
    selectedProject: Project
    projects: Project[]
}

export const usePanopticStore = defineStore('panopticStore', () => {
    const project = useProjectStore()

    const data = reactive({
        status: {} as SelectionStatus,
        plugins: [] as PluginKey[],
        init: false
    })

    const state = reactive({
        hasError: false,
        error: ''
    })

    const openModalId = ref(null)
    const modalData = ref(null)

    const isProjectLoaded = computed(() => data.status.isLoaded)

    async function init() {
        // console.log('init')
        data.init = false
        try {
            data.status = await apiGetStatus()
            data.plugins = await apiGetPlugins()
            data.init = true
            // console.log('end init')
            if (data.status.isLoaded) {
                project.init()
            }
        }
        catch { 
            setTimeout(() => init(), 1000)
        }
    }

    async function loadProject(path: string, noCall?: boolean) {
        project.clear()
        if (!noCall) {
            data.status = await apiLoadProject(path)
        }
        await router.push('/view')
        setTimeout(() => project.init(), 10)
    }

    async function closeProject() {
        project.status.loaded = false
        project.clear()
        data.status = await apiCloseProject()
        router.push('/')
    }

    async function deleteProject(path: string) {
        data.status = await apiDeleteProject(path)
    }

    async function createProject(path: string, name: string) {
        path = path.endsWith('\\') ? path : path + '/'
        const projectPath = path + name
        data.status = await apiCreateProject(projectPath, name)
        await loadProject(projectPath, true)
    }

    async function importProject(path: string) {
        data.status = await apiImportProject(path)
        await loadProject(path, true)
    }

    function showModal(modalId: ModalId, data?: any) {
        openModalId.value = modalId
        // openModal.data = data
        modalData.value = data
    }

    function getModalData() {
        return modalData
    }

    function hideModal() {
        openModalId.value = null
        modalData.value = null
    }

    async function addPlugin(plugin: PluginAddPayload) {
        if (!plugin) return
        await apiAddPlugin(plugin)
        data.plugins = await apiGetPlugins()
    }

    async function delPlugin(path) {
        console.log(path)
        await apiDelPlugin(path)
        data.plugins = await apiGetPlugins()
    }

    return {
        init, data, state,
        modalData, hideModal, showModal, openModalId,
        isProjectLoaded,
        loadProject, closeProject, deleteProject, createProject, importProject,
        addPlugin, delPlugin
    }
})