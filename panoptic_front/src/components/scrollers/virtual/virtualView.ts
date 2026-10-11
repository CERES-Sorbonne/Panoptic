/**
 * What VirtualScroller.vue does, minus Vue and the DOM: the pager, the slot pool, the range and
 * the motion state. The component gives it a host (the scrolling element, timers, how to make a
 * slot); the tests give it a fake one.
 *
 * Slot pool rules:
 *  - a slot is created for one pool type and keeps it; slots are never removed or reordered, so the
 *    DOM never moves and focus inside a slot survives scrolling;
 *  - a line that stays in range keeps its slot and its LineRef object, so it is not re-rendered;
 *  - a line leaving the range frees its slot (hidden, content kept so it can be patched rather
 *    than remounted); a line entering takes a free slot of its type, or a new one;
 *  - free slots drop their content once scrolling stops, and on relayout, so they never render a
 *    line that is gone;
 *  - positions are written by the host straight to the slot element, never through Vue.
 */
import { HEADER, lineKey } from './scrollLayout'
import type { LineRef, LocatedLine, NodeId, ScrollLayout } from './scrollLayout'
import { ScrollPager } from '../scrollPager'

export type Motion = 'idle' | 'scrolling' | 'fast'

export interface Slot {
    readonly id: number
    readonly type: string
    // The line shown (a shallowRef in the component). Replaced only when the slot is given
    // another line, or on a relayout that asks for a re-render.
    readonly line: { value: LineRef | null }
    // Key of the line while mounted; null while free.
    key: string | null
    // Virtual top and size of the line, as last placed.
    top: number
    size: number
}

export interface ViewRange {
    visible: [LineRef, LineRef]
    mounted: [LineRef, LineRef]
    prefetch: [LineRef, LineRef]
    direction: 1 | -1
}

export interface ViewHost {
    viewportHeight(): number
    scrollTop(): number
    setScrollTop(px: number): void
    // Physical height of the scrolled content.
    setContentHeight(px: number): void
    createSlot(id: number, type: string): Slot
    // Writes the slot's position: physical y, and its height when fixed (undefined = its own).
    // `null` hides it.
    place(slot: Slot, y: number | null, size: number | undefined): void
    // The slot was handed another line (to remeasure it).
    lineChanged?(slot: Slot): void
    range?(range: ViewRange): void
    motion?(motion: Motion): void
    now(): number
    setTimer(fn: () => void, ms: number): unknown
    clearTimer(handle: unknown): void
}

export interface ViewOptions {
    overscan: number
    // Viewports of prefetch range ahead in the scroll direction.
    lead: number
    // Slots size themselves (measured rows): their height is not written.
    measured: boolean
    // Px of space below the last line (a filler).
    tail: number
    fastSpeed: number
    idleDelay: number
    // Ms between ranges while motion is 'fast' (default 100): what is flown past is not loaded,
    // what the fling slows down over is, without waiting for it to stop.
    fastRangeEvery?: number
}

export type RelayoutAnchor = 'pixels' | 'scale'

interface Anchor {
    ref: LineRef
    within: number
    size: number
}

const sameRef = (a: LineRef | undefined, b: LineRef | undefined) =>
    a === b || (!!a && !!b && a.node === b.node && a.index === b.index)

export class VirtualView {
    readonly pager: ScrollPager
    readonly slots: Slot[] = []
    private byKey = new Map<string, Slot>()
    private free = new Map<string, Slot[]>()
    private anchor: Anchor | null = null
    private lastRange: ViewRange | null = null
    private heldRange: ViewRange | null = null
    private heldTimer: unknown = null
    private direction: 1 | -1 = 1
    private motionState: Motion = 'idle'
    private lastScrollAt = 0
    private lastScrollTop = 0
    private idleTimer: unknown
    private tallest = 0
    // Lines placed by the last update, in display order.
    private placed: LocatedLine[] = []
    // Slots handed a new line by the last update (for tests and stats).
    entered = 0

    constructor(
        public layout: ScrollLayout,
        private readonly host: ViewHost,
        public options: ViewOptions,
        maxHeight?: number,
    ) {
        this.pager = new ScrollPager(maxHeight)
    }

    get motion(): Motion {
        return this.motionState
    }

    get virtualTop(): number {
        return this.pager.virtualTop
    }

    get totalHeight(): number {
        return this.layout.height + this.options.tail
    }

    /** The lines mounted now, in display order. */
    mountedLines(): LineRef[] {
        return this.placed.map(l => this.byKey.get(lineKey(l))!.line.value!)
    }

    /** Where the tail (filler) starts, physical px. */
    tailTop(): number {
        return this.layout.height - this.pager.offset
    }

    // ── Scrolling ────────────────────────────────────────────────────────────

