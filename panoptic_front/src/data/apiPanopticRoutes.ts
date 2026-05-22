/**
 * Fichier servant à regrouper les fonctions permettant de communiquer avec le serveur
 */

import axios from 'axios'
import { DirInfo, PluginAddPayload, Notif, NotifType, ApiRequestDescription, ProjectRef, User, PluginType } from './models'
import { PluginKey, usePanopticStore } from './panopticStore'
import { keysToCamel, keysToSnake } from '@/utils/utils'

export const SERVER_PREFIX = (import.meta as any).env.VITE_API_ROUTE

export const panopticApi = axios.create({
    baseURL: SERVER_PREFIX,
});

panopticApi.interceptors.request.use(config => {
    const panoptic = usePanopticStore()
    if (panoptic.connectionState?.connectionId) {
        config.params = config.params || {};
        config.params.connection_id = panoptic.connectionState?.connectionId;
    }
    return config
})

panopticApi.interceptors.response.use(response => response, (error) => {
    const panoptic = usePanopticStore()

    const baseURL: string = error.config.baseURL
    const method = error.config.method
    const url = error.config.url
    const data = error.config.data
    const traceback = error.response?.data?.traceback
    const message = error.response?.data?.message
    const errorName = error.response?.data?.name

    const req: ApiRequestDescription = {
        method, baseURL, url, data
    }

    const notif: Notif = { type: NotifType.ERROR, name: 'BackendError: ' + errorName, message: message, request: req, unexpected: true, traceback: traceback }
    panoptic.notify(notif)
    return Promise.reject(error)
})

export async function apiGetFilesystemInfo() {
    let res = await panopticApi.get('/filesystem/info')
    return res.data as { partitions: DirInfo[], fast: DirInfo[] }
}

export async function apiGetFilesystemLs(path: string) {
    let res = await panopticApi.get('/filesystem/ls' + '/' + path)
    return res.data as { directories: DirInfo[], images: [] }
}

export async function apiGetFilesystemCount(path: string) {
    let res = await panopticApi.get('/filesystem/count' + '/' + path)
    return res.data as { path: string, count: number }
}


export async function apiGetProjects() {
    const res = await panopticApi.get('/projects')
    return keysToCamel(res.data) as ProjectRef[]
}

export async function apiGetUsers() {
    const res = await panopticApi.get('/users')
    return keysToCamel(res.data) as User[]
}

export async function apiGetPlugins() {
    const res = await panopticApi.get('/plugins')
    return (res.data as any[]).map(p => ({
        id: p[0],
        installPath: p[1],
        sourceType: p[2] as PluginType,
        sourcePath: p[3],
    })) as PluginKey[]
}

export async function apiLoadProject(projectId: string) {
    await panopticApi.post('/load', { id: projectId })
}

export async function apiCloseProject(projectId: string) {
    await panopticApi.post('/close', { id: projectId })
}

export async function apiDeleteProject(projectId: string, deleteFiles: boolean) {
    await panopticApi.post('/delete_project', { id: projectId, delete_files: deleteFiles })
}

export async function apiUpdateProject(project: ProjectRef) {
    await panopticApi.post('/update_project', { id: project.id, name: project.name, excluded_plugins: project.excludedPlugins })
}

export async function apiCreateProject(path: string, name: string) {
    await panopticApi.post('/create_project', { path, name })
}

export async function apiImportProject(path: string) {
    await panopticApi.post('/import_project', { path })
}

export async function apiAddPlugin(payload: PluginAddPayload) {
    await panopticApi.post('/plugins', { name: payload.name, source: payload.source, source_type: payload.type })
}

export async function apiDelPlugin(pluginId: string) {
    await panopticApi.delete('/plugins', { params: { plugin_id: pluginId } })
}

export async function apiUpdatePlugin(pluginId: string) {
    let res = await panopticApi.post('/plugin/update', { plugin_id: pluginId })
    return res.data as boolean
}

export async function apiGetVersion() {
    const res = await panopticApi.get('/version')
    return res.data
}

export async function apiGetPackagesInfo() {
    const res = await panopticApi.get('/packages')
    return res.data
}
