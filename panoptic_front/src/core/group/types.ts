/**
 * Shared Group types. Kept dependency-free (only leaf modules + @/data) so every other
 * group/* module and the GroupManager class import from here, never the reverse — the
 * import graph stays a DAG.
 */
import { DateUnit, GroupScoreList, PropertyValue, Score } from "@/data/models";
import { SortOption } from "../SortManager";
import { PileData } from "../sha1Piles";
import { GroupValueIndex } from "./valueIndex";
import type { GroupIterator } from "./GroupIterator";

export enum GroupType {
    All = 'all',
    Selection = 'selection',
    Property = 'property',
    Cluster = 'cluster'
}

export interface GroupState {
    groupBy: number[],
    options: { [groupId: number]: GroupOption },
    sha1Mode: boolean
}

export interface Group {
    id: number
    key: any[]
    name?: string
    slots: number[]
    type: GroupType
    subGroupType?: GroupType
    dirty?: boolean

    parent?: Group
    parentIdx?: number
    children: Group[]
    depth: number
    order: number

    // Offsets into GroupTree.orderedIds — set by buildOrdinalRanges() after each rebuild.
    start: number
    end: number

    score?: Score
    scores?: GroupScoreList

    view: GroupView
    meta: GroupMetaData
    isSha1Group?: boolean
    // Leftover "Unclustered" bucket that receives images from deleted sibling groups.
    isLeftover?: boolean
}

export interface GroupView {
    selected: boolean
    closed: boolean
}

export interface ClusterParam {
    name: string
    label?: string
    value: any
}

export interface GroupMetaData {
    propertyValues?: PropertyValue[]
    score?: number
    clusterFunction?: string
    clusterInputs?: ClusterParam[]
}

export interface GroupIndex { [key: string]: Group }

export interface GroupTree {
    root: Group
    index: GroupIndex
    imageToGroups: Map<number, Set<number>>  // instanceId → Set<leafGroupId>
    valueIndex: GroupValueIndex               // persistent across rebuilds — stable group IDs
    orderedIds: Int32Array                    // instance IDs in DFS display order
    cacheStale: boolean
    // sha1Mode display overlay — non-destructive. Keyed by leaf group id; present only
    // for leaves that actually contain duplicate-sha1 instances. Absent leaves render flat.
    pileIndex: Map<number, PileData>
}

export enum GroupSortType {
    Size,
    Property
}

export interface GroupOption extends SortOption {
    type?: GroupSortType
    stepSize?: number
    stepUnit?: DateUnit
}

export type SelectedImages = { [imageId: number]: boolean }

// ── Host interfaces (cycle-breaking) ────────────────────────────────────────
// Iterators and structural ops depend on these narrow structural contracts, not on the
// concrete GroupManager class, so those modules never import GroupManager.

export interface IteratorHost {
    result: GroupTree
    registerIterator(it: GroupIterator): void
}

// What group/groupOps.ts needs from the manager to mutate the tree.
export interface GroupOpsHost {
    result: GroupTree
    state: GroupState
    customGroups: { [parentGroupId: number]: Group[] }
    setChildGroup(parent: Group, groups: Group[]): void
    removeChildren(group: Group): void
    regsiterGroup(group: Group): void
    buildOrdinalRanges(): void
    applySha1Piles(): void
    invalidateIterators(): void
    emitResult(): void
}
