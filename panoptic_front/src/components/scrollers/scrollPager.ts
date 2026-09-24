/**
 * Maps a very tall list onto a scroll area of bounded height.
 *
 * Browsers cannot lay out an element past a fixed height: about 17.9M px in Firefox, about
 * 33.5M px in Chrome and WebKit. Past it Firefox silently draws nothing, with no error. A
 * scroller that is as tall as its content (220k grid rows of 104px = 22.9M px) goes blank.
 *
 * The list keeps its real ("virtual") height `th`, but the DOM is only `h = min(th, max)`
 * tall. The virtual range is cut in `n` pages; each page shifts the content up by `offset`,
 * so virtual position = physical scrollTop + offset. A row at virtual `y` is drawn at
 * physical `y - offset`. (Same scheme as SlickGrid.)
 *
 * - A small scroll (wheel, keys: less than a viewport) moves 1:1. When it crosses into
 *   another page, the offset changes and the physical scrollTop is moved by the same amount
 *   (`adjustTo`), so the content does not move; only the scrollbar thumb does, a little.
 * - A large scroll (scrollbar drag, page jump) maps the thumb position proportionally onto
 *   the whole list.
 *
 * When `th <= max` there is one page and offset is 0: physical and virtual are the same.
 */

// Well under Firefox's limit (17,895,697 px).
export const MAX_SCROLL_PX = 8_000_000

// Pages per physical height. More pages = smaller thumb jumps at page switches.
const PAGES_PER_HEIGHT = 100

export interface ScrollResult {
    virtualTop: number
    // Physical scrollTop to set, when the scroll switched page.
    adjustTo?: number
}

export class ScrollPager {
    private th = 0          // virtual height
    private vh = 0          // viewport height
    private h = 0           // physical height
    private ph = 1          // page height
    private n = 1           // number of pages
    private cj = 0          // offset added per page
    private page = 0
    private lastPhysical = 0
    offset = 0
    virtualTop = 0

    constructor(private readonly maxPx = MAX_SCROLL_PX) { }

    get physicalHeight() { return this.h }
    get virtualHeight() { return this.th }
    get paged() { return this.n > 1 }

    /**
     * Sets the list and viewport heights. Keeps the current virtual position (clamped to the
     * new height) and returns the physical scrollTop that shows it.
     */
    setSizes(virtualHeight: number, viewportHeight: number): number {
        this.th = Math.max(0, virtualHeight)
        this.vh = Math.max(0, viewportHeight)
        this.h = Math.min(this.th, this.maxPx)
        if (this.th <= this.maxPx) {
            this.n = 1
            this.ph = Math.max(1, this.h)
            this.cj = 0
        } else {
            this.ph = this.h / PAGES_PER_HEIGHT
            this.n = Math.ceil(this.th / this.ph)
            this.cj = (this.th - this.h) / (this.n - 1)
        }
        return this.scrollTo(this.virtualTop)
    }

    /** Handles the scroller's scroll event, given its physical scrollTop. */
    onScroll(physicalTop: number): ScrollResult {
        const delta = Math.abs(physicalTop - this.lastPhysical)
        this.lastPhysical = physicalTop
        // No move, or the echo of our own adjustment.
        if (delta === 0 || this.n === 1) {
            this.virtualTop = physicalTop + this.offset
            return { virtualTop: this.virtualTop }
        }
        if (delta < this.vh) {
            const physical = this.scrollTo(physicalTop + this.offset)
            if (physical !== physicalTop) return { virtualTop: this.virtualTop, adjustTo: physical }
            return { virtualTop: this.virtualTop }
        }
        // Jump: pick the page that puts this thumb position at its proportional place. The
        // offsets are multiples of cj, so the error is at most cj / 2 (under half a page).
        const range = this.h - this.vh
        const target = range > 0 ? physicalTop * (this.th - this.vh) / range : 0
        this.setPage(Math.round((target - physicalTop) / this.cj))
        this.virtualTop = physicalTop + this.offset
        return { virtualTop: this.virtualTop }
    }

    /**
     * Moves to a virtual position (clamped to the list) and returns the physical scrollTop to
     * set. The caller must set it: the next onScroll then sees no move.
     */
    scrollTo(virtualTop: number): number {
        const v = Math.max(0, Math.min(virtualTop, this.th - this.vh))
        if (this.n > 1) {
            this.setPage(Math.floor(v / this.ph))
            // Keep the physical position inside the scroll range.
            const maxPhysical = Math.max(0, this.h - this.vh)
            while (this.page < this.n - 1 && v - this.offset > maxPhysical) this.setPage(this.page + 1)
            while (this.page > 0 && v - this.offset < 0) this.setPage(this.page - 1)
        } else {
            this.setPage(0)
        }
        this.virtualTop = v
        this.lastPhysical = v - this.offset
        return this.lastPhysical
    }

    private setPage(page: number) {
        this.page = Math.max(0, Math.min(this.n - 1, page))
        this.offset = Math.round(this.page * this.cj)
    }
}
