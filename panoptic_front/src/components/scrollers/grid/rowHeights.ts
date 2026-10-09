/**
 * Grid rows fit their content: each mounted row is measured by one ResizeObserver per scroller.
 *
 * Rows used to be measured cell by cell: every cell read its own clientHeight in a nextTick (a
 * forced layout per cell), the row took the tallest and pushed it back down to its cells as a
 * min-height, and every report refreshed the scroller — which moved the window, mounted more rows
 * that measured again, and froze the table in waves. Here:
 *  - a row is laid out at its natural height (its cells stretch to the tallest, in CSS) and nothing
 *    in it depends on the size the scroller gives its line, so what is measured is never an echo of
 *    what was assigned;
 *  - the observer is told about every row at once, after layout and before paint, without any
 *    forced layout; the rows whose height differs from their line's size (by a pixel or more) are
 *    handed over together, once per frame, and the owner applies them in one go
 *    (usePagedLines.updateSizes) — before that frame is painted;
 *  - a row component is reused for other lines as the scroller recycles it: the element is
 *    observed once, the line it shows is read when it is measured, and it is measured again when it
 *    is given another line (`remeasure`) — the new line's size may be wrong even if the element
 *    keeps its height.
 *
 * Rows mounted while a batch is being applied (the scroller mounting more once positions moved)
 * are observed from the next frame: observing them during the observer's own delivery would leave
 * notifications undelivered, which the browser reports as an error ("ResizeObserver loop").
 *
 * No Vue, no stores: RowLine registers its element, GridScroller applies the sizes, the tests
 * drive it with a fake observer.
 */
import type { InjectionKey } from 'vue'
import type { ScrollerLine } from '../types'

export interface RowHeightsEnv {
    createObserver(callback: (entries: readonly ResizeObserverEntry[]) => void): Pick<ResizeObserver, 'observe' | 'unobserve' | 'disconnect'>
    nextFrame(callback: () => void): void
}

const browserEnv: RowHeightsEnv = {
    createObserver: callback => new ResizeObserver(callback),
    nextFrame: callback => requestAnimationFrame(callback),
}

// The height an entry reports for its row, in whole pixels; 0 when it is not laid out.
export function entryHeight(entry: Pick<ResizeObserverEntry, 'borderBoxSize' | 'contentRect'>): number {
    const box = entry.borderBoxSize?.[0]
    return Math.round(box ? box.blockSize : entry.contentRect.height)
}

export class RowHeights {
    // Each observed row element, and the line it shows now.
    private rows = new Map<Element, () => ScrollerLine | undefined>()
    private observer: ReturnType<RowHeightsEnv['createObserver']> | undefined
    // Set while a batch is being applied, until the next frame (see the header).
    private settling = false
    private deferred = new Set<Element>()

    constructor(
        // The rows whose height changed, with their new height. Called at most once per frame.
        private readonly onResize: (changes: Map<ScrollerLine, number>) => void,
        private readonly env: RowHeightsEnv = browserEnv,
    ) { }

    /** Starts measuring a row element; `line` gives the line it shows when it is measured. */
    observe(el: Element, line: () => ScrollerLine | undefined) {
        this.rows.set(el, line)
        this.watch(el)
    }

    unobserve(el: Element) {
        this.rows.delete(el)
        this.deferred.delete(el)
        this.observer?.unobserve(el)
    }

    /** The row was given another line: measure it again even if its height does not change. */
    remeasure(el: Element) {
        if (!this.rows.has(el)) return
        this.observer?.unobserve(el)
        this.watch(el)
    }

    /** The lines on the rows mounted now. */
    mountedLines(): Set<ScrollerLine> {
        const lines = new Set<ScrollerLine>()
        for (const line of this.rows.values()) {
            const l = line()
            if (l) lines.add(l)
        }
        return lines
    }

    disconnect() {
        this.observer?.disconnect()
        this.observer = undefined
        this.rows.clear()
        this.deferred.clear()
    }

    private watch(el: Element) {
        if (this.settling) {
            this.deferred.add(el)
            return
        }
        // An observed element is always reported once, with its size, after its next layout.
        this.observer ??= this.env.createObserver(entries => this.onEntries(entries))
        this.observer.observe(el)
    }

    private onEntries(entries: readonly ResizeObserverEntry[]) {
        const changes = new Map<ScrollerLine, number>()
        for (const entry of entries) {
            const line = this.rows.get(entry.target)?.()
            if (!line) continue
            const height = entryHeight(entry)
            // 0: not laid out (a hidden pane): its last size stands.
            if (height <= 0 || Math.abs(height - line.size) < 1) continue
            changes.set(line, height)
        }
        if (!changes.size) return
        this.settling = true
        this.env.nextFrame(() => {
            this.settling = false
            const deferred = [...this.deferred]
            this.deferred.clear()
            for (const el of deferred) if (this.rows.has(el)) this.watch(el)
        })
        this.onResize(changes)
    }
}

export const rowHeightsKey: InjectionKey<RowHeights> = Symbol('rowHeights')
