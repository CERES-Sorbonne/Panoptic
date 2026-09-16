export interface FileSourceSyncStatus {
    lastSyncedAt: string
    status: 'success' | 'partial'
    folderCount: number
    fileCount: number
    importedCount: number
    failedCount: number
}

export interface FileSource {
    id: number
    dtype: string
    name: string | null
    rootUrl: string | null
    metadata: Record<string, any> | null
    syncStatus: FileSourceSyncStatus | null
}

export interface FileSourceIndex {
    [id: number]: FileSource
}

export interface SourceNode {
    id: number
    name: string
    type: 'file_source'
    children: Folder[]
}

export interface FolderNode {
    id: number
    name: string
    type: 'folder'
    children: Folder[]
}

export type RootNode = SourceNode | FolderNode

export interface Folder {
    id: number
    name: string
    path: string
    parent: number
    sourceId?: number // file source this root folder belongs to (camelCased from source_id)
    children: Array<Folder>
    show?: boolean // frontend variable to know if exanded in view or not
    selected?: boolean // frontend variable for smart folder filter
    count?: number
}

export interface FolderIndex {
    [id: number]: Folder
}

export interface DirInfo {
    path: string,
    name: string,
    images?: number
    images_url?: string,
    isProject: boolean
}
