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
 */
import { onUnmounted, ref, shallowRef, watch, nextTick, Ref } from 'vue'
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
    // Px rendered above and below the viewport.
    buffer?: number
    // Make the window deeply reactive (the grid edits line sizes through the rendered items).
    deep?: boolean
}

export function usePagedLines<T extends PagedLine>(options: PagedLinesOptions) {
    const buffer = options.buffer ?? 800
    const pager = new ScrollPager()

    let lines: T[] = []
    let cumSizes: number[] = [0]   // cumSizes[i] = total height of lines[0..i-1]
    let winStart = -1
    let winEnd = -1

    const windowLines = (options.deep ? ref([]) : shallowRef([])) as Ref<(T | PadLine)[]>
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

    function rebuildWindow(force = false) {
        if (!lines.length) {
            winStart = winEnd = -1
            windowLines.value = []
            windowRange.value = { start: 0, end: -1 }
            return
        }
        const top = pager.virtualTop
        // Nothing above the page offset can be on screen.
        let start = lineAt(Math.max(pager.offset, top - buffer))
        const end = lineAt(top + options.viewportHeight() + buffer)
        if (cumSizes[start] < pager.offset && start < end) start++
        if (!force && start === winStart && end === winEnd) return
        winStart = start
        winEnd = end

        const topPad = Math.max(0, cumSizes[start] - pager.offset)
        const bottomPad = Math.max(0, pager.physicalHeight - (cumSizes[end + 1] - pager.offset))
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

    function measure() {
        const n = lines.length
        cumSizes = new Array(n + 1)
        cumSizes[0] = 0
        for (let i = 0; i < n; i++) cumSizes[i + 1] = cumSizes[i] + lines[i].size
        const physical = pager.setSizes(cumSizes[n], options.viewportHeight())
        rebuildWindow(true)
        applyPhysical(physical)
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
        setLines,
        refresh,
        refreshSoon,
        getScrollTop,
        scrollToPosition,
        scrollToIndex,
        lineIndex,
        lineOffset,
        lineAt,
    }
}
