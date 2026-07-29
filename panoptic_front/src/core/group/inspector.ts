/**
 * GroupInspector — the tree-inspection contract the scrollers render against.
 *
 * The scrollers used to take a concrete `GroupManager`, which forced views owning a
 * `CollectionManager` to reach through `.groupManager`. Both classes satisfy this
 * interface (`CollectionManager` by delegation), so a scroller can be fed either:
 * a collection in the main/group views, a standalone GroupManager in the preview,
 * recommend and image-modal panels, which have no collection behind them.
 *
 * It is deliberately the *read + view-state* surface only: no filter/sort/group
 * config, no rebuild. Anything a scroller must not do is absent from the type.
 */

import type { Ref } from "vue"
import type { Group, GroupState } from "./types"
import type { GroupResult } from "./GroupResult"
import type { GroupIterator, ImageIterator, GroupIteratorOptions } from "./GroupIterator"
import type { ClusterRequest } from "./ClusterManager"

export interface GroupInspector {
    // Result tree + change tick the scrollers watch.
    readonly result: GroupResult
    readonly version: Ref<number>
    // Named `groupState` on both implementations (CollectionManager already has its own
    // `state`, the CollectionState).
    readonly groupState: GroupState
    readonly selectionNamespace: string

    hasResult(): boolean
    emitResult(): void

    // Iteration
    getGroupIterator(groupId?: number, options?: GroupIteratorOptions): GroupIterator
    getImageIterator(groupId?: number, imageIdx?: number, options?: GroupIteratorOptions): ImageIterator
    findImageIterator(groupId: number, imageId: number): ImageIterator | undefined

    // Open / close
    toggleGroup(groupId: number, emit?: boolean): void
    openGroup(groupId: number, emit?: boolean): void
    closeGroup(groupId: number, emit?: boolean): void

    // Selection
    toggleGroupIterator(iterator: GroupIterator, shift?: boolean): void
    toggleImageIterator(iterator: ImageIterator, shift?: boolean): void
    isGroupSelected(group: Group): boolean
    // Direct id-based selection, for views that don't navigate by iterator (the map's lasso).
    selectImages(imageIds: number[]): void
    unselectImages(imageIds: number[]): void

    // Cluster / custom-group ops reachable from group lines
    cluster(targetGroupId: number, req: ClusterRequest): void
    isClustering(groupId: number): boolean
    delCustomGroups(targetGroupId: number, emit?: boolean): void
    clearCustomGroups(emit?: boolean): void
}
