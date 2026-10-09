/**
 * Windowing shared by the image scrollers (grid, tree, image, cluster).
 *
 * RecycleScroller makes its content as tall as all its items, and a list of a few hundred
 * thousand rows goes past the browser's height limit (see scrollPager.ts). So the scroller
 * is never given the whole list: it gets the lines around the viewport plus two padding
 * items that hold the space above and below, sized so the total stays under the limit.
 *
 * The owner keeps the full line list and calls `setLines` when it changes (or `refresh`
 * after changing line sizes in place). It renders `windowLines` in the RecycleScroller and
 * renders nothing for `PAD_TYPE` items. Positions and indices given to and returned by this
 * composable are virtual (in the full list), never the scroller's own scrollTop or item index.
 *
 * How much is mounted, and when (two margins, two different jobs):
 *
 * - `buffer` (returned, bound to the RecycleScroller's own `:buffer`) is what gets MOUNTED: the
 *   scroller draws the items crossing [scrollTop - buffer, scrollTop + height + buffer], and only
 *   those. It is what the compositor can scroll into before the main thread catches up, so it is
 *   the margin against blank flashes: max(the tallest line, `minBuffer`) — one whole line ready on
 *   each side, and never less than one fast trackpad frame (~150-250px) when the lines are short.
 *   A scrollbar drag outruns any margin; that blank is unavoidable.
 * - The window is only what the scroller CAN mount without being handed a new list. The scroller
 *   (vue-virtual-scroller 2.0.1) treats a new `items` array as a whole new list: it releases every
 *   view and hands them back out in reverse order, so every line on screen re-renders with another
 *   line's data — cards, images and all. A window that followed the viewport line by line did that
 *   on almost every scroll event (both of its edges move a line at a time). So the window is kept
 *   while it still covers the mounted range plus `LEAD_SCREENS` of a viewport, and when it no
 *   longer does it is rebuilt with `REBUILD_SCREENS` viewports of slack on each side: one full
 *   re-render per screen and a half scrolled instead of one per line. The slack costs nothing to
 *   mount (the scroller ignores items outside its range); it widens what the owners derive from
 *   `windowRange`, the instances they load — the lead is there so the lines about to be mounted
 *   are always among them, their values asked for before they are drawn.
 *   `setLines`/`refresh` hand the scroller a new list as well, with the same full re-render:
 *   batch size changes (`refreshSoon`) rather than refreshing per line.
 *
 * Sizes measured on screen (rows that fit their content) go through `updateSizes` instead, which
 * hands the scroller no new list while the window still covers what it mounts: the scroller's
 * size table is cached on its `items` array, so changing sizes in place on the same array is
 * invisible to it — `restoreCache(null)` is what makes it re-read them. That sets its internal
 * size cache to a new empty object, its sizes are recomputed from the items, and its watcher on
 * them runs a non-forced update: every view keeps its line, only positions move. (Checked on the
 * real 2.0.1 `useRecycleScroller`: a plain `updateVisibleItems(false)` still sees the old sizes.)
 * The line at the top of the viewport keeps its place on screen, so rows above it growing or
 * shrinking do not move what is shown.
 *
 * The window check runs in the scroll handler. The scroller updates after it (on the new list
 * right away, on its own animation frame otherwise), so it always finds its range in the window.
 */
import { onUnmounted, shallowRef, watch, nextTick, Ref, ShallowRef } from 'vue'
import { ScrollPager } from './scrollPager'

export const PAD_TYPE = '__pad__'

export interface PagedLine {
    id: string | number
    size: number
}

interface PadLine {
    id: string
    type: typeof PAD_TYPE
    size: number
    data: null
}

export interface PagedLinesOptions {
    // The RecycleScroller component instance.
    scroller: Ref<any>
    viewportHeight: () => number
    // Least px mounted above and below the viewport; the tallest line raises it (see `buffer`).
    // 400 is what the scrollers that do not bind `buffer` give their RecycleScroller.
    minBuffer?: number
}

// Slack, in viewports, put on each side of the mounted range when the window is rebuilt, and how
// much of it must be left ahead of the mounted range for the window to be kept. One can scroll
// their difference before the next rebuild (and its full re-render, see the header).
const REBUILD_SCREENS = 2
const LEAD_SCREENS = 0.5

