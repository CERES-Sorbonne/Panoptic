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
