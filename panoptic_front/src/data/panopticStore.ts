import { defineStore } from "pinia"
import { computed, ref } from "vue"
import {
    apiAddPlugin,
    apiCloseProject,
    apiConnectUser,
    apiCreateProject,
    apiCreateUser,
    apiDelPlugin,
    apiDeleteProject,
    apiDeleteUser,
    apiDisconnectUser,
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
import { useSocketStore } from "./socketStore"


const LAST_USER_KEY = 'panoptic_last_user_id'
const DEFAULT_USER_ID = 'default'

let idCounter = 0

export interface Project {
    path: string
    name: string
}

export interface PluginKey {
    id: string
    sourcePath: string
    sourceType: PluginType
    installPath?: string
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
    const hasAttemptedUserReconnect = ref(false)

    const isConnected = computed(() => connectionState.value != undefined)
    const isUserValid = computed(() => isConnected.value)
    const isProjectLoaded = computed(() => isConnected.value && !!connectionState.value.connectedProject)

    function init() {
        console.log('[panopticStore] Initializing socket connection')
        const socket = useSocketStore()
        socket.init()
    }

    // ---------------------------------------------------------------
    // Data fetches — called on socket trigger or after mutations
    // ---------------------------------------------------------------

    async function fetchProjects() {
        projects.value = await apiGetProjects()
        projectsLoaded.value = true
    }

    async function fetchPlugins() {
        plugins.value = await apiGetPlugins()
        console.log(plugins.value)
    }

    async function fetchUsers() {
        users.value = await apiGetUsers()
    }

    async function createUser(name: string) {
        await apiCreateUser(name)
        await fetchUsers()
    }

    async function deleteUser(userId: string) {
        await apiDeleteUser(userId)
        await fetchUsers()
    }

    async function connectUser(userId: string) {
        await apiConnectUser(userId)
        localStorage.setItem(LAST_USER_KEY, userId)
    }

    async function disconnectUser() {
        await apiDisconnectUser()
        localStorage.removeItem(LAST_USER_KEY)
    }

    async function tryReconnectUser(state: ConnectionState) {
        if (hasAttemptedUserReconnect.value) return
        hasAttemptedUserReconnect.value = true

        const savedId = localStorage.getItem(LAST_USER_KEY)
        if (!savedId || savedId === DEFAULT_USER_ID) return
        if (state.user?.id && state.user.id !== DEFAULT_USER_ID) return

        try {
            await apiConnectUser(savedId)
        } catch {
            localStorage.removeItem(LAST_USER_KEY)
        }
    }

    async function fetchVersion() {
        const res = await apiGetVersion()
        if (res?.version) version.value = res.version
    }

    // ---------------------------------------------------------------
    // Connection state — pushed directly by socket connection_state event
    // ---------------------------------------------------------------

    function updateConnectionState(state: ConnectionState | undefined) {
        console.log('[panopticStore] updateConnectionState called with:', state)
        connectionState.value = state
        const pendingReconnect = !hasAttemptedUserReconnect.value && !!localStorage.getItem(LAST_USER_KEY)
        if (state?.connectedProject) {
            console.log('[panopticStore] Project loaded, routing to /view')
            router.push('/view')
        } else if (state && !pendingReconnect) {
            console.log('[panopticStore] No project, routing to /')
            router.push('/')
        }
    }

    // ---------------------------------------------------------------
    // Project management
    // ---------------------------------------------------------------

    async function loadProject(projectId: string) {
        project.clear()
        await apiLoadProject(projectId)
    }

    async function closeProject(projectId: string) {
        notifs.value = []
        project.clear()
        await apiCloseProject(projectId)
    }

    async function deleteProject(projectId: string) {
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
        fetchProjects, fetchPlugins, fetchUsers, createUser, deleteUser, connectUser, disconnectUser, tryReconnectUser,
        addPlugin, delPlugin, updatePlugin,
        notifs, clearNotif, notify, delNotif,
        getPackagesInfo,
        updateConnectionState, setConnect, setFailedConnect
    }
})
