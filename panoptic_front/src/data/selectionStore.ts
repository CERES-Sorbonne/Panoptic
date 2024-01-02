import { defineStore } from "pinia"
import { computed, reactive } from "vue"
import { apiCloseProject, apiGetStatus, apiLoadProject } from "./api"
import router from "@/router"

export interface Project {
    path: string
    name: string
}

export interface SelectionStatus {
    isLoaded: boolean
    selectedProject: Project
    projects: Project[]
}

export const useSelectionStore = defineStore('selectionStore', () => {
    const data = reactive({
        status: {} as SelectionStatus,
        init: false
    })

    const state = reactive({
        hasError: false,
        error: ''
    })

    const isProjectLoaded = computed(() => data.status.isLoaded)

    async function init() {
        // console.log('init')
        data.init = false
        data.status = await apiGetStatus()
        data.init = true
        // console.log('end init')
    }

    async function loadProject(path: string) {
        data.status = await apiLoadProject(path)
        router.push('/view')
    }

    async function closeProject() {
        data.status = await apiCloseProject()
        router.push('/')
    }

    init()

    return {
        init, data, state,
        isProjectLoaded,
        loadProject, closeProject
    }
})