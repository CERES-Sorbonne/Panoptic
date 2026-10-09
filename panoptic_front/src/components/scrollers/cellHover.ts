// Hover on the read-only property cells of a scroller, handled once at the scroller's root.
//
// Each cell used to carry its own pointer listeners, a hover-store source and a tooltip (with its
// Teleport). Now the cells only carry data attributes (see cellAttrs) and the scroller listens
// for pointerover/pointerout on its root: one hover-store token, one tooltip, and a reactive
// `pointed` cell the cards read to mount the filter/copy buttons on the one row under the pointer.
import { InjectionKey, onUnmounted, ShallowRef, shallowRef } from 'vue'
import { installHoverListeners, useHoverStore } from '@/data/stores/hoverStore'
import { CellKey, sameCell } from './cellEditing'

// The cell under the pointer (see useCellHover's `pointed`), provided by the scroller to its cards.
export const cellPointedKey: InjectionKey<ShallowRef<CellKey | null>> = Symbol('cellPointed')

// The attributes a read-only cell carries, from which the delegate reads which cell it is.
export function cellAttrs(key: CellKey) {
    return {
        'data-cell-instance': key.instanceId,
        'data-cell-group': key.groupId,
        'data-cell-prop': key.propertyId,
    }
}

const CELL_SELECTOR = '[data-cell-prop]'

function cellKeyOf(el: HTMLElement): CellKey | null {
    const d = el.dataset
    if (d.cellProp === undefined) return null
    return { instanceId: Number(d.cellInstance), groupId: Number(d.cellGroup), propertyId: Number(d.cellProp) }
}

// The value zone and the values inside it each cut their own overflow with an ellipsis, so the
// cut can be on any of them. (Same rule as TreeCellFrame's tooltip.)
export function isClipped(zone: HTMLElement) {
    return [zone, ...Array.from(zone.querySelectorAll<HTMLElement>('*'))].some(e => e.scrollWidth > e.clientWidth)
}

export interface CellTip {
    text: string
    // the box the tooltip is placed against, and which it closes with once it is no longer hovered
    anchor: HTMLElement
}

export interface CellHoverOptions {
    // Full value of a cell, for cells whose rendering loses part of it (line breaks drawn as
    // icons, tags drawn as badges). Undefined: the text the cell shows.
    fullText?: (key: CellKey) => string | undefined
}

// Longer than wTT's default, since the pointer crosses rows constantly on its way elsewhere.
const TIP_DELAY = 400

export function useCellHover(options: CellHoverOptions = {}) {
    const hover = useHoverStore()
    installHoverListeners()
    // One token for the whole scroller: only one of its cells is ever under the pointer.
    const token = Symbol('cell-hover')

    // The row under the pointer, for the cards to mount its buttons. Like the per-row flag it
    // replaces, it only decides whether they exist; whether they SHOW is still the row's CSS
    // :hover, so a stale value costs a mount, never buttons stuck on another image.
    const pointed = shallowRef<CellKey | null>(null)
    const tip = shallowRef<CellTip | null>(null)

    let cellElem: HTMLElement | null = null
    let tipTimer: ReturnType<typeof setTimeout> | undefined

    function hideTip() {
        clearTimeout(tipTimer)
        if (tip.value) tip.value = null
    }

    function setCell(el: HTMLElement | null) {
        cellElem = el
        const key = el ? cellKeyOf(el) : null
        if (!sameCell(key, pointed.value)) pointed.value = key
        if (key) hover.setHover(token, key.propertyId)
        else hover.clearHover(token)
        hideTip()
        if (el) tipTimer = setTimeout(() => showTip(el), TIP_DELAY)
    }

    // Only when the row actually cuts its value: a tooltip repeating what is already readable
    // would pop up on every cell the pointer crosses.
    function showTip(el: HTMLElement) {
        if (el !== cellElem || !el.isConnected || !el.matches(':hover')) return
        const key = cellKeyOf(el)
        const zone = el.querySelector<HTMLElement>('.value-zone')
        if (!key || !zone || zone.querySelector('.empty') || !isClipped(zone)) return
        const text = options.fullText?.(key) ?? zone.innerText.trim()
        if (!text) return
        tip.value = { text, anchor: zone.parentElement ?? zone }
    }

    function onPointerOver(e: PointerEvent) {
        const el = (e.target as Element)?.closest?.(CELL_SELECTOR) as HTMLElement | null
        if (el && el === cellElem) {
            // A recycled row keeps its element under a still pointer and swaps the cell behind
            // it: no leave, no enter, and the hover would keep naming the old cell.
            if (!sameCell(cellKeyOf(el), pointed.value)) setCell(el)
            return
        }
        setCell(el)
    }

    function onPointerOut(e: PointerEvent) {
        if (!cellElem) return
        const to = e.relatedTarget as Node | null
        if (to && cellElem.contains(to)) return
        // Not on touch: every tap ends with a pointerleave, while the :hover it leaves behind
        // sticks. The buttons that tap revealed would then be gone by the next tap, the one
        // meant for them. The hover store is released all the same.
        if (e.pointerType === 'touch') {
            hover.clearHover(token)
            hideTip()
            return
        }
        setCell(null)
    }

    // the click it starts opens an editor over the row
    function onPointerDown() {
        hideTip()
    }

    onUnmounted(() => {
        clearTimeout(tipTimer)
        hover.clearHover(token)
    })

    return {
        pointed,
        tip,
        hideTip,
        listeners: { pointerover: onPointerOver, pointerout: onPointerOut, pointerdown: onPointerDown },
    }
}
