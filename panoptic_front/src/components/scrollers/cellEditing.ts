// Which property cells of a scroller have their editor mounted.
//
// The scrollers draw every property cell as plain read-only markup and mount the real editor
// (DBInput + typed input + popup, hover source, ...) only for the cell being edited: with
// hundreds of cards on screen, an editor stack per cell was most of the cost of scrolling,
// opening a group or toggling a property.
//
// One instance per scroller, provided to its cells: two scrollers (both panes, or the grid next to
// the tree) never share one, so opening a cell in one cannot close the other's.
import { InjectionKey, shallowRef } from 'vue'
import { CellTarget } from './cellNavigation'

export interface CellKey extends CellTarget {
    propertyId: number
}

export function sameCell(a: CellKey, b: CellKey) {
    return !!a && !!b && a.instanceId === b.instanceId && a.groupId === b.groupId && a.propertyId === b.propertyId
}

export interface CellEditingOptions {
    // The cell Tab (or Shift-Tab) moves to from `from`, after bringing it into view; undefined at
    // either end. Async: when the target has to be scrolled to, its editor must only open once the
    // scroll has settled (the popups close on any scroll).
    navigate?: (from: CellKey, backwards: boolean) => Promise<CellKey | undefined> | CellKey | undefined
}

export type CellEditing = ReturnType<typeof useCellEditing>

export const cellEditingKey: InjectionKey<CellEditing> = Symbol('cellEditing')

export function useCellEditing(options: CellEditingOptions = {}) {
    // Cells whose editor is mounted, the active one last. Normally a single cell. A second one is
    // there only while an editor opens before the previous one is done: the previous editor
    // commits on its own blur — which the new one's focus is what causes — so it stays mounted
    // until it reports closed. Unmounting it first would tear the focused field out of the page,
    // and a removed element does not reliably fire the blur that commits it.
    const open = shallowRef<CellKey[]>([])

    function active(): CellKey | undefined {
        return open.value[open.value.length - 1]
    }

    // Anything older than the active editor is dropped: it had its chance to close.
    function openCell(key: CellKey) {
        const current = active()
        if (current && sameCell(current, key)) return
        open.value = current ? [current, key] : [key]
    }

    function closeCell(key: CellKey) {
        if (!open.value.some(c => sameCell(c, key))) return
        open.value = open.value.filter(c => !sameCell(c, key))
    }

    async function tab(from: CellKey, backwards: boolean) {
        if (!options.navigate) return
        const to = await options.navigate(from, backwards)
        if (to) openCell(to)
    }

    return { open, openCell, closeCell, tab }
}

// The properties of one card (instance, group) whose editor is open. Handed `previous` (a
// computed's last value) so it returns that same array while nothing changed for this card: every
// card on screen re-evaluates when any cell opens or closes, and only the one or two cards it
// concerns should re-render.
export function openPropertiesOf(open: CellKey[], instanceId: number, groupId: number, previous?: number[]): number[] {
    const ids: number[] = []
    for (const c of open) {
        if (c.instanceId === instanceId && c.groupId === groupId) ids.push(c.propertyId)
    }
    if (previous && previous.length === ids.length && previous.every((id, i) => id === ids[i])) return previous
    return ids
}
