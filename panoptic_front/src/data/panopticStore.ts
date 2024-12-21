import { defineStore } from "pinia"
import { computed, nextTick, reactive, ref } from "vue"
import { apiAddPlugin, apiCloseProject, apiCreateProject, apiDelPlugin, apiDeleteProject, apiGetPlugins, apiGetStatus, apiImportProject, apiLoadProject, apiSetIgnoredPlugin } from "./api"
import router from "@/router"
import { useProjectStore } from "./projectStore"
import { IgnoredPlugins, ModalId, Notif, NotifType, PluginAddPayload } from "./models"
import { useModalStore } from "./modalStore"

let idCounter = 0

export interface Project {
    path: string
    name: string
}

export interface PluginKey {
    name: string
    path: string
    sourceUrl?: string
}

export interface SelectionStatus {
    isLoaded: boolean
    selectedProject: Project
    projects: Project[]
    ignoredPlugins: IgnoredPlugins
}

export const usePanopticStore = defineStore('panopticStore', () => {
    const project = useProjectStore()

    const data = reactive({
        status: {} as SelectionStatus,
        plugins: [] as PluginKey[],
        init: false,
    })

    const state = reactive({
        hasError: false,
        error: ''
    })

    const openModalId = ref(null)
    const modalData = ref(null)

    const notifs = ref<Notif[]>([])

    const isProjectLoaded = computed(() => data.status.isLoaded)

    async function init() {
        data.init = false
        try {
            data.status = await apiGetStatus()
            data.plugins = await apiGetPlugins()
            data.init = true
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
        // setTimeout(() => project.init(), 10)
        await nextTick()
        project.init()
    }

    async function closeProject() {
        project.status.loaded = false
        project.clear()
        notifs.value = []
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
        const modal = useModalStore()
        modal.openModal(modalId, data)
    }

    function getModalData() {
        return modalData
    }

    function hideModal(id: ModalId) {
        openModalId.value = null
        modalData.value = null

        const modal = useModalStore()
        modal.closeModal(id)
    }

    async function addPlugin(plugin: PluginAddPayload) {
        if (!plugin) return
        await apiAddPlugin(plugin)
        data.plugins = await apiGetPlugins()
    }

    async function delPlugin(path) {
        await apiDelPlugin(path)
        data.plugins = await apiGetPlugins()
    }

    function clearNotif() {
        notifs.value = []
    }

    function notify(notifList: Notif | Notif[]) {
        if(!Array.isArray(notifList)) {
            notifList = [notifList]
        }
        for(let notif of notifList) {
            notif.id = getId()
            notif.receivedAt = new Date()
            notifs.value.push(notif)
        }

        showModal(ModalId.NOTIF, notifList[notifList.length-1].id)
    }

    function delNotif(id: number) {
        const index = notifs.value.findIndex(n => n.id == id)
        console.log(index)
        if(index < 0) return
        notifs.value.splice(index, 1)
    }

    function getId() {
        idCounter += 1
        return idCounter
    }

    async function updateIgnorePlugin(project, plugin, value) {
        const res = await apiSetIgnoredPlugin({project, plugin, value})
        data.status.ignoredPlugins = res
    }

    return {
        init, data, state,
        modalData, hideModal, showModal, openModalId,
        isProjectLoaded,
        loadProject, closeProject, deleteProject, createProject, importProject, updateIgnorePlugin,
        addPlugin, delPlugin,
        notifs, clearNotif, notify, delNotif
    }
})