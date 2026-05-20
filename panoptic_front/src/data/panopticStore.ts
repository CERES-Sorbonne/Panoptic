import { defineStore } from "pinia"
import { computed, ref } from "vue"
import {
    apiAddPlugin,
    apiCloseProject,
    apiCreateProject,
    apiDelPlugin,
    apiDeleteProject,
    apiGetPlugins,
    apiGetProjects,
    apiGetUsers,
    apiGetVersion,
    apiImportProject,
    apiLoadProject,
    apiUpdatePlugin,
    apiGetPackagesInfo,
    apiUpdateProject
} from "./apiPanopticRoutes"
import router from "@/router"
import { useProjectStore } from "./projectStore"
import { ConnectionState, ModalId, Notif, PluginAddPayload, PluginType, ProjectRef, User } from "./models"
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
    const project = useProjectStore()

    const projects = ref<ProjectRef[]>([])
    const plugins = ref<PluginKey[]>([])
    const users = ref<User[]>([])
    const version = ref<string>('')

    const connectionState = ref<ConnectionState>()
    const projectsLoaded = ref(false)

    // TODO: remove openModalId/modalData — use modalStore directly
    const openModalId = ref(null)
    const modalData = ref(null)
    const failedConnected = ref(false)

    const notifs = ref<Notif[]>([])

    const isConnected = computed(() => connectionState.value != undefined)
    const isUserValid = computed(() => isConnected.value)
    const isProjectLoaded = computed(() => isConnected.value && !!connectionState.value.connectedProject)

    function init() {}

    // ---------------------------------------------------------------
    // Data fetches — called on socket trigger or after mutations
    // ---------------------------------------------------------------

    async function fetchProjects() {
        projects.value = await apiGetProjects()
        projectsLoaded.value = true
    }

    async function fetchPlugins() {
        plugins.value = await apiGetPlugins()
    }

    async function fetchUsers() {
        users.value = await apiGetUsers()
    }

    async function fetchVersion() {
        const res = await apiGetVersion()
        if (res?.version) version.value = res.version
    }

    // ---------------------------------------------------------------
    // Connection state — pushed directly by socket connection_state event
    // ---------------------------------------------------------------

    function updateConnectionState(state: ConnectionState | undefined) {
        connectionState.value = state
        if (state?.connectedProject) {
            router.push('/view')
        } else if (state) {
            router.push('/')
        }
    }

    // ---------------------------------------------------------------
    // Project management
    // ---------------------------------------------------------------

    async function loadProject(projectId: number) {
        project.clear()
        await apiLoadProject(projectId)
    }

    async function closeProject(projectId: number) {
        notifs.value = []
        project.clear()
        await apiCloseProject(projectId)
    }

    async function deleteProject(projectId: number) {
        const deleteFiles: boolean = window.confirm("Would you also like to delete the associated files?")
        await apiDeleteProject(projectId, deleteFiles)
        await fetchProjects()
    }

    async function createProject(path: string, name: string) {
        path = path.endsWith('\\') ? path : path + '/'
        const projectPath = path + name
        await apiCreateProject(projectPath, name)
    }

    async function importProject(path: string) {
        await apiImportProject(path)
    }

    async function updateProject(proj: ProjectRef) {
        await apiUpdateProject(proj)
        await fetchProjects()
    }

    // ---------------------------------------------------------------
    // Plugin management
    // ---------------------------------------------------------------

    async function addPlugin(plugin: PluginAddPayload) {
        if (!plugin) return
        await apiAddPlugin(plugin)
        await fetchPlugins()
    }

    async function delPlugin(name: string) {
        await apiDelPlugin(name)
        await fetchPlugins()
    }

    async function updatePlugin(name: string) {
        const res = await apiUpdatePlugin(name)
        await fetchPlugins()
        return res
    }

    // ---------------------------------------------------------------
    // Modal system
    // ---------------------------------------------------------------

    function showModal(modalId: ModalId, data?: any) {
        openModalId.value = modalId
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

    // ---------------------------------------------------------------
    // Notifications
    // ---------------------------------------------------------------

    function clearNotif() {
        notifs.value = []
    }

    function notify(notifList: Notif | Notif[]) {
        if (!Array.isArray(notifList)) {
            notifList = [notifList]
        }
        for (const notif of notifList) {
            notif.id = getId()
            notif.receivedAt = new Date()
            notifs.value.push(notif)
        }
        showModal(ModalId.NOTIF, notifList[notifList.length - 1].id)
    }

    function delNotif(id: number) {
        const index = notifs.value.findIndex(n => n.id == id)
        if (index < 0) return
        notifs.value.splice(index, 1)
    }

    function getId() {
        idCounter += 1
        return idCounter
    }

    // ---------------------------------------------------------------
    // Connection helpers (called by socketStore)
    // ---------------------------------------------------------------

    function setConnect() {
        failedConnected.value = false
    }

    function setFailedConnect() {
        failedConnected.value = true
    }

    async function getPackagesInfo() {
        return apiGetPackagesInfo()
    }

    return {
        init, isConnected, connectionState, projectsLoaded, failedConnected,
        projects, plugins, users, version,
        modalData, hideModal, showModal, openModalId, isUserValid,
        isProjectLoaded,
        loadProject, closeProject, deleteProject, createProject, importProject, updateProject,
        fetchProjects, fetchPlugins, fetchUsers,
        addPlugin, delPlugin, updatePlugin,
        notifs, clearNotif, notify, delNotif,
        getPackagesInfo,
        updateConnectionState, setConnect, setFailedConnect
    }
})
