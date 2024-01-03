import { defineStore } from "pinia"
import { computed, nextTick, reactive } from "vue"
import { apiCloseProject, apiCreateProject, apiDeleteProject, apiGetStatus, apiImportProject, apiLoadProject } from "./api"
import router from "@/router"
import { useProjectStore } from "./projectStore"
import { ModalId } from "./models"

export interface Project {
    path: string
    name: string
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
        init: false
    })

    const state = reactive({
        hasError: false,
        error: ''
    })

    const openModal = reactive({ id: undefined, data: undefined })

    const isProjectLoaded = computed(() => data.status.isLoaded)

    async function init() {
        // console.log('init')
        data.init = false
        data.status = await apiGetStatus()
        data.init = true
        // console.log('end init')
        if(data.status.isLoaded) {
            project.init()
        }
    }

    async function loadProject(path: string) {
        data.status = await apiLoadProject(path)
        router.push('/view')
        project.clear()
        setTimeout(() => project.init(), 10)
    }

    async function closeProject() {
        data.status = await apiCloseProject()
        router.push('/')
    }

    async function deleteProject(path:string) {
        data.status = await apiDeleteProject(path)
    }

    async function createProject(path: string, name: string) {
        data.status = await apiCreateProject(path + '/' + name, name)
        await loadProject(path)
    }

    async function importProject(path: string) {
        data.status = await apiImportProject(path)
        await loadProject(path)
    }

    function showModal(modalId: ModalId, data?: any) {
        openModal.id = modalId
        openModal.data = data
    }

    function hideModal() {
        Object.assign(openModal, { id: undefined, data: undefined })
    }

    return {
        init, data, state,
        openModal, hideModal, showModal,
        isProjectLoaded,
        loadProject, closeProject, deleteProject, createProject, importProject
    }
})