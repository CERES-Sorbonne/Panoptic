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
import { useColumnStore } from "@/data/columnStore";
import { Group } from "./types";
import { GroupIterator, ImageIterator } from "./GroupIterator";
import { GroupResult } from "./GroupResult";

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

    toggleGroup(groupId: number, emit?: boolean) {
        const view = this.result.index[groupId].view
        view.closed = !view.closed
        if (emit) this.result.emitResult()
    }

    openGroup(groupId: number, emit?: boolean) {
        this.result.index[groupId].view.closed = false
        if (emit) this.result.emitResult()
    }

    closeGroup(groupId: number, emit?: boolean) {
        this.result.index[groupId].view.closed = true
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

    selectImageIterator(iterator: ImageIterator, shift = false) {
        if (shift) this._shiftSelect(iterator)
        useColumnStore().select(iterator.slots, this.selectionNamespace)
        this.clearLastSelected()
        this.lastImage = iterator.clone()
    }

    unselectImageIterator(iterator: ImageIterator) {
        useColumnStore().deselect(iterator.slots, this.selectionNamespace)
        this.clearLastSelected()
    }

    toggleImageIterator(iterator: ImageIterator, shift = false) {
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
    private _shiftSelect(iterator: ImageIterator) {
        if (this.lastImage == undefined) return false
        const selected = this.lastImage.collectRange(iterator)
        if (selected.length) { useColumnStore().select(selected, this.selectionNamespace); return true }
        return false
    }

    private _shiftGroup(iterator: GroupIterator) {
        if (this.lastGroup == undefined) return false
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
    isGroupSelected(group: Group): boolean {
        const col = useColumnStore()
        col.selectionTick(this.selectionNamespace)
        const slots = group?.slots
        if (!slots?.length) return false
        return !slots.some(s => !col.isSelected(s, this.selectionNamespace))
    }

    selectGroup(group: Group) {
        useColumnStore().select(group.slots, this.selectionNamespace)
    }

    unselectGroup(group: Group) {
        useColumnStore().deselect(group.slots, this.selectionNamespace)
    }

    selectGroupIterator(iterator: GroupIterator, shift = false) {
        if (shift) this._shiftGroup(iterator)
        this.selectGroup(iterator.group)
        this.clearLastSelected()
        this.lastGroup = iterator.clone()
    }

    unselectGroupIterator(iterator: GroupIterator) {
        this.unselectGroup(iterator.group)
        this.clearLastSelected()
    }

    toggleGroupIterator(iterator: GroupIterator, shift = false) {
        const col = useColumnStore()
        const selected = !iterator.group.slots.some(s => !col.isSelected(s, this.selectionNamespace))
        if (selected) this.unselectGroupIterator(iterator)
        else this.selectGroupIterator(iterator, shift)
    }
}