    onScroll() {
        const physical = this.host.scrollTop()
        const before = this.pager.virtualTop
        const r = this.pager.onScroll(physical)
        if (r.adjustTo !== undefined) this.host.setScrollTop(r.adjustTo)
        const top = this.pager.virtualTop
        const moved = top - before
        // The echo of a position set here (relayout, scrollTo): nothing moved.
        if (!moved && r.adjustTo === undefined) return
        const now = this.host.now()
        if (moved) this.direction = moved > 0 ? 1 : -1
        const dt = Math.max(1, now - this.lastScrollAt)
        const speed = Math.abs(top - this.lastScrollTop) / dt
        this.lastScrollAt = now
        this.lastScrollTop = top
        // A jump of more than a viewport (scrollbar drag, page key) is a fling too.
        const jump = Math.abs(moved) > this.host.viewportHeight()
        const fast = jump || speed > (this.motionState === 'fast' ? this.options.fastSpeed / 2 : this.options.fastSpeed)
        this.setMotion(fast ? 'fast' : 'scrolling')
        this.host.clearTimer(this.idleTimer)
        this.idleTimer = this.host.setTimer(() => this.onIdle(), this.options.idleDelay)
        this.update()
    }

    private onIdle() {
        this.setMotion('idle')
        // The mounted range was widened ahead while moving: back to normal.
        this.update()
        this.dropFreeContent()
    }

    private setMotion(m: Motion) {
        if (m === this.motionState) return
        const wasFast = this.motionState === 'fast'
        this.motionState = m
        this.host.motion?.(m)
        if (wasFast && m !== 'fast') this.releaseHeld()
    }

    /** Scrolls to a virtual offset. */
    scrollToOffset(virtualTop: number) {
        const physical = this.pager.scrollTo(virtualTop)
        this.lastScrollTop = this.pager.virtualTop
        this.host.setScrollTop(physical)
        this.update()
    }

    /** Scrolls to a node's top (its header) or to a line. A hidden node goes to its closed ancestor. */
    scrollTo(target: NodeId | LineRef, align: 'start' | 'center' | 'nearest' = 'start') {
        let ref: LineRef
        if (typeof target === 'number') {
            const node = this.layout.visibleAncestor(target)
            if (node === undefined) return
            ref = { node, index: HEADER }
        } else {
            ref = target
        }
        const top = this.layout.offsetOf(ref)
        const size = this.layout.sizeOf(ref)
        const vh = this.host.viewportHeight()
        let to = top
        if (align === 'center') to = top + size / 2 - vh / 2
        else if (align === 'nearest') {
            const cur = this.pager.virtualTop
            if (top >= cur && top + size <= cur + vh) return
            to = top < cur || size > vh ? top : top + size - vh
        }
        this.scrollToOffset(to)
    }

    // ── Layout changes ───────────────────────────────────────────────────────

    /**
     * After the layout changed (or the viewport): sizes the content again, keeps the line at the
     * top of the viewport where it is on screen, and reconciles the slots by key.
     *  - anchor 'pixels' keeps the same px of the top line above the viewport (rows that grew);
     *    'scale' keeps the same fraction of it (every line changed size).
     *  - rerender hands every mounted slot a new LineRef object, so it renders again: for changes
     *    the keys do not show (what a line draws changed, not which line it is).
     */
    relayout(opts: { anchor?: RelayoutAnchor, rerender?: boolean } = {}) {
        const layout = this.layout
        const a = this.anchor
        let target = this.pager.virtualTop
        if (a && layout.isShown(a.ref)) {
            const size = layout.sizeOf(a.ref)
            const within = opts.anchor === 'scale' && a.size > 0 ? a.within * size / a.size : Math.min(a.within, size)
            target = layout.offsetOf(a.ref) + within
        }
        this.pager.setSizes(this.totalHeight, this.host.viewportHeight())
        this.host.setContentHeight(this.pager.physicalHeight)
        const physical = this.pager.scrollTo(target)
        this.lastScrollTop = this.pager.virtualTop
        if (Math.abs(this.host.scrollTop() - physical) >= 1) this.host.setScrollTop(physical)
        this.dropFreeContent()
        if (opts.rerender) {
            for (const slot of this.byKey.values()) {
                const ref = slot.line.value
                if (ref) slot.line.value = { node: ref.node, index: ref.index }
            }
        }
        this.update()
    }

    /** The slot's content is laid out (its element exists): put it in place. */
    placeSlot(slot: Slot) {
        if (slot.key === null) this.host.place(slot, null, undefined)
        else this.host.place(slot, slot.top - this.pager.offset, this.fixedSize(slot))
    }

    // ── The update ───────────────────────────────────────────────────────────

