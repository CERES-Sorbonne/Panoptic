import { ref } from 'vue'
import { defineStore } from 'pinia'
import { io, Socket } from 'socket.io-client'
import {
    DbCommit,
    Folder,
    PanopticClientState,
    PanopticServerState,
    PointMap,
    ProjectSettings,
    ProjectState,
    TaskState,
    VectorType
} from './models'
import { keysToCamel } from '@/utils/utils'
import { usePanopticStore } from '@/data/panopticStore'
import { useProjectStore } from './projectStore'
import { useDataStore } from './dataStore'

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

    function init() {
        const connectionId = getConnectionId()
        const url = (import.meta as any).env.VITE_API_ROUTE || 'http://localhost:8000'
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
            // console.log('Connected to socket server.')
        })

        socket.on('server_state', (data) => {
            const state = keysToCamel(data) as PanopticServerState
            usePanopticStore().updateServerState(state)
        })

        socket.on('client_state', (data) => {
            const state = keysToCamel(data) as PanopticClientState
            // console.log(state)
            usePanopticStore().updateClientState(state)
            if (state.connectionId) {
                setConnectionId(state.connectionId)
            }
        })

        socket.on('disconnect', () => {
            usePanopticStore().updateClientState(undefined)
        })

        socket.on('project_state', (data: ProjectState) => {
            useProjectStore().importState(keysToCamel(data))
        })

        socket.on('commit', (data) => {
            const commits = keysToCamel(data) as DbCommit[]
            useDataStore().applyMultipleCommits(commits)
        })

        socket.on('tasks', (data) => {
            const tasks = keysToCamel(data) as TaskState[]
            useProjectStore().importTasks(tasks)
        })

        socket.on('project_settings', (data) => {
            const settings = keysToCamel(data) as ProjectSettings
            useProjectStore().importSettings(settings)
        })

        socket.on('folders', (data: Folder[]) => {
            useDataStore().importFolders(keysToCamel(data))
        })

        socket.on('folders_delete', () => {
            location.reload()
        })

        socket.on('vector_types', (data: VectorType[]) => {
            useDataStore().importVectorTypes(keysToCamel(data))
        })

        socket.on('maps', (mapList: PointMap[]) => {
            useDataStore().loadMaps(mapList)
        })

        socket.on('atlas', () => useDataStore().loadAtlas())
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
