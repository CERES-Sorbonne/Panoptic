/**
 * GroupIterator / ImageIterator — read-only navigators over a GroupTree's display order.
 * They depend only on IteratorHost (tree index + pile overlay + rev), never on the concrete
 * GroupManager class, so this module has no cycle back to the manager.
 */
import { PileData } from "../sha1Piles";
import { Group, IteratorHost } from "./types";

export interface GroupIteratorOptions {
    ignoreClosed?: boolean
}

export class GroupIterator {
    // "This iterator resolved" — set once at construction, never changed afterwards. Cheap plain
    // field read; the scrollers walk it per image. It says nothing about later tree changes: for
    // that, a holder that outlives a rebuild must ask `isCurrent`.
    isValid: boolean
    readonly group: Group

    protected manager: IteratorHost
    // Host revision this iterator was last verified against (see isCurrent).
    protected hostRev: number
    groupId: number
    options: GroupIteratorOptions

    constructor(manager: IteratorHost, groupId?: number, options?: GroupIteratorOptions) {
        this.isValid = true
        this.manager = manager
        this.hostRev = manager.rev
        this.groupId = groupId ?? 0
        this.options = options ?? {}
        this.group = this.getGroup()
        this.isValid = this.group !== undefined
    }

    // "This iterator still describes a real position in the CURRENT tree."
    //
    // For iterators created and consumed inside one synchronous walk this is always true and
    // nobody needs to ask. It exists for handles held across a rebuild (the image modal and its
    // navigation history), where `group` is a captured reference that a rebuild orphans.
    //
    // Strictly identity-based, on purpose: no re-resolution, no following an image that moved.
    // Traversal is only meaningful relative to a position that still exists — if the anchor is
    // gone, any "next" we could offer would assert an adjacency that never existed and read to
    // the user as "these were side by side". Failing is the honest answer.
    get isCurrent(): boolean {
        if (this.hostRev === this.manager.rev) return true
        if (!this.isValid) return false
        if (this.manager.index[this.groupId] !== this.group) return false
        this.hostRev = this.manager.rev     // re-stamp so repeat checks are a single compare
        return true
    }

    clone(options?: GroupIteratorOptions): GroupIterator {
        return new GroupIterator(this.manager, this.groupId, options ?? this.options)
    }

    private getGroup(): Group {
        return this.manager.index[this.groupId]
    }

    // Every hop carries `this.options` forward. Without it a walk silently reverted to the
    // defaults after one step, so `ignoreClosed` only ever applied to the first group.
    protected at(groupId: number): GroupIterator {
        return new GroupIterator(this.manager, groupId, this.options)
    }

    nextGroup(): GroupIterator {
        let current = this.group
        // Descend into an open group's children — or any group's, when the walk is told to
        // ignore the open/closed state (prevGroup has always honoured that flag; forward
        // traversal used to stop at every closed group regardless).
        if ((!current.view.closed || this.options.ignoreClosed) && current.children.length > 0) {
            return this.at(current.children[0].id)
        }
        let parent = current.parent
        while (parent != undefined) {
            const next = parent.children[current.parentIdx + 1]
            if (next) return this.at(next.id)
            current = parent
            parent = current.parent
        }
        return undefined
    }

    prevGroup(): GroupIterator {
        const current = this.group
        const prevSibling = current.parent?.children[current.parentIdx - 1]
        if (prevSibling) {
            if (prevSibling.children.length > 0 && (!prevSibling.view.closed || this.options.ignoreClosed)) {
                let lastChild = prevSibling.children[prevSibling.children.length - 1]
                while (lastChild.children.length > 0 && (!lastChild.view.closed || this.options.ignoreClosed)) {
                    lastChild = lastChild.children[lastChild.children.length - 1]
                }
                return this.at(lastChild.id)
            } else {
                return this.at(prevSibling.id)
            }
        }
        const parent = current.parent
        if (parent && parent.parent) return this.at(parent.id)
        return undefined
    }

    isGroupBefore(it: GroupIterator): boolean { return this.group.order < it.group.order }
    isGroupEqual(it: GroupIterator): boolean  { return this.group.order == it.group.order }

    // ── Range walk (shift-select geometry) ─────────────────────────────────────
    // The three primitives below are the only things that differ between a group
    // walk and an image walk; ImageIterator overrides them so collectRange is shared.
    protected isBefore(it: GroupIterator): boolean { return this.isGroupBefore(it) }
    protected rangeSlots(): number[] { return this.group.slots }
    protected advance(): GroupIterator { return this.nextGroup() }

    // Collect every slot from `this` to `other` inclusive, in display order, regardless
    // of which endpoint comes first. Pure geometry — no selection/store side effects.
    collectRange(other: GroupIterator): number[] {
        const start = this.isBefore(other) ? this : other
        const end   = start === this ? other : this
        const selected: number[] = []
        let it: GroupIterator = start
        while (it) {
            if (end.isBefore(it)) break
            for (const s of it.rangeSlots()) selected.push(s)
            it = it.advance()
        }
        return selected
    }
}

export class ImageIterator extends GroupIterator {
    // Slot index of the current image (or first slot of the sha1 pile).
    readonly slot: number
    // All slots at this position (one entry normally, many if a sha1 pile).
    readonly slots: number[]
    declare readonly group: Group

    imageIdx: number

    constructor(manager: IteratorHost, groupId?: number, imageIdx?: number, options?: GroupIteratorOptions) {
        super(manager, groupId, options)
        this.imageIdx = imageIdx ?? 0

        if (this.isValid && this.shouldSkipGroup(this.group)) {
            const next = this.nextGroup()
            if (next) {
                this.groupId = next.groupId
                Object.defineProperty(this, 'group', { value: next.group, writable: false })
                this.imageIdx = 0
            } else {
                this.isValid = false
            }
        }

        if (this.isValid) {
            this.slots = this.getSlots()
            this.slot = this.slots[0]
        }
    }

