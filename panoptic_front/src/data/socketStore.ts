import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { io, Socket } from 'socket.io-client'
import {
    ConnectionState,
    DbCommit,
    Folder,
    PointMap,
    ProjectSettings,
    ProjectState,
    TaskState,
} from './models'
import { keysToCamel } from '@/utils/utils'
import { usePanopticStore } from '@/data/panopticStore'
import { useProjectStore } from './projectStore'
import { useDataStore } from './dataStore'
import { useMediaStore } from './mediaStore'
import { useColumnStore } from './columnStore'
import { apiGetDelta, mapVectorType } from './apiProjectRoutes'

const CONNECTION_ID_KEY = 'panoptic_connection_id'

function getConnectionId(): string | null {
    return localStorage.getItem(CONNECTION_ID_KEY)
}

function setConnectionId(id: string) {
    localStorage.setItem(CONNECTION_ID_KEY, id)
}

export const useSocketStore = defineStore('socketStore', () => {
    let socket: Socket = null
    const loaded = ref(false)

    let isSyncing = false
    let pendingUpdate = false

    async function processDelta() {
        const dataStore = useDataStore()
        if (!dataStore.isLoaded || isSyncing) return
        isSyncing = true
        pendingUpdate = false
        try {
            const fullPropIds = useColumnStore().getFullyLoadedPropIds()
            const delta = await apiGetDelta(dataStore.lastSequence, { fullPropIds, pointPropIds: [], instanceIds: [] })
            await dataStore.applyDelta(delta)
        } finally {
            isSyncing = false
            if (pendingUpdate) processDelta()
        }
    }

    // Flush any update that arrived while the initial stream load was still in progress
    watch(() => useDataStore().isLoaded, (isLoaded) => {
        if (isLoaded && pendingUpdate) processDelta()
    })

    function init() {
        const connectionId = getConnectionId()
        const url = (import.meta as any).env.VITE_API_ROUTE
        socket = io(url, {
            path: '/socket.io/',
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 1000,
            timeout: 60000,
            transports: ['websocket'],
            auth: {
                connection_id: connectionId
            }
        })

        socket.on('connect', () => {
            usePanopticStore().setConnect()
        })

        socket.on("connect_error", (err) => {
            usePanopticStore().setFailedConnect()
        });

        socket.on('update_projects', () => {
            usePanopticStore().fetchProjects()
        })

        socket.on('update_plugins', () => {
            usePanopticStore().fetchPlugins()
        })

        socket.on('update_users', () => {
            usePanopticStore().fetchUsers()
        })

        socket.on('connection_state', (data) => {
            const state = keysToCamel(data) as ConnectionState
            usePanopticStore().updateConnectionState(state)
            if (state.connectionId) {
                setConnectionId(state.connectionId)
            }
        })

        socket.on('disconnect', () => {
            usePanopticStore().updateConnectionState(undefined)
        })

        socket.on('project_state', (data: ProjectState) => {
            useProjectStore().importState(keysToCamel(data))
        })

        socket.on('db_update', () => {
            pendingUpdate = true
            processDelta()
        })

        socket.on('tasks', (data) => {
            const payload = keysToCamel(data) as { projectId: string, tasks: TaskState[] }
            useProjectStore().importTasks(payload.tasks ?? [])
        })

        socket.on('project_settings', (data) => {
            const settings = keysToCamel(data) as ProjectSettings
            useProjectStore().importSettings(settings)
        })

        socket.on('folders', (data: Folder[]) => {
            const store = useDataStore()
            store.importFolders(keysToCamel(data))
            store.fetchFolderCounts()
        })

        socket.on('folders_delete', () => {
            location.reload()
        })

        socket.on('vector_types', (data: any[]) => {
            useMediaStore().importVectorTypes(data.map(mapVectorType))
        })

        socket.on('maps', (mapList: PointMap[]) => {
            useMediaStore().loadMaps(mapList)
        })

        socket.on('atlas', () => useMediaStore().loadAtlas())

        socket.on('plugins_info', () => {
            useProjectStore().fetchPluginsInfo()
        })
    }

    function close() {
        if (socket) {
            socket.disconnect()
        }
    }

    function on(event: string, callback: (...args: any[]) => void) {
        if (socket) {
            socket.on(event, callback)
        }
    }

    function connectUser(userId: number) {
        socket.emit('connect_user', userId)
    }

    function disconnectUser() {
        socket.emit('disconnect_user')
    }

    return {
        init,
        close,
        on,
        connectUser,
        disconnectUser
    }
})
