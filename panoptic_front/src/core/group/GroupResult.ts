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
    orderedIds: Int32Array
    cacheStale: boolean
    pileIndex: Map<number, PileData>

    // Result-change signal. Bumped whenever the tree changes; UI watches this and
    // re-reads the (non-reactive) tree. onResultChange is the legacy event kept during
    // the transition for any not-yet-migrated listener.
    version: Ref<number>
    onResultChange: EventEmitter

    private iterators: GroupIterator[]

    constructor() {
        this.root = undefined
        this.index = {}
        this.imageToGroups = new Map()
        this.valueIndex = new GroupValueIndex()
        this.orderedIds = new Int32Array(0)
        this.cacheStale = false
        this.pileIndex = new Map()
        this.version = ref(0)
        this.onResultChange = new EventEmitter()
        this.iterators = []
    }

    // Reset all tree data (keeps the version ref / listeners identity).
    clear() {
        this.invalidateIterators()
        this.root = undefined
        this.index = {}
        this.imageToGroups = new Map()
        this.valueIndex = new GroupValueIndex()
        this.orderedIds = new Int32Array(0)
        this.cacheStale = false
        this.pileIndex = new Map()
    }

    emitResult() {
        this.version.value++
        this.onResultChange.emit(this)
    }

    // ── Iterators ────────────────────────────────────────────────────────────

    registerIterator(it: GroupIterator) {
        this.iterators.push(it)
    }

    invalidateIterators() {
        for (const it of this.iterators) it.isValid = false
        this.iterators = []
    }

    getGroupIterator(groupId?: number, options?: GroupIteratorOptions) {
        return new GroupIterator(this, groupId, options)
    }

    getImageIterator(groupId?: number, imageIdx?: number, options?: GroupIteratorOptions) {
        return new ImageIterator(this, groupId, imageIdx, options)
    }

    findImageIterator(groupId: number, imageId: number) {
        const col = useColumnStore()
        const group = this.index[groupId]
        const targetSlot = col.slotMap.get(imageId)
        let idx = -1
        if (targetSlot !== undefined) {
            const pile = this.pileIndex.get(groupId)
            idx = pile ? pileIndexOfSlot(pile, targetSlot) : group.slots.indexOf(targetSlot)
        }
        return this.getImageIterator(groupId, idx)
    }

    // ── Ordinal ranges / display order ─────────────────────────────────────────

    // Build start/end offsets for all groups and fill orderedIds (instance IDs in DFS display
    // order). Single DFS pass: root.slots.length is the pre-known total, so we pre-allocate and
    // fill in one sweep.
    buildOrdinalRanges(): void {
        if (!this.root) return
        const ids = useColumnStore().instanceIds()
        const orderedIds = new Int32Array(this.root.slots.length)
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

        this.orderedIds = orderedIds
        this.cacheStale = false
    }
}
