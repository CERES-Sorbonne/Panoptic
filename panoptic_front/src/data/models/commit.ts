import { Instance, RawInstance } from "./instance"
import { FunctionDescription, PluginDescription } from "./plugin"
import { TaskState } from "./project"
import { FilePropertyValue, ImagePropertyValue, InstancePropertyValue, Property, PropertyGroup } from "./property"
import { Tag } from "./tag"

export interface StatusUpdate {
    tasks: TaskState[];
    // updated_images: Image[];
    pluginLoaded?: boolean
    update: UpdateCounter
}

export interface SyncResult {
    newImageCount: number
    missingImages: Instance[]
}

export interface UpdateCounter {
    action: number;
    image: number;
    vectorType: number;
}

export interface DbCommit {
    emptyInstances?: number[]
    emptyPropertyGroups?: number[]
    emptyProperties?: number[]
    emptyTags?: number[]
    emptyInstanceValues?: InstancePropertyValue[]
    emptyImageValues?: ImagePropertyValue[]
    emptyFileValues?: FilePropertyValue[]

    instances?: RawInstance[]
    propertyGroups?: PropertyGroup[]
    properties?: Property[]
    tags?: Tag[]
    instanceValues?: InstancePropertyValue[]
    imageValues?: ImagePropertyValue[]
    fileValues?: FilePropertyValue[]

    undo?: boolean
    history?: CommitHistory
}

export interface CommitStat {
    id: number
    timestamp: string
    author?: string
    source: string        // 'ui', 'import', 'system', or a plugin name — labels authorless commits
    // False for a commit authored by somebody else (only ever present with scope='all'):
    // it is shown in the history dropdown but can never be undone by this user.
    own: boolean
    tags: number
    values: number
}

// Lightweight commit metadata for the Data settings commit timeline (distinct from the
// DbCommit delta blob). Mirrors the backend Commit struct.
export interface DbCommitInfo {
    id: number
    groupId?: number
    source: string
    timestamp: string
    active: number        // 1 = enabled, 0 = disabled (undone)
    author?: string
}

export interface CommitHistory {
    undo: CommitStat[]
    redo: CommitStat[]
}

export interface Update {
    commits?: DbCommit[]
    plugins?: PluginDescription[]
    actions?: FunctionDescription[]
    status?: StatusUpdate
}
