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
            console.log('[delta] processDelta fetch', { since: dataStore.lastSequence, fullPropIds })
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
        console.log('[socketStore] Initializing socket with url:', url)
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
            console.log('[socketStore] Socket connected')
            usePanopticStore().setConnect()
        })

        socket.on("connect_error", (err) => {
            console.error('[socketStore] Socket connection error:', err)
            usePanopticStore().setFailedConnect()
        });

        socket.on('disconnect', () => {
            console.log('[socketStore] Socket disconnected')
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

        socket.on('connection_state', async (data) => {
            console.log('[socketStore] Received connection_state:', data)
            const state = keysToCamel(data) as ConnectionState
            const panoptic = usePanopticStore()
            panoptic.updateConnectionState(state)
            if (state.connectionId) {
                setConnectionId(state.connectionId)
            }
            await panoptic.tryReconnectUser(state)
        })

        socket.on('disconnect', () => {
            usePanopticStore().updateConnectionState(undefined)
        })

        socket.on('project_state', (data: ProjectState) => {
            useProjectStore().importState(keysToCamel(data))
        })

        socket.on('db_update', () => {
            console.log('[delta] socket db_update received')
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

    return {
        init,
        close,
        on,
    }
})
