/**
 * slotOrder — put a group's slots back in display order after an incremental edit.
 *
 * Display order is the position a slot got from the last full group() run (SortManager's
 * order). An incremental update touches a group's slot array in only two ways: the edit's
 * filter drops some slots (order preserving, so the survivors stay ordered) and
 * addUpdatedToGroups appends the changed slots at the end. So the array is a sorted prefix
 * followed by a short unsorted tail, and a full comparison sort over it is wasted work.
 *
 * No imports: this module is pulled in by GroupManager, and anything reaching the stores
 * (sort.ts, builders.ts) would close an import cycle.
 */

// Slot -> display position, as GroupManager records it during group().
//  - posArr[slot] is the position, or -1 when the slot was not in that run
//  - a slot with no recorded position (imported since) gets count + slot, so it lands at the
//    end, ordered by slot index, instead of at position 0 ahead of everything
export interface SlotPositions {
    posArr: Int32Array
    maxSlot: number
    count: number
}

export function slotPosition(slot: number, p: SlotPositions): number {
    const v = slot <= p.maxSlot ? p.posArr[slot] : -1
    return v >= 0 ? v : p.count + slot
}

/**
 * Order `slots` in place, knowing that `slots[0 .. appendedFrom)` was already in display order
 * before the edit and `slots[appendedFrom ..]` was appended by it.
 *
 * Result is element-for-element what `slots.sort((a, b) => pos(a) - pos(b))` produces:
 *  - the prefix is checked, not assumed — a prefix that is not ordered falls back to that
 *    exact sort, so a group whose array was written by some other path is still fixed
 *  - ties (two entries with the same position, i.e. the same slot listed twice) keep their
 *    original relative order, because the merge takes from the appended tail only when the
 *    prefix entry is strictly smaller — the same result as the stable sort it replaces
 *
 * Cost is O(k log k + n) with one position lookup per element, against O(n log n) with two
 * lookups per comparison. Nothing is copied when nothing was appended.
 */
export function orderSlots(slots: number[], appendedFrom: number, p: SlotPositions): void {
    const n = slots.length
    if (n < 2) return
    const cut = appendedFrom < 0 ? 0 : (appendedFrom > n ? n : appendedFrom)

    let prev = cut > 0 ? slotPosition(slots[0], p) : 0
    for (let i = 1; i < cut; i++) {
        const cur = slotPosition(slots[i], p)
        if (cur < prev) {
            slots.sort((a, b) => slotPosition(a, p) - slotPosition(b, p))
            return
        }
        prev = cur
    }
    // Nothing was appended: the prefix is the whole array and it is already in order.
    if (cut == n) return

    // Sort the appended tail on its own, then merge it into the prefix from the back: every
    // element is written at most once and only the tail is copied.
    const tail = slots.slice(cut)
    tail.sort((a, b) => slotPosition(a, p) - slotPosition(b, p))

    let i = cut - 1
    let j = tail.length - 1
    let out = n - 1
    let pa = i >= 0 ? slotPosition(slots[i], p) : 0
    let pb = slotPosition(tail[j], p)
    while (j >= 0) {
        if (i >= 0 && pa > pb) {
            slots[out--] = slots[i--]
            if (i >= 0) pa = slotPosition(slots[i], p)
        } else {
            slots[out--] = tail[j--]
            if (j >= 0) pb = slotPosition(tail[j], p)
        }
    }
}
