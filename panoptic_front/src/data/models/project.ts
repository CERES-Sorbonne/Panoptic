import { DbCommit } from "./commit"
import { PluginDescription } from "./plugin"
import { FileValuesArray, ImageValuesArray, InstanceValuesArray } from "./property"
import { ScoreInterval } from "./tab"

// Migration des projets d'une ancienne version de Panoptic (0.x)
export interface LegacyRegistry {
    path: string
    shape: string
    projects: number
    plugins: string[]
    problem?: string
}

export interface LegacyProject {
    legacyPath: string
    name: string
    registry: string
    shape?: string
    recordedVersion?: number
    instanceCount?: number
    exists: boolean
    status?: string
    problem?: string
    migratedTo?: string
    suggestedPath: string
    plugins: string[]
    dbSize?: number
}

export interface LegacyScan {
    scanned: boolean
    skipped: boolean
    reason?: string
    registries: LegacyRegistry[]
    projects: LegacyProject[]
}

export interface LegacyMigrationRun {
    id: string
    legacyPath: string
    destPath: string
    name: string
    status: 'pending' | 'running' | 'done' | 'failed'
    stage?: string
    stageIndex: number
    stageCount: number
    detail?: string
    error?: string
    warnings: string[]
    plugins: string[]
    reportPath?: string
    projectId?: string
}

export interface TaskState {
    id: string
    key: string
    name: string
    total: number
    done: number
    failed: number
    remain: number
    running: boolean
    finished: boolean
    // A stop was requested. While `running` is still true the task is stopping.
    cancelled: boolean
    // Plugin that queued the task, null for core tasks
    owner?: string | null
    step?: string | null
    detail?: string | null
    workers?: number | null
    started_at?: number | null
    elapsed?: number | null
    rate?: number | null
    eta_seconds?: number | null
}

export interface ProjectSettings {
    imageSmallSize: number
    imageMediumSize: number
    imageLargeSize: number

    saveImageSmall: boolean
    saveImageMedium: boolean
    saveImageLarge: boolean

    saveFileRaw: boolean
}

export interface ImageType {
    id: number
    name: string
    format: string
    width: number | null
    height: number | null
    autoGen: boolean
}

export interface ImageStats {
    counts: { [typeId: number]: number }
    sha1Count: number
}

export interface UiState {
    activeTab?: string
    lang?: string
    similarityIntervals: { [key: string]: ScoreInterval },
    similarityImageSize: number
}

export interface LoadResult {
    chunk?: DbCommit
    state: LoadState
    instanceValues?: InstanceValuesArray[]
    imageValues?: ImageValuesArray[]
    fileValues?: FileValuesArray[]
}

export interface LoadState {
    finishedProperty?: boolean
    finishedInstance?: boolean
    finishedTags?: boolean
    finishedInstanceValues?: boolean
    finishedImageValues?: boolean
    finishedFileValues?: boolean
    finishedPropertyGroups?: boolean

    counterInstance: number
    counterInstanceValue: number
    counterImageValue: number
    counterFileValue: number

    maxInstance: number
    maxInstanceValue: number
    maxImageValue: number
    maxFileValue: number

    maxSequence: number
}

export interface ProjectId {
    id: number;
    name?: string;
    path?: string;
}

export interface ProjectRef extends ProjectId {
    loaded: boolean
    excludedPlugins: string[]
    // 'outdated': written by an older version, can be converted. 'incompatible' / 'missing': cannot be opened
    status: 'ok' | 'outdated' | 'incompatible' | 'missing'
    problem?: string
}

export interface User {
    id: string
    name: string
}

export interface UserState extends User {
    connectedTo?: string
}

export interface ConnectionState {
    connectionId: string
    user: UserState
    connectedProject?: string
}

export interface ProjectState {
    id: string
    name: string
    path: string
    tasks: TaskState[]
    plugins: PluginDescription[]
    settings: ProjectSettings
}
