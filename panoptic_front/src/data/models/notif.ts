import { ActionContext, ExecuteActionPayload } from "./plugin"
import { Property } from "./property"

export enum NotifType {
    DEBUG = 'debug',
    INFO = 'info',
    WARNING = 'warning',
    ERROR = 'error'
}

export interface NotifFunction extends ExecuteActionPayload {
    message: string
    context: ActionContext
}

export interface ApiRequestDescription {
    method: string,
    baseURL: string,
    url: string,
    data: any
}

export interface Notif {
    type?: NotifType

    id?: number
    createdAt?: Date
    receivedAt?: Date
    name?: string
    message?: string
    data?: any

    functions?: NotifFunction[]

    read?: boolean
    unexpected?: boolean
    traceback?: string[]

    request?: ApiRequestDescription
}

export enum UploadError {
    no_key = 'no_key',
    invalid_type = 'invalid_type'
}

export interface UploadConfirm {
    key: string
    colToProperty: { [key: number]: Property }
    errors: { [key: number]: UploadError }
}

export interface ImportVerify {
    missingRows: number[]
    newInstancesCount: number[]
}