    // The pile overlay for the current leaf (undefined when the leaf renders flat).
    private pile(): PileData | undefined {
        return this.manager.pileIndex.get(this.groupId)
    }

    // A leaf (no property/cluster children) yields images; a group with children is
    // descended into via group iteration. Piled leaves have no children, so this holds.
    private shouldSkipGroup(group: Group): boolean {
        return group.children.length > 0
    }

    // Number of navigable image positions in a leaf: pile count when piled, else slots.
    private positionCount(group: Group): number {
        const pile = this.manager.pileIndex.get(group.id)
        return pile ? pile.bounds.length - 1 : group.slots.length
    }

    // Same as GroupIterator.isCurrent, plus the image position itself: the group must still be
    // the same node AND still hold the same image (the same slots, in the same place) at
    // `imageIdx`. Groups are mutated in place — ClusterManager.drain filters a group's `slots`
    // without replacing the node — so group identity alone would pass while `slot`, captured at
    // construction, points at an image that has left. The whole `slots` array is compared, so a
    // sha1 pile whose membership changed also counts as "not the same image".
    override get isCurrent(): boolean {
        if (this.hostRev === this.manager.rev) return true
        if (!this.isValid) return false
        if (this.manager.index[this.groupId] !== this.group) return false
        // Bounds first: getSlots() past the end would read undefined and compare as garbage.
        if (this.imageIdx >= this.positionCount(this.group)) return false
        const now = this.getSlots()
        if (now.length !== this.slots.length) return false
        for (let i = 0; i < now.length; i++) if (now[i] !== this.slots[i]) return false
        this.hostRev = this.manager.rev
        return true
    }

    static fromGroupIterator(it: GroupIterator, options?: GroupIteratorOptions) {
        const imageIt = new ImageIterator(it['manager'], it.group.id, 0, options)
        if (!imageIt.isValid) return undefined
        return imageIt
    }

    private getSlots(): number[] {
        const pile = this.pile()
        if (pile) {
            const k = this.imageIdx
            return pile.order.slice(pile.bounds[k], pile.bounds[k + 1])
        }
        return [this.group.slots[this.imageIdx]]
    }

    nextGroup(): ImageIterator {
        let next = super.nextGroup()
        while (next) {
            const group = next.group
            const shouldIterate = (!group.view.closed || this.options.ignoreClosed)
                && !this.shouldSkipGroup(group)
            if (shouldIterate) {
                const lastIndex = this.positionCount(group) - 1
                return new ImageIterator(this.manager, next.group.id, lastIndex, this.options)
            }
            next = next.nextGroup()
        }
        return undefined
    }

    prevGroup(): ImageIterator {
        let prev = super.prevGroup()
        while (prev) {
            const group = prev.group
            const shouldIterate = (!group.view.closed || this.options.ignoreClosed)
                && !this.shouldSkipGroup(group)
            if (shouldIterate) {
                return new ImageIterator(this.manager, prev.group.id, 0, this.options)
            }
            prev = prev.prevGroup()
        }
        return undefined
    }

    nextImages(): ImageIterator {
        let current: ImageIterator = this
        let nextIdx = current.imageIdx + 1
        while (current) {
            if (nextIdx < this.positionCount(current.group)) {
                return new ImageIterator(this.manager, current.groupId, nextIdx, this.options)
            }
            current = current.nextGroup()
            nextIdx = 0
        }
        return undefined
    }

    prevImages(): ImageIterator {
        // No clone: the walk only ever READS current and reassigns it, so cloning just added
        // an allocation per step to a loop that runs once per image.
        let current: ImageIterator = this
        let prevIdx = current.imageIdx - 1
        while (current) {
            if (prevIdx >= 0) {
                return new ImageIterator(this.manager, current.groupId, prevIdx, this.options)
            }
            current = current.prevGroup()
            if (current) {
                prevIdx = this.positionCount(current.group) - 1
            }
        }
        return undefined
    }

    // Override the range-walk primitives so collectRange walks images (piles included)
    // rather than groups. `it.slots` is the whole pile when piled, or [slot] otherwise.
    protected isBefore(it: GroupIterator): boolean { return this.isImageBefore(it as ImageIterator) }
    protected rangeSlots(): number[] { return this.slots }
    protected advance(): GroupIterator { return this.nextImages() }

    isImageBefore(it: ImageIterator) {
        if (this.isGroupEqual(it)) return this.imageIdx < it.imageIdx
        return this.isGroupBefore(it)
    }

    isImageEqual(it: ImageIterator) {
        return this.isGroupEqual(it) && this.imageIdx == it.imageIdx
    }

    clone(options?: GroupIteratorOptions): ImageIterator {
        return new ImageIterator(this.manager, this.groupId, this.imageIdx, options ?? this.options)
    }

    // Returns the global display position for this image within orderedIds.
    // For piled leaves: group.start + the pile's offset (bounds[imageIdx]).
    // For flat leaves: group.start + imageIdx.
    getImageOrder(): number {
        // start/end are rebuilt lazily now — force them current before reading.
        this.manager.ensureOrderedIds()
        const group = this.manager.index[this.groupId]
        if (!group) return 0
        const pile = this.manager.pileIndex.get(this.groupId)
        if (pile) return group.start + pile.bounds[this.imageIdx]
        return group.start + this.imageIdx
    }
}
