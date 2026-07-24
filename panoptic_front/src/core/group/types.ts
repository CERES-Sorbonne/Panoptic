/**
 * Shared Group types. Kept dependency-free (only leaf modules + @/data) so every other
 * group/* module and the GroupManager class import from here, never the reverse — the
 * import graph stays a DAG.
 */
import { DateUnit, GroupScoreList, PropertyValue, Score } from "@/data/models";
import { SortOption } from "../SortManager";
import { PileData } from "../sha1Piles";
import { GroupValueIndex } from "./valueIndex";

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

    // Offsets into GroupTree.orderedIds. Computed lazily with it (GroupResult.ensureOrderedIds),
    // so read them through orderedIds / ensureOrderedIds rather than straight after an edit.
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
    readonly orderedIds: Int32Array           // instance IDs in DFS display order (lazy — see GroupResult)
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

// Iterators navigate the display order; they read only the tree index + pile overlay + the
// structural revision. Satisfied by GroupResult (the host is the result now, not the manager).
export interface IteratorHost {
    index: GroupIndex
    pileIndex: Map<number, PileData>
    // Non-reactive structural revision, bumped on every tree/order change. Iterators compare
    // against it to decide whether they still describe a real position (GroupIterator.isCurrent).
    // Deliberately a plain number, not the `version` Ref: the check sits on hot paths and must
    // not create reactive dependencies. Consumers that want reactivity read `version` too.
    rev: number
    // Materialise the display order if a structural change invalidated it. Only the
    // position-reporting iterator methods need it (start/end are lazy now).
    ensureOrderedIds(): void
}

// The tree-mutation primitives the cluster ops delegate to (provided by the tree layer /
// GroupManager). The custom-group registry itself is NOT here — it lives on ClusterManager.
export interface ClusterOpsHost {
    result: GroupTree
    setChildGroup(parent: Group, groups: Group[]): void
    removeChildren(group: Group): void
    regsiterGroup(group: Group): void
    buildOrdinalRanges(): void
    // `only` limits the recompute to the given leaves; omitted = full rebuild.
    applySha1Piles(only?: Iterable<Group>): void
    emitResult(): void
}

// What group/groupOps.ts needs: the tree primitives + the custom-group registry.
// Satisfied by ClusterManager.
export interface GroupOpsHost extends ClusterOpsHost {
    customGroups: { [parentGroupId: number]: Group[] }
}
