/**
 * HoverStore
 *
 * Which property the user is currently pointing at or editing, anywhere in the app, so that
 * distant views can react to it — the properties panel grows the icon of the property whose
 * cell is hovered in the scroller.
 *
 * Everything global lives here: the state, the producer composable (useHoverSource), and the
 * injection key the tree/cluster rows publish their property id on.
 *
 * Entries are keyed by an owner token (one Symbol per component instance), NOT by property id,
 * and never by a single shared ref. Two bugs disappear because of it:
 *
 *  - enter/leave races: moving between two cells fires B's enter BEFORE A's leave in most
 *    browsers. A single ref would end up cleared by the row the pointer just left. Here A can
 *    only ever delete A's own entry.
 *  - the same property shown in two rows: clearing "by property id" would let one row cancel
 *    the other's hover.
 */

import { defineStore } from "pinia";
import { computed, inject, InjectionKey, onUnmounted, reactive, Ref, watch } from "vue";

// Which property the rows below are editing, published by TreePropertyInput and
// ClusterPropertyInput so TreeCellFrame can report hover/focus without every typed input in
// between having to carry a propertyId prop it has no other use for.
// A getter rather than a value: a recycled row swaps property under a live component.
export const hoverPropertyKey: InjectionKey<() => number> = Symbol('hoverProperty')

// Last writer wins: the pointer moved onto it most recently, so it is the one to show.
function lastOf(map: Map<symbol, number>) {
    let last: number = null
    for (const v of map.values()) last = v
    return last
}

export const useHoverStore = defineStore('hoverStore', () => {
    const hovered = reactive(new Map<symbol, number>())
    // Editing outranks pointing: while a cell's editor is open the pointer is free to wander.
    const focused = reactive(new Map<symbol, number>())

    const activeProperty = computed(() => lastOf(focused) ?? lastOf(hovered))

    function set(map: Map<symbol, number>, token: symbol, propertyId: number) {
        if (propertyId === null || propertyId === undefined) map.delete(token)
        else map.set(token, propertyId)
    }

    // Everything the pointer could be on is gone or unreachable: window blurred, pointer left
    // the document, a drag started. Focus is untouched — an open editor survives all three.
    function clearAllHover() {
        hovered.clear()
    }

    function clear() {
        hovered.clear()
        focused.clear()
    }

    return {
        activeProperty, hovered, focused, clearAllHover, clear,
        setHover: (t: symbol, id: number) => set(hovered, t, id),
        clearHover: (t: symbol) => hovered.delete(t),
        setFocus: (t: symbol, id: number) => set(focused, t, id),
        clearFocus: (t: symbol) => focused.delete(t),
    }
})

// Listeners are global but installed once for the whole app, not once per row: a scroller
// mounts hundreds of sources.
let installed = false

// Sources holding a DOM-focus claim, asked to re-check it whenever focus moves anywhere in the
// page. focusout is not enough on its own: an editor that unmounts its <input> as it closes
// (the number cell hides it the moment it blurs) can have the element torn out of the document
// before the event is delivered, and then it never comes.
const focusClaims = new Set<() => void>()

/**
 * Producer side: one call per component that can be pointed at. Injects the property id
 * published above, so a component outside the tree/cluster scrollers reports nothing.
 *
 * Covers the four ways a hover goes stale in a virtualized scroller, none of which send a
 * pointerleave:
 *   - the row unmounts while hovered (recycling, group collapse, tab switch) → onUnmounted
 *   - the row is rebound to another property under a still pointer → watch on the id
 *   - the window loses focus, or the pointer leaves the document → global listeners
 *   - a drag steals the pointer → pointercancel
 */
export function useHoverSource(root?: Ref<HTMLElement>) {
    const hover = useHoverStore()
    const propertyId = inject(hoverPropertyKey, () => null)

    if (!installed) {
        installed = true
        const clear = () => hover.clearAllHover()
        // Deferred: during focusout the document still reports the OLD activeElement, and a
        // click on empty space moves focus to <body> without ever firing focusin.
        const recheck = () => setTimeout(() => focusClaims.forEach(check => check()), 0)
        document.addEventListener('focusin', recheck, true)
        document.addEventListener('focusout', recheck, true)
        document.addEventListener('pointerdown', recheck, true)
        // 'blur' on window: alt-tab, devtools, another app. The pointer may come back anywhere.
        window.addEventListener('blur', clear)
        // pointer left the page entirely — a fast exit can outrun the row's own pointerleave
        document.documentElement.addEventListener('pointerleave', clear)
        // vuedraggable and the like capture the pointer; no leave is ever delivered
        document.addEventListener('pointercancel', clear, true)
        document.addEventListener('dragstart', clear, true)
    }

    // Identity of this component instance. Not the property id: the same property can be shown
    // by several rows at once, and they must not clear each other. One token for both maps.
    const token = Symbol('hover')
    let pointing = false
    let editing = false

    function enter() {
        pointing = true
        hover.setHover(token, propertyId())
    }

    function leave() {
        pointing = false
        hover.clearHover(token)
    }

    // viaDom: the claim comes from a real focus inside `root`, so it can be verified against
    // document.activeElement. Editors that focus a teleported popup instead pass false and stay
    // in charge of releasing it themselves — nothing inside the row is focused for them.
    function setFocus(on: boolean, viaDom = false) {
        editing = on
        if (!on) {
            focusClaims.delete(checkClaim)
            hover.clearFocus(token)
            return
        }
        hover.setFocus(token, propertyId())
        if (viaDom && root) focusClaims.add(checkClaim)
    }

    // The row no longer holds focus and never got the focusout that would have said so.
    function checkClaim() {
        if (!editing) return focusClaims.delete(checkClaim)
        if (!root?.value?.contains(document.activeElement)) setFocus(false)
    }

    // A recycled row keeps the DOM node under a motionless pointer and swaps the property
    // behind it: no enter, no leave, and the store would keep pointing at the old one.
    watch(propertyId, id => {
        if (pointing) hover.setHover(token, id)
        if (editing) hover.setFocus(token, id)
    })

    onUnmounted(() => {
        leave()
        setFocus(false)
    })

    return { enter, leave, setFocus, propertyId }
}