    /** Reconciles the slots with the lines in range, and places them. */
    update() {
        const layout = this.layout
        const vh = this.host.viewportHeight()
        const top = this.pager.virtualTop
        const overscan = Math.max(this.options.overscan, this.tallest)
        // More room ahead while moving: what is about to come into view is already there.
        const ahead = this.motionState === 'idle' ? overscan : overscan * 2
        const from = Math.max(this.pager.offset, top - (this.direction < 0 ? ahead : overscan))
        const to = top + vh + (this.direction > 0 ? ahead : overscan)

        const want: LocatedLine[] = []
        let tallest = 0
        let line = layout.locate(from)
        while (line && line.top < to) {
            want.push(line)
            const size = layout.sizeOf(line)
            if (size > tallest) tallest = size
            line = this.after(line)
        }
        this.tallest = tallest

        const keep = new Set<string>()
        for (const l of want) keep.add(lineKey(l))
        for (const [key, slot] of this.byKey) {
            if (keep.has(key)) continue
            this.byKey.delete(key)
            slot.key = null
            this.freeList(slot.type).push(slot)
            this.host.place(slot, null, undefined)
        }

        let entered = 0
        for (const l of want) {
            const key = lineKey(l)
            let slot = this.byKey.get(key)
            if (!slot) {
                const type = layout.lineType(l)
                slot = this.takeSlot(type)
                slot.key = key
                this.byKey.set(key, slot)
                if (!sameRef(slot.line.value ?? undefined, l)) {
                    slot.line.value = { node: l.node, index: l.index }
                    entered++
                    this.host.lineChanged?.(slot)
                }
            }
            slot.top = l.top
            slot.size = layout.sizeOf(l)
            this.placeSlot(slot)
        }
        this.entered = entered
        this.placed = want

        // The anchor for the next relayout: the line at the top of the viewport.
        const at = layout.locate(top)
        this.anchor = at ? { ref: { node: at.node, index: at.index }, within: top - at.top, size: layout.sizeOf(at) } : null

        if (want.length) this.computeRange(want, top, vh)
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    private after(line: LocatedLine): LocatedLine | null {
        const end = line.top + this.layout.sizeOf(line)
        const next = end < this.layout.height ? this.layout.locate(end) : null
        // Never back onto a line already placed: the walk must always move down.
        return next && next.top > line.top ? next : null
    }

    private fixedSize(slot: Slot): number | undefined {
        // Measured scrollers size their body lines themselves; headers are always fixed.
        const ref = slot.line.value
        if (this.options.measured && ref && ref.index >= 0) return undefined
        return slot.size
    }

    private freeList(type: string): Slot[] {
        let list = this.free.get(type)
        if (!list) this.free.set(type, list = [])
        return list
    }

    private takeSlot(type: string): Slot {
        const free = this.freeList(type)
        const slot = free.pop()
        if (slot) return slot
        const created = this.host.createSlot(this.slots.length, type)
        this.slots.push(created)
        return created
    }

    // Free slots keep their content while scrolling (patched when reused, not remounted); once
    // scrolling stops, or the layout changed under them, they render nothing.
    private dropFreeContent() {
        for (const list of this.free.values()) {
            for (const slot of list) if (slot.line.value) slot.line.value = null
        }
    }

    private computeRange(want: LocatedLine[], top: number, vh: number) {
        const layout = this.layout
        const strip = (l: LineRef): LineRef => ({ node: l.node, index: l.index })
        const visFirst = layout.locate(top) ?? want[0]
        const visLast = layout.locate(top + vh - 1) ?? want[want.length - 1]
        const first = want[0], last = want[want.length - 1]
        const leadPx = this.options.lead * vh
        const prefetch: [LineRef, LineRef] = this.direction > 0
            ? [strip(first), strip(layout.locate(top + vh + leadPx) ?? last)]
            : [strip(layout.locate(top - leadPx) ?? first), strip(last)]
        const range: ViewRange = {
            visible: [strip(visFirst), strip(visLast)],
            mounted: [strip(first), strip(last)],
            prefetch,
            direction: this.direction,
        }
        this.emitRange(range)
    }

    private emitRange(range: ViewRange, force = false) {
        const last = this.lastRange
        if (!force && last && sameRef(last.visible[0], range.visible[0]) && sameRef(last.visible[1], range.visible[1])
            && sameRef(last.mounted[0], range.mounted[0]) && sameRef(last.mounted[1], range.mounted[1])
            && sameRef(last.prefetch[0], range.prefetch[0]) && sameRef(last.prefetch[1], range.prefetch[1])) return
        this.lastRange = range
        // Held while flinging, and given every fastRangeEvery ms: what is flown past is not worth
        // loading, but a momentum scroll glides on for a second or more after the hand has left.
        if (this.motionState === 'fast' && !force) {
            this.heldRange = range
            this.heldTimer ??= this.host.setTimer(() => {
                this.heldTimer = null
                this.releaseHeld()
            }, this.options.fastRangeEvery ?? 100)
            return
        }
        this.host.range?.(range)
    }

    private releaseHeld() {
        if (this.heldTimer !== null) this.host.clearTimer(this.heldTimer)
        this.heldTimer = null
        const r = this.heldRange
        this.heldRange = null
        if (r) this.emitRange(r, true)
    }

    dispose() {
        this.host.clearTimer(this.idleTimer)
        if (this.heldTimer !== null) this.host.clearTimer(this.heldTimer)
    }
}
