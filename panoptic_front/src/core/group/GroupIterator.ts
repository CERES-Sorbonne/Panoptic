/**
 * GroupIterator / ImageIterator — read-only navigators over a GroupTree's display order.
 * They depend only on IteratorHost (result + registerIterator), never on the concrete
 * GroupManager class, so this module has no cycle back to the manager.
 */
import { PileData } from "../sha1Piles";
import { Group, IteratorHost } from "./types";

export interface GroupIteratorOptions {
    ignoreClosed?: boolean
    onlyPropertyGroups?: boolean
    register?: boolean
}

export class GroupIterator {
    isValid: boolean
    readonly group: Group

    protected manager: IteratorHost
    groupId: number
    options: GroupIteratorOptions

    constructor(manager: IteratorHost, groupId?: number, options?: GroupIteratorOptions) {
        this.isValid = true
        this.manager = manager
        if (options?.register) this.manager.registerIterator(this)
        this.groupId = groupId ?? 0
        this.options = options ?? {}
        this.group = this.getGroup()
        this.isValid = this.group !== undefined
    }

    clone(options?: GroupIteratorOptions): GroupIterator {
        return new GroupIterator(this.manager, this.groupId, options ?? this.options)
    }

    private getGroup(): Group {
        return this.manager.result.index[this.groupId]
    }

    nextGroup(): GroupIterator {
        let current = this.group
        if (!current.view.closed && current.children.length > 0) {
            return new GroupIterator(this.manager, current.children[0].id)
        }
        let parent = current.parent
        while (parent != undefined) {
            const next = parent.children[current.parentIdx + 1]
            if (next) return new GroupIterator(this.manager, next.id)
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
                return new GroupIterator(this.manager, lastChild.id)
            } else {
                return new GroupIterator(this.manager, prevSibling.id)
            }
        }
        const parent = current.parent
        if (parent && parent.parent) return new GroupIterator(this.manager, parent.id)
        return undefined
    }

    isGroupBefore(it: GroupIterator): boolean { return this.group.order < it.group.order }
    isGroupEqual(it: GroupIterator): boolean  { return this.group.order == it.group.order }
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
        return this.manager.result.pileIndex.get(this.groupId)
    }

    // A leaf (no property/cluster children) yields images; a group with children is
    // descended into via group iteration. Piled leaves have no children, so this holds.
    private shouldSkipGroup(group: Group): boolean {
        return group.children.length > 0
    }

    // Number of navigable image positions in a leaf: pile count when piled, else slots.
    private positionCount(group: Group): number {
        const pile = this.manager.result.pileIndex.get(group.id)
        return pile ? pile.bounds.length - 1 : group.slots.length
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
        let current = this.clone()
        let nextIdx = current.imageIdx + 1
        while (current) {
            if (nextIdx < this.positionCount(current.group)) {
                return new ImageIterator(this.manager, current.groupId, nextIdx, this.options)
            }
            current = current.nextGroup()
            nextIdx = 0
        }
    }

    prevImages(): ImageIterator {
        let current = this.clone()
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
        const group = this.manager.result.index[this.groupId]
        if (!group) return 0
        const pile = this.manager.result.pileIndex.get(this.groupId)
        if (pile) return group.start + pile.bounds[this.imageIdx]
        return group.start + this.imageIdx
    }
}