export function usePagedLines<T extends PagedLine>(options: PagedLinesOptions) {
    const minBuffer = options.minBuffer ?? 400
    const pager = new ScrollPager()
    // Px the scroller mounts beyond the viewport, to bind to its `:buffer` (see the header).
    const buffer = shallowRef(minBuffer) as ShallowRef<number>

    let lines: T[] = []
    let cumSizes: number[] = [0]   // cumSizes[i] = total height of lines[0..i-1]
    let winStart = -1
    let winEnd = -1

    const windowLines = shallowRef([]) as Ref<(T | PadLine)[]>
    // Full-list index range of the lines in the window, both ends included (end < start when
    // there is none). Reactive, so what the window shows can be derived from it.
    const windowRange = shallowRef({ start: 0, end: -1 })

    function el(): HTMLElement | undefined {
        return options.scroller.value?.$el
    }

    // Line index whose row contains virtual pixel `px`.
    function lineAt(px: number): number {
        if (px <= 0 || !lines.length) return 0
        let lo = 0, hi = lines.length - 1
        while (lo < hi) {
            const mid = (lo + hi) >> 1
            if (cumSizes[mid + 1] <= px) lo = mid + 1
            else hi = mid
        }
        return lo
    }

    // Full-list index range of the lines crossing virtual [from, to], minus those above the page
    // offset: nothing there can be on screen.
    function lineRange(from: number, to: number): [number, number] {
        let start = lineAt(Math.max(pager.offset, from))
        const end = lineAt(to)
        // The line straddling the offset would be drawn from the top of the content, shifted.
        if (cumSizes[start] < pager.offset && start < end) start++
        return [start, end]
    }

    // Does the window hold what the scroller mounts from here, and the lead?
    function windowCovers(): boolean {
        if (winStart < 0) return false
        const vh = options.viewportHeight()
        const top = pager.virtualTop
        const margin = buffer.value
        const lead = LEAD_SCREENS * vh
        const [needStart, needEnd] = lineRange(top - margin - lead, top + vh + margin + lead)
        return winStart <= needStart && winEnd >= needEnd
    }

    function padSizes(start: number, end: number): [number, number] {
        return [
            Math.max(0, cumSizes[start] - pager.offset),
            Math.max(0, pager.physicalHeight - (cumSizes[end + 1] - pager.offset)),
        ]
    }

    function rebuildWindow(force = false) {
        if (!lines.length) {
            winStart = winEnd = -1
            windowLines.value = []
            windowRange.value = { start: 0, end: -1 }
            return
        }
        const vh = options.viewportHeight()
        const top = pager.virtualTop
        const bottom = top + vh
        const margin = buffer.value
        // Keep the window while it holds what the scroller mounts from here, and the lead.
        if (!force && windowCovers()) return
        // Wider than the lead, or the next scroll event would rebuild again.
        const slack = Math.max(REBUILD_SCREENS * vh, margin)
        const [start, end] = lineRange(top - margin - slack, bottom + margin + slack)
        if (start === winStart && end === winEnd && !force) return
        winStart = start
        winEnd = end

        const [topPad, bottomPad] = padSizes(start, end)
        const items: (T | PadLine)[] = []
        if (topPad > 0) items.push({ id: '__pad_top__', type: PAD_TYPE, size: topPad, data: null })
        for (let i = start; i <= end; i++) items.push(lines[i])
        if (bottomPad > 0) items.push({ id: '__pad_bottom__', type: PAD_TYPE, size: bottomPad, data: null })
        windowLines.value = items
        windowRange.value = { start, end }
    }

    // Sets the scroller's scrollTop once the new window is rendered (before that, the browser
    // would clamp it to the old content height).
    function applyPhysical(physical: number) {
        nextTick(() => {
            const e = el()
            if (e && Math.abs(e.scrollTop - physical) >= 1) e.scrollTop = physical
        })
    }

    // cumSizes, the buffer and the pager from the lines' sizes; the physical scrollTop that keeps
    // the virtual position.
    function computeSizes(): number {
        const n = lines.length
        cumSizes = new Array(n + 1)
        cumSizes[0] = 0
        let tallest = 0
        for (let i = 0; i < n; i++) {
            const size = lines[i].size
            cumSizes[i + 1] = cumSizes[i] + size
            if (size > tallest) tallest = size
        }
        buffer.value = Math.max(minBuffer, tallest)
        return pager.setSizes(cumSizes[n], options.viewportHeight())
    }

    function measure() {
        const physical = computeSizes()
        rebuildWindow(true)
        applyPhysical(physical)
    }

    // After sizes changed in place: lays the current window out again without handing the scroller
    // a new list (see the header), when the window still covers what it mounts and keeps its pads.
    // False when it has to be rebuilt instead.
    function relayoutWindow(): boolean {
        const s = options.scroller.value
        if (typeof s?.restoreCache !== 'function' || !windowCovers()) return false
        const items = windowLines.value
        const first = items[0], last = items[items.length - 1]
        const hasTop = first?.id === '__pad_top__', hasBottom = last?.id === '__pad_bottom__'
        const [topPad, bottomPad] = padSizes(winStart, winEnd)
        if (hasTop !== topPad > 0 || hasBottom !== bottomPad > 0) return false
        if (hasTop) first.size = topPad
        if (hasBottom) last.size = bottomPad
        s.restoreCache(null)
        return true
    }

    /**
     * Changes line sizes in place — `apply` does it, and says whether anything changed — keeping the
     * line at the top of the viewport where it is on screen. Meant for sizes measured on screen,
     * once per frame for all of them: no new list for the scroller unless the window no longer
     * covers what it mounts (see the header).
     */
    function updateSizes(apply: () => boolean): boolean {
        // The anchor is read off the sizes before the change.
        const top = pager.virtualTop
        const anchor = lineAt(top)
        const within = top - (cumSizes[anchor] ?? 0)
        if (!apply()) return false
        const offset = pager.offset
        computeSizes()
        const anchorSize = lines[anchor]?.size ?? 0
        const physical = pager.scrollTo((cumSizes[anchor] ?? 0) + Math.min(within, anchorSize))
        // A page switch moves every line on the physical axis: that is a new window.
        if (pager.offset !== offset || !relayoutWindow()) rebuildWindow(true)
        // The scroller lays out on its old scrollTop first; when the anchor moved it, bring its
        // mounted range there in the same frame, or what scrolled in would be blank for a frame.
        nextTick(() => {
            const e = el()
            if (!e || Math.abs(e.scrollTop - physical) < 1) return
            e.scrollTop = physical
            options.scroller.value?.updateVisibleItems?.(false)
        })
        return true
    }

    /** Replaces the full line list. Keeps the virtual scroll position. */
    function setLines(next: T[]) {
        lines = next
        refreshQueued = false
        measure()
    }

    /** Call after changing line sizes in place. */
    function refresh() {
        refreshQueued = false
        measure()
    }

    // Same, once for all the calls made in this tick (rows report their height one by one).
    let refreshQueued = false
    function refreshSoon() {
        if (refreshQueued) return
        refreshQueued = true
        queueMicrotask(() => { if (refreshQueued) refresh() })
    }

    function onScroll() {
        const e = el()
        if (!e) return
        const r = pager.onScroll(e.scrollTop)
        if (r.adjustTo !== undefined) e.scrollTop = r.adjustTo
        rebuildWindow(r.adjustTo !== undefined)
    }

    function getScrollTop() {
        return pager.virtualTop
    }

    function scrollToPosition(virtualTop: number) {
        const physical = pager.scrollTo(virtualTop)
        rebuildWindow(true)
        applyPhysical(physical)
    }

    function scrollToIndex(index: number) {
        if (index === undefined || index < 0 || index >= lines.length) return
        scrollToPosition(cumSizes[index])
    }

    /** Full-list index of the item at `windowIndex` in `windowLines`. */
    function lineIndex(windowIndex: number): number {
        const hasTopPad = windowLines.value[0]?.id === '__pad_top__'
        return winStart + windowIndex - (hasTopPad ? 1 : 0)
    }

    /** Virtual offset of a line (the height of everything above it). */
    function lineOffset(index: number): number {
        return cumSizes[Math.max(0, Math.min(index, lines.length))] ?? 0
    }

    watch(options.viewportHeight, () => measure())

    // The scroller can be mounted later than its owner (v-if), or re-created.
    let listened: HTMLElement | undefined
    watch(el, (e) => {
        if (e === listened) return
        listened?.removeEventListener('scroll', onScroll)
        listened = e
        if (!e) return
        e.addEventListener('scroll', onScroll, { passive: true })
        // A new element starts at the top: show the current position.
        applyPhysical(pager.scrollTo(pager.virtualTop))
    }, { immediate: true, flush: 'post' })
    onUnmounted(() => listened?.removeEventListener('scroll', onScroll))

    return {
        windowLines,
        windowRange,
        buffer,
        setLines,
        refresh,
        refreshSoon,
        updateSizes,
        getScrollTop,
        scrollToPosition,
        scrollToIndex,
        lineIndex,
        lineOffset,
        lineAt,
    }
}
