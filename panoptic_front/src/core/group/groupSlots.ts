/**
 * groupSlots — the slots a group effectively holds.
 *
 * Its own file, with a type-only import, so it stays free of runtime imports: the selection
 * surface (GroupNavigator, GroupIterator) needs it, and reaching it through groupOps would pull
 * the store chain (groupOps → sort → dataStore → tabStore → TabManager → GroupManager) back into
 * those modules. Re-exported from groupOps for the callers that already import it there.
 */
import type { Group } from "./types";

// Every image a group shows, including those of its sub-piles. A group that has been split
// carries no slots of its own — its images live in its leaves — so the union is walked for the
// operations that act on a whole card.
export function groupSlots(group: Group): number[] {
    if (!group.children.length) return group.slots
    const res: number[] = []
    const seen = new Set<number>()
    const walk = (g: Group) => {
        if (!g.children.length) { for (const s of g.slots) if (!seen.has(s)) { seen.add(s); res.push(s) } }
        else g.children.forEach(walk)
    }
    walk(group)
    return res
}

// The first `n` images a group shows, read from its leaves when it has been sub-clustered. A
// card only needs a few images to draw, so the walk stops as soon as it has them instead of
// building the whole union.
export function firstSlots(group: Group, n: number): number[] {
    if (!group.children.length) return group.slots.slice(0, n)
    const res: number[] = []
    const walk = (g: Group): boolean => {
        if (!g.children.length) {
            for (const s of g.slots) {
                res.push(s)
                if (res.length >= n) return true
            }
            return false
        }
        return g.children.some(walk)
    }
    walk(group)
    return res
}
