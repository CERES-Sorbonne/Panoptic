import { FilterState } from "@/core/FilterManager"
import { GroupState } from "@/core/GroupManager"
import { SortState } from "@/core/SortManager"
import { PropertyOption } from "./property"

// Bump when TabState changes shape: persisted tabs with another version are reset.
export const TAB_MODEL_VERSION = 11

export interface CollectionState {
    autoReload: boolean,
    filterBySelection?: boolean
}

export interface ScoreInterval {
    min: number
    max: number
    maxIsBest: boolean
    values: number[]
    description: string
}

// 'cluster' is the legacy name of the 'group' view, kept so views persisted before the
// rename still resolve. Nothing creates it anymore.
export type ViewType = 'tree' | 'grid' | 'graph' | 'map' | 'reco' | 'group' | 'cluster'

/**
 * Per-view display state (Pillar F). A tab holds a fixed pair of views; the
 * collection pipeline (filter/sort/group) is shared at the tab level, while
 * each view owns only its display options.
 */
export interface ViewState {
    type: ViewType
    imageSize: number
    mapOptions: MapOptions
    recoOptions: RecoOptions
    clusterOptions: ClusterOptions
    // Optional so tabs persisted before the graph view had options still load (the view
    // fills it in on first render). Do not make it required without a TAB_MODEL_VERSION bump.
    graphOptions?: GraphOptions
    showProperties: boolean
    // Which collection (filter/sort/group pipeline) this view renders. Two views
    // may share one collectionId (computed once) or reference different ones.
    collectionId: string
}

// The filter/sort/group pipeline config for one collection. A tab holds a list
// of these; views reference them by id (M4 — multiple collections per tab).
export interface CollectionConfig {
    id: string
    collectionState: CollectionState
    filterState: FilterState
    sortState: SortState
    groupState: GroupState
}

export interface TabState {
    version: number
    id: string
    name: string
    selected?: boolean

    // Collection pipeline config promoted from tab-level to a per-tab list (M4).
    // Views reference an entry by `collectionId`.
    collections: CollectionConfig[]

    // Per-view display state. Fixed pair; view2 is rendered only when splitView.
    views: [ViewState, ViewState]
    splitView: boolean
    splitRatio: number

    // Shared tab-level state
    visibleProperties: { [key: number]: boolean }
    visibleFolders: { [key: number]: boolean }
    selectedFolders: { [key: number]: boolean }
    propertyOptions: { [key: number]: PropertyOption }

    isSelection?: boolean
}

export interface MapOptions {
    showPoints: boolean
    selectedMap: number
    // Border width of the rendered images. Optional so tabs persisted before this existed still
    // load — the map view fills it in on first render (same pattern as graphOptions).
    borderWidth?: number
    // How much the HD preview grows over the hovered point. Optional for the same reason.
    hoverScale?: number
}

// Per-view options for the group recommendation view. Stores which group the
// recommendation grid is currently showing so the selection survives re-renders.
export interface RecoOptions {
    selectedGroupId: number | null
    // View type to restore when the reco view is closed (set when opened from a group).
    previousType: ViewType | null
}

// Per-view options for the cluster view. Stores which cluster group is
// currently shown so the selection survives re-renders.
export interface ClusterOptions {
    selectedGroupId: number | null
}

// Per-view options for the graph view: how the grouped counts are drawn.
export interface GraphOptions {
    chartType: 'line' | 'area' | 'bar'
    stacked: boolean
    // Draw one thumbnail per data point, on top of the marks.
    showThumbnails: boolean
}

export interface TabData {
    id: string
    user_id: string
    state: TabState | null
    selection: number[] | null
}

export interface TabIndex {
    [tabId: string]: TabState
}
