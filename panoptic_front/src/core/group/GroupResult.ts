/**
 * GroupResult
 * The composed result of a group() build: the tree data (index / imageToGroups /
 * orderedIds / valueIndex / pileIndex), the reactive result-change signal, and the
 * navigators (iterators) over the display order.
 *
 * Extracted out of GroupManager so the engine (slots + groupBy → tree) stays separate
 * from the *result* object views read and iterate. GroupResult is the IteratorHost —
 * iterators are constructed from it, not from the manager (see collection_inspection_mission.md).
 */
import { Ref, ref } from "vue";
import { EventEmitter } from "@/utils/utils";
import { useColumnStore } from "@/data/columnStore";
import { PileData, pileIndexOfSlot } from "../sha1Piles";
import { Group, GroupIndex, GroupTree, IteratorHost } from "./types";
import { GroupValueIndex } from "./valueIndex";
import { GroupIterator, ImageIterator, GroupIteratorOptions } from "./GroupIterator";

export class GroupResult implements GroupTree, IteratorHost {
    root: Group
    index: GroupIndex
    imageToGroups: Map<number, Set<number>>
    valueIndex: GroupValueIndex
    cacheStale: boolean
    pileIndex: Map<number, PileData>

    private _orderedIds: Int32Array

    // Instance IDs in DFS display order. Materialised on read: every structural edit only
    // marks it stale (buildOrdinalRanges), so a drag-and-drop no longer pays a full-collection
    // sweep for an order nothing may look at.
    get orderedIds(): Int32Array {
        this.ensureOrderedIds()
        return this._orderedIds
    }

    // Result-change signal. Bumped whenever the tree changes; UI watches this and
    // re-reads the (non-reactive) tree. onResultChange is the legacy event kept during
    // the transition for any not-yet-migrated listener.
    version: Ref<number>
    onResultChange: EventEmitter

    // Non-reactive counterpart of `version`, for iterators (see IteratorHost.rev). Bumped by
    // buildOrdinalRanges — i.e. on every structural/order change, including the `emit = false`
    // batching paths that never reach emitResult — so it tracks the *tree*, not the notification.
    rev: number

    constructor() {
        this.root = undefined
        this.index = {}
        this.imageToGroups = new Map()
        this.valueIndex = new GroupValueIndex()
        this._orderedIds = new Int32Array(0)
        this.cacheStale = false
        this.pileIndex = new Map()
        this.version = ref(0)
        this.onResultChange = new EventEmitter()
        this.rev = 0
    }

    // Reset all tree data (keeps the version ref / listeners identity).
    clear() {
        this.root = undefined
        this.index = {}
        this.imageToGroups = new Map()
        this.valueIndex = new GroupValueIndex()
        this._orderedIds = new Int32Array(0)
        this.cacheStale = false
        this.pileIndex = new Map()
        this.rev++
    }

    emitResult() {
        this.version.value++
        this.onResultChange.emit(this)
    }

    // ── Iterators ────────────────────────────────────────────────────────────

    getGroupIterator(groupId?: number, options?: GroupIteratorOptions) {
        return new GroupIterator(this, groupId, options)
    }

    getImageIterator(groupId?: number, imageIdx?: number, options?: GroupIteratorOptions) {
        return new ImageIterator(this, groupId, imageIdx, options)
    }

    // The image's iterator within `groupId`, or undefined when the group is gone or no
    // longer holds it. It used to fall through with idx = -1, producing an iterator whose
    // slot was undefined — callers then "selected" it and wrote a junk key into the mask.
    findImageIterator(groupId: number, imageId: number): ImageIterator | undefined {
        const group = this.index[groupId]
        if (!group) return undefined
        const targetSlot = useColumnStore().slotMap.get(imageId)
        if (targetSlot === undefined) return undefined
        const pile = this.pileIndex.get(groupId)
        const idx = pile ? pileIndexOfSlot(pile, targetSlot) : group.slots.indexOf(targetSlot)
        if (idx < 0) return undefined
        return this.getImageIterator(groupId, idx)
    }

    // ── Ordinal ranges / display order ─────────────────────────────────────────

    // Invalidate the display order (orderedIds + every group's start/end). Called after each
    // structural change; the rebuild itself happens lazily in ensureOrderedIds.
    buildOrdinalRanges(): void {
        this.cacheStale = true
        // Every structural or order change funnels through here, so this is the one place that
        // has to bump `rev` for iterators to notice (see IteratorHost.rev).
        this.rev++
    }

    // Build start/end offsets for all groups and fill orderedIds (instance IDs in DFS display
    // order), if a structural change invalidated them.
    ensureOrderedIds(): void {
        if (!this.cacheStale) return
        this.cacheStale = false
        if (!this.root) { this._orderedIds = new Int32Array(0); return }
        const ids = useColumnStore().instanceIds()

        // The total is NOT root.slots.length: under tag grouping one instance lands in several
        // leaves, so the DFS emits more entries than the root holds. Pre-sizing from the root
        // silently dropped that overflow (typed-array writes past the end are no-ops), leaving
        // a truncated order and out-of-range start/end. Count the leaves first instead.
        let total = 0
        const count = (group: Group): void => {
            if (group.children.length === 0) {
                const pile = this.pileIndex.get(group.id)
                total += pile ? pile.order.length : group.slots.length
            } else {
                for (const child of group.children) count(child)
            }
        }
        count(this.root)

        const orderedIds = new Int32Array(total)
        let pos = 0
        const dfs = (group: Group): void => {
            group.start = pos
            if (group.children.length === 0) {
                // Piled leaf: emit in pile order so getImageOrder = group.start + bounds[k].
                const pile = this.pileIndex.get(group.id)
                const slots = pile ? pile.order : group.slots
                for (const s of slots) orderedIds[pos++] = ids[s]
            } else {
                for (const child of group.children) dfs(child)
            }
            group.end = pos
        }
        dfs(this.root)

        this._orderedIds = orderedIds
    }
}
