import { defineStore } from "pinia"
import { computed, ref } from "vue"
import {
    apiAddPlugin,
    apiCloseProject,
    apiCreateProject,
    apiDelPlugin,
    apiDeleteProject,
    apiImportProject,
    apiLoadProject,
    apiSetIgnoredPlugin,
    apiUpdatePlugin,
    apiGetPackagesInfo,
    apiGetPanopticState,
    apiGetPlugins
} from "./apiPanopticRoutes"
import router from "@/router"
import { useProjectStore } from "./projectStore"
import { ModalId, Notif, PanopticClientState, PanopticServerState, PluginAddPayload, PluginType } from "./models"
import { useModalStore } from "./modalStore"


let idCounter = 0

export interface Project {
    path: string
    name: string
}

export interface PluginKey {
    name: string
    source: string
    type: PluginType
    path?: string
}


export const usePanopticStore = defineStore('panopticStore', () => {
    let _init = false
    const project = useProjectStore()

    const serverState = ref<PanopticServerState>()
    const clientState = ref<PanopticClientState>()

    // TODO: remove this
    const openModalId = ref(null)
    const modalData = ref(null)

    const notifs = ref<Notif[]>([])

    const isConnected = computed(() => {
        if(serverState.value == undefined || clientState.value == undefined) return false
        return true
    })

    const isUserValid = computed(() => isConnected.value && (!serverState.value.askUser || clientState.value.user))

    const isProjectLoaded = computed(() => isConnected.value && clientState.value.connectedProject)


    function init() {
        _init = true
    }

    function updateClientState(state: PanopticClientState) {
        clientState.value = state
        if(state.connectedProject) {
            router.push('/view')
        }
        else {
            router.push('/')
        }
    }

    function updateServerState(state: PanopticServerState) {
        serverState.value = state
    }

    async function getPackagesInfo(){
        return apiGetPackagesInfo()
    }

    async function loadProject(path: string, noCall?: boolean) {
        project.clear()
        await apiLoadProject(path)
    }

    async function closeProject(projectId: number) {
        notifs.value = []
        await apiCloseProject(projectId)
    }

    async function deleteProject(path: string) {
        const state = await apiDeleteProject(path)
    }

    async function createProject(path: string, name: string) {
        path = path.endsWith('\\') ? path : path + '/'
        const projectPath = path + name
        const state = await apiCreateProject(projectPath, name)
        await loadProject(projectPath, true)
    }

    async function importProject(path: string) {
        const state = await apiImportProject(path)
        await loadProject(path)
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
        serverState.value.plugins = await apiGetPlugins()
    }

    async function delPlugin(name: string) {
        await apiDelPlugin(name)
        serverState.value.plugins = await apiGetPlugins()
    }

    async function updatePlugin(name: string) {
       const res = await apiUpdatePlugin(name) 
       return res
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
        await apiSetIgnoredPlugin({project, plugin, value})
    }

    return {
        init, isConnected, clientState, serverState,
        modalData, hideModal, showModal, openModalId, isUserValid,
        isProjectLoaded,
        loadProject, closeProject, deleteProject, createProject, importProject, updateIgnorePlugin,
        addPlugin, delPlugin, updatePlugin,
        notifs, clearNotif, notify, delNotif,
        getPackagesInfo,
        updateClientState, updateServerState
    }
})