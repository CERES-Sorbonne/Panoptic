export const deletedID = -999999999
export const deletedName = 'Deleted'

// Thin runtime object — only what's needed for display/identity.
// All other fields (sha1, width, height, folderId, …) live in the column store.
export interface Instance {
    id: number
    imageUrl: string   // base URL — append ?size=N for a specific thumbnail size
    dist?: number      // similarity score, set by search/recommend paths
}

// Full shape as received from the server in stream chunks / commits.
// Used only at import time to populate the column store and index maps.
export interface RawInstance {
    id: number
    name: string
    sha1: string
    ahash: string
    width: number
    height: number
    url: string
    folderId: number
    fileId: number
    extension: string
}

export interface InstanceIndex {
    [id: number]: Instance
}

export type Sha1ToInstances = { [sha1: string]: number[] }

export type Sha1Scores = { [sha1: string]: number }
