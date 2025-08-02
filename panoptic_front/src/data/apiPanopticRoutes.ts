/**
 * Fichier servant à regrouper les fonctions permettant de communiquer avec le serveur
 */

import axios from 'axios'
import { DirInfo, PluginAddPayload, Notif, NotifType, IngoredPluginPayload, ApiRequestDescription, PanopticState } from './models'
import { PluginKey, usePanopticStore } from './panopticStore'
import { keysToCamel, keysToSnake } from '@/utils/utils'

export const SERVER_PREFIX = (import.meta as any).env.VITE_API_ROUTE

export const panopticApi = axios.create({
    baseURL: SERVER_PREFIX,
});

panopticApi.interceptors.request.use(config => {
    const panoptic = usePanopticStore()
    if (panoptic.clientState.connectionId) {
        config.params = config.params || {};
        config.params.connection_id = panoptic.clientState.connectionId;
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

    // if (url == '/update' || url == '/status') {
    //     if (error.code == 'ERR_NETWORK') {
    //         const panoptic = usePanopticStore()
    //         panoptic.updatePanopticState(undefined)
    //     }
    // } else {
    const notif: Notif = { type: NotifType.ERROR, name: 'BackendError: ' + errorName, message: message, request: req, unexpected: true, traceback: traceback }
    panoptic.notify(notif)
    // }
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


export async function apiGetPanopticState() {
    let res = await panopticApi.get('/panoptic_state')
    return res.data as PanopticState
}

export async function apiLoadProject(path: string) {
    let res = await panopticApi.post('/load', { path })
    return res.data as PanopticState
}

export async function apiCloseProject(projectId: number) {
    let res = await panopticApi.post('/close', { project_id: projectId })
    return res.data as PanopticState
}

export async function apiDeleteProject(path: string) {
    let res = await panopticApi.post('/delete_project', { path })
    return res.data as PanopticState
}

export async function apiCreateProject(path: string, name: string) {
    let res = await panopticApi.post('/create_project', { path, name })
    return res.data as PanopticState
}

export async function apiImportProject(path: string) {
    let res = await panopticApi.post('/import_project', { path })
    return res.data as PanopticState
}

export async function apiGetPlugins() {
    let res = await panopticApi.get('/plugins')
    return keysToCamel(res.data) as PluginKey[]
}

export async function apiAddPlugin(payload: PluginAddPayload) {
    let res = await panopticApi.post('/plugins', payload)
    return res.data as string[]
}

export async function apiDelPlugin(path: string) {
    let res = await panopticApi.delete('/plugins', { params: { path } })
    return res.data as string[]
}

export async function apiUpdatePlugin(data: PluginAddPayload) {
    let res = await panopticApi.post('/plugin/update', data)
    return res.data as boolean
}

export async function apiSetIgnoredPlugin(data: IngoredPluginPayload) {
    const res = await panopticApi.post('/ignored_plugin', keysToSnake(data))
    return keysToCamel(res.data)
}

export async function apiGetVersion() {
    const res = await panopticApi.get('/version')
    return res.data
}

export async function apiGetPackagesInfo() {
    const res = await panopticApi.get('/packages')
    return res.data
}
