// Placement shared by the tree cells whose editor is bigger than the 26px row it edits.
//
// Such an editor can't live in the cell: the scrollers virtualize and clip their cells, so it is
// teleported to the body and parked on the cell instead. Everything here is MEASURED off the live
// cell — its box, its icon's box, its text metrics — rather than re-derived from the frame's CSS,
// so opening an editor moves nothing: the icon and the first line of text stay on the pixels they
// occupied while reading.
import { onBeforeUnmount, nextTick, ref, Ref } from 'vue'
// the popup's own chrome (.cell-popup / .popup-icon), shared by every input using this
import './cellPopup.css'

export function useCellPopup(frame: Ref<any>) {
    const popupElem = ref(null)
    const popup = ref({
        top: 0, left: 0, width: 0,
        // the cell's own width and right padding: the floor and the frame setWidth() grows within
        cellWidth: 0, rightPad: 0,
        // both boxes are placed from the cell's own measurements, not re-derived from its CSS
        icon: { top: 0, left: 0, width: 0, height: 0, fontSize: '' },
        contentLeft: 0, contentWidth: 0,
        // the cell's own insets from its edges to its value box: an editor that pads itself by
        // these is exactly as tall as the cell, with its first line on the cell's value line
        padTop: 0, padBottom: 0,
        // set by fit() when the editor would otherwise run past the bottom of the window
        maxHeight: 0,
        // extra width paid to the vertical scrollbar that the cap brings, so the content keeps
        // its full width instead of being pushed under a horizontal scrollbar too
        scrollbar: 0,
        text: {} as Record<string, string>,
    })

    // Parks the popup ON the cell: same top-left, same width, so a popup that hasn't grown yet is
    // the cell, pixel for pixel. It carries the property icon too, so it lines its own icon column
    // up with the one it covers; its CONTENT is put back on the value's line by padding itself
    // with the cell's own insets (padTop / padBottom / contentLeft) rather than by moving the box.
    function place() {
        const zone = frame.value?.valueZone as HTMLElement
        const cell = frame.value?.root as HTMLElement
        if (!zone || !cell) return

        const rect = cell.getBoundingClientRect()
        const zoneRect = zone.getBoundingClientRect()
        const iconElem = frame.value?.iconZone as HTMLElement
        const iconRect = iconElem?.getBoundingClientRect()
        const style = getComputedStyle(zone)

        popup.value = {
            top: rect.top,
            left: rect.left,
            // starts as the cell; setWidth() grows it only as far as the content actually needs
            width: rect.width,
            cellWidth: rect.width,
            rightPad: rect.right - zoneRect.right,
            // Offsets from the cell's top-left, which is the popup's own — and, since the icon is
            // absolutely positioned, the origin it is laid out from, whatever padding the popup
            // gives its in-flow content. fontSize included because the icon IS a font glyph, and
            // the popup hangs off the body: it inherits none of the cell's sizing and would
            // otherwise draw at the browser default.
            icon: iconRect
                ? {
                    top: iconRect.top - rect.top, left: iconRect.left - rect.left,
                    width: iconRect.width, height: iconRect.height,
                    fontSize: getComputedStyle(iconElem).fontSize,
                }
                : { top: 0, left: 0, width: 0, height: 0, fontSize: '' },
            contentLeft: zoneRect.left - rect.left,
            contentWidth: zoneRect.width,
            padTop: zoneRect.top - rect.top,
            padBottom: rect.bottom - zoneRect.bottom,
            maxHeight: 0,
            scrollbar: 0,
            // Copied rather than restated: the cell's font depends on which scroller renders it.
            // Property by property, not via the `font` shorthand — that shorthand serializes to ''
            // whenever it can't represent the computed style, which silently drops an editor back
            // to its own default font and shifts every line off the text it replaced.
            text: {
                fontFamily: style.fontFamily,
                fontSize: style.fontSize,
                fontWeight: style.fontWeight,
                fontStyle: style.fontStyle,
                letterSpacing: style.letterSpacing,
                lineHeight: style.lineHeight,
            },
        }
    }

    // The cell's width is the default: the popup only grows when its content needs more room, and
    // never past `maxWidth` (nor the window). `needed` is the width of the CONTENT alone.
    function setWidth(needed: number, maxWidth: number) {
        const p = popup.value
        const ceiling = Math.min(maxWidth, window.innerWidth)
        p.width = Math.max(p.cellWidth, Math.min(p.contentLeft + needed + p.rightPad, ceiling))
        p.contentWidth = p.width - p.contentLeft - p.rightPad
    }

    // Fixed to the viewport, the popup would happily grow past its edges — off-screen content, and
    // a window the page can't scroll to reach. So keep the whole box inside the window: slide it
    // up (and left) to fit, and only when even that isn't enough, cap its height and let it scroll
    // inside itself. `contentElem` is measured rather than the popup, whose own height may still
    // be capped from a previous fit().
    // `chrome` is whatever the caller adds around the content (its own vertical padding), which
    // measuring the content alone misses.
    function fit(contentElem: HTMLElement, chrome = 0) {
        const p = popup.value
        if (!popupElem.value || !contentElem) return

        p.maxHeight = 0
        const height = contentElem.offsetHeight + chrome
        if (height > window.innerHeight) {
            p.maxHeight = window.innerHeight
            p.top = 0
        } else if (p.top + height > window.innerHeight) {
            p.top = window.innerHeight - height
        }

        if (!p.maxHeight) {
            p.scrollbar = 0
            return clampLeft()
        }
        // The cap may bring a vertical scrollbar, which on a classic (non-overlay) scrollbar
        // platform eats into the content width and would push the fixed-width content under a
        // HORIZONTAL one. Pay for it in width instead — measurable only once the cap is applied.
        nextTick(() => {
            const capped = popupElem.value as HTMLElement
            if (!capped) return
            p.scrollbar = capped.offsetWidth - capped.clientWidth
            clampLeft()
        })
    }

    function clampLeft() {
        const p = popup.value
        p.left = Math.max(0, Math.min(p.left, window.innerWidth - p.width - p.scrollbar))
    }

    // Teleported to the body, the popup does not follow the scroller: rather than track it, close
    // on any scroll or resize, which is what clicking away does anyway. A capped popup scrolling
    // inside itself is not the scroller moving out from under it, so those are ignored.
    let onViewportMove: (e?: Event) => void = null
    let onOutside: (e: MouseEvent) => void = null

    function watchViewport(close: () => void) {
        stopWatch()
        onViewportMove = (e?: Event) => {
            const elem = popupElem.value as HTMLElement
            if (e && elem && e.target instanceof Node && elem.contains(e.target)) return
            close()
        }
        // Clicking away closes too. An editor that commits on blur gets this for free, but one
        // whose focus lives in a teleported menu (the tag picker) does not.
        onOutside = (e: MouseEvent) => {
            const elem = popupElem.value as HTMLElement
            const cell = frame.value?.root as HTMLElement
            if (!(e.target instanceof Node)) return
            if (elem?.contains(e.target) || cell?.contains(e.target)) return
            close()
        }
        // Focusing can itself scroll an ancestor (the browser reveals the focused element), so the
        // listeners go on only once that settled — otherwise the popup closes on the very scroll
        // its own opening caused.
        requestAnimationFrame(() => {
            if (!onViewportMove) return
            // capture: the scroller scrolls its own element, which doesn't bubble
            window.addEventListener('scroll', onViewportMove, true)
            window.addEventListener('resize', onViewportMove)
            window.addEventListener('mousedown', onOutside, true)
        })
    }

    function stopWatch() {
        if (onViewportMove) {
            window.removeEventListener('scroll', onViewportMove, true)
            window.removeEventListener('resize', onViewportMove)
            onViewportMove = null
        }
        if (onOutside) {
            window.removeEventListener('mousedown', onOutside, true)
            onOutside = null
        }
    }

    onBeforeUnmount(stopWatch)

    return { popup, popupElem, place, setWidth, fit, watchViewport, stopWatch }
}
