/**
 * GroupNavigator
 * View/selection state over a built GroupResult tree: open/close, image & group
 * selection, and the shift-select anchors. Extracted out of GroupManager so the
 * engine (slots + groupBy → tree) stays separate from traversal of that tree.
 *
 * Selection itself lives in columnStore, keyed by namespace. By default a navigator
 * drives the shared 'global' selection; a custom namespace (setSelectionNamespace)
 * gives it an independent selection mask. The shift anchors (lastImage/lastGroup)
 * are the only navigation state that must outlive an individual iterator, so they
 * live here — not on the ephemeral, read-only GroupIterator.
 */
import { useColumnStore } from "@/data/stores/columnStore";
import { Group } from "./types";
import { GroupIterator, ImageIterator } from "./GroupIterator";
import { GroupResult } from "./GroupResult";
import { groupSlots } from "./groupSlots";

export class GroupNavigator {
    private result: GroupResult

    selectionNamespace = 'global'
    private lastImage: ImageIterator
    private lastGroup: GroupIterator

    constructor(result: GroupResult) {
        this.result = result
        this.lastImage = undefined
        this.lastGroup = undefined
    }

    // ── Open / close ─────────────────────────────────────────────────────────

    // All three take a raw id, which a recycled scroller line can hold after the group it
    // pointed at is gone: a missing group is nothing to open or close, not a crash.
    toggleGroup(groupId: number, emit?: boolean) {
        const group = this.result.index[groupId]
        if (!group) return
        group.view.closed = !group.view.closed
        if (emit) this.result.emitResult()
    }

    openGroup(groupId: number, emit?: boolean) {
        const group = this.result.index[groupId]
        if (!group) return
        group.view.closed = false
        if (emit) this.result.emitResult()
    }

    closeGroup(groupId: number, emit?: boolean) {
        const group = this.result.index[groupId]
        if (!group) return
        group.view.closed = true
        if (emit) this.result.emitResult()
    }

    // ── Selection ──────────────────────────────────────────────────────────

    // Point this navigator at a custom selection namespace (creating its mask).
    setSelectionNamespace(ns: string) {
        this.selectionNamespace = ns
        useColumnStore().ensureNamespace(ns)
    }

    clearSelection() {
        useColumnStore().clearSelection(this.selectionNamespace)
        this.clearLastSelected()
    }

    clearLastSelected() {
        this.lastGroup = undefined
        this.lastImage = undefined
    }

    // The six *Iterator methods below all early-return on an invalid iterator. Callers are
    // recycled virtual-scroller lines that can outlive the group they point at, and an invalid
    // iterator has no `group` and no `slots` — dereferencing either would throw.
    selectImageIterator(iterator: ImageIterator, shift = false) {
        if (!iterator?.isValid) return
        if (shift) this._shiftSelect(iterator)
        useColumnStore().select(iterator.slots, this.selectionNamespace)
        this.clearLastSelected()
        this.lastImage = iterator.clone()
    }

    unselectImageIterator(iterator: ImageIterator) {
        if (!iterator?.isValid) return
        useColumnStore().deselect(iterator.slots, this.selectionNamespace)
        this.clearLastSelected()
    }

    toggleImageIterator(iterator: ImageIterator, shift = false) {
        if (!iterator?.isValid) return
        const col = useColumnStore()
        const selected = iterator.slots.every(s => col.isSelected(s, this.selectionNamespace))
        if (selected) this.unselectImageIterator(iterator)
        else this.selectImageIterator(iterator, shift)
    }

    toggleAll() {
        const iterator = this.result.getGroupIterator()
        this.toggleGroupIterator(iterator)
    }

    // Range geometry lives on the iterator now (collectRange); the navigator only owns
    // the anchor + the store write.
    //
    // The anchor is the one iterator here that outlives the click that set it, so it is exactly
    // the handle `isCurrent` exists for: a rebuild between the two clicks leaves it pointing at
    // a node of the previous tree, and a range walked from there crosses two trees — it threw on
    // the first hop, and a range that did not throw would claim an adjacency that never existed.
    // A stale anchor is no anchor: the shift-click selects its own image.
    private _shiftSelect(iterator: ImageIterator) {
        if (!this.lastImage?.isCurrent) return false
        const selected = this.lastImage.collectRange(iterator)
        if (selected.length) { useColumnStore().select(selected, this.selectionNamespace); return true }
        return false
    }

    private _shiftGroup(iterator: GroupIterator) {
        if (!this.lastGroup?.isCurrent) return false
        const selected = this.lastGroup.collectRange(iterator)
        if (selected.length) { useColumnStore().select(selected, this.selectionNamespace); return true }
        return false
    }

    unselectImage(imageId: number) { useColumnStore().deselectIds([imageId], this.selectionNamespace) }
    selectImage(imageId: number)   { useColumnStore().selectIds([imageId], this.selectionNamespace) }

    selectImages(imageIds: number[]) {
        useColumnStore().selectIds(imageIds, this.selectionNamespace)
    }

    unselectImages(imageIds: number[]) {
        useColumnStore().deselectIds(imageIds, this.selectionNamespace)
    }

    // Is every image of `group` selected in this navigator's namespace?
    //
    // The single read-side answer to "is this group selected". It used to be a cached
    // `group.view.selected` flag maintained by a recursive propagateSelect — state on tree nodes
    // that a rebuild replaces, and in practice never written, so the flag was permanently false.
    // Derived instead: always correct, nothing to invalidate.
    //
    // Reads selectionTick first so a caller in a template/computed picks up a reactive dependency
    // on this namespace's selection — the masks themselves are markRaw for speed.
    // An empty group is NOT selected (`every` on an empty array would say it is).
    //
    // Asks groupSlots, not group.slots: a sub-clustered pile holds no slots of its own — its
    // images live in its children — so raw slots answered "not selected" for a card that shows
    // images, and the whole group-selection surface went with it.
    isGroupSelected(group: Group): boolean {
        const col = useColumnStore()
        col.selectionTick(this.selectionNamespace)
        const slots = group ? groupSlots(group) : undefined
        if (!slots?.length) return false
        return !slots.some(s => !col.isSelected(s, this.selectionNamespace))
    }

    selectGroup(group: Group) {
        useColumnStore().select(groupSlots(group), this.selectionNamespace)
    }

    unselectGroup(group: Group) {
        useColumnStore().deselect(groupSlots(group), this.selectionNamespace)
    }

    selectGroupIterator(iterator: GroupIterator, shift = false) {
        if (!iterator?.isValid) return
        if (shift) this._shiftGroup(iterator)
        this.selectGroup(iterator.group)
        this.clearLastSelected()
        this.lastGroup = iterator.clone()
    }

    unselectGroupIterator(iterator: GroupIterator) {
        if (!iterator?.isValid) return
        this.unselectGroup(iterator.group)
        this.clearLastSelected()
    }

    // One read-side answer: the same predicate the checkbox renders from decides which way the
    // click goes. The inline copy this replaces said "selected" for an empty slot list, so a
    // sub-clustered pile always took the unselect branch and the click did nothing.
    toggleGroupIterator(iterator: GroupIterator, shift = false) {
        if (!iterator?.isValid) return
        const selected = this.isGroupSelected(iterator.group)
        if (selected) this.unselectGroupIterator(iterator)
        else this.selectGroupIterator(iterator, shift)
    }
}
