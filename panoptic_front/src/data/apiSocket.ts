import { usePanopticStore } from '@/data/panopticStore';
import { io, Socket } from 'socket.io-client';
import { DbCommit, Folder, PanopticClientState, PanopticServerState, PanopticState, ProjectSettings, ProjectState, TaskState, VectorType } from './models';
import { keysToCamel } from '@/utils/utils';
import { useProjectStore } from './projectStore';
import { useDataStore } from './dataStore';

const CONNECTION_ID_KEY = 'panoptic_connection_id';

function getConnectionId(): string | null {
    return localStorage.getItem(CONNECTION_ID_KEY);
}

function setConnectionId(id: string) {
    localStorage.setItem(CONNECTION_ID_KEY, id);
}

class SocketAPI {
    _socket: Socket | null = null

    on(key: string, callback) {
        this._socket.on(key, callback)
    }
    connect() {
        const connectionId = getConnectionId();
        const url = (import.meta as any).env.VITE_API_ROUTE || 'http://localhost:8000';

        this._socket = io(url, {
            path: '/socket.io/',
            transports: ['websocket'],
            auth: {
                connection_id: connectionId
            }
        })

        this._socket.on('connect', () => {
            console.log(`Connected to socket server.`)
        })

        this._socket.on('server_state', (data) => {
            const state = keysToCamel(data) as PanopticServerState
            const panoptic = usePanopticStore()
            panoptic.updateServerState(state)
        })

        this._socket.on('client_state', (data) => {
            const state = keysToCamel(data) as PanopticClientState
            const panoptic = usePanopticStore()
            panoptic.updateClientState(state)
            if (state.connectionId) {
                setConnectionId(state.connectionId)
            }
            console.log(state)
        })

        this._socket.on('disconnect', () => {
            console.log('Disconnected from socket server')
            const panoptic = usePanopticStore()
            panoptic.updateClientState(undefined)
        })

        this._socket.on('project_state', (data: ProjectState) => {
            const project = useProjectStore()
            project.importState(keysToCamel(data))
        })

        this._socket.on('commit', (data) => {
            data = keysToCamel(data) as DbCommit[]
            const dataStore = useDataStore()
            dataStore.applyMultipleCommits(data)
        })

        this._socket.on('tasks', (data) => {
            data = keysToCamel(data) as TaskState[]
            const project = useProjectStore()
            project.importTasks(data)
        })

        this._socket.on('project_settings', (data) => {
            data = keysToCamel(data) as ProjectSettings
            const project = useProjectStore()
            project.importSettings(data)
        })


        this._socket.on('folders', (data: Folder[]) => {
            const dataStore = useDataStore()
            dataStore.importFolders(keysToCamel(data))
        })

        this._socket.on('folders_delete', (data) => {
            location.reload()
        })

        this._socket.on('vector_types', (data: VectorType[]) => {
            const dataStore = useDataStore()
            dataStore.importVectorTypes(keysToCamel(data))
        })
    }

    disconnect() {
        if (this._socket) {
            this._socket.disconnect()
        }
    }
}

export const socketAPI = new SocketAPI()
