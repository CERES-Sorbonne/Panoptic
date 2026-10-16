/**
 * V2 — the slot pool behind VirtualScroller: lines that stay in range keep their slot and are not
 * re-rendered, entering lines reuse freed slots, the top line stays put on a relayout, and lists
 * past the browser's height limit are paged.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { HEADER, LayoutSource, LineRef, ScrollLayout, lineKey } from '@/components/scrollers/virtual/scrollLayout'
import { Motion, Slot, ViewHost, ViewRange, VirtualView } from '@/components/scrollers/virtual/virtualView'

const VH = 600

/** Groups 1..groups under root 0, each with `lines(id)` lines of `size` px and a 30px header. */
function groupsSource(groups: number, lines: (id: number) => number, size = 50) {
    const open = new Set<number>()
    for (let i = 1; i <= groups; i++) open.add(i)
    const src: LayoutSource = {
        root: () => 0,
        childCount: id => id === 0 ? groups : 0,
        child: (_, i) => i + 1,
        isOpen: id => id === 0 || open.has(id),
        headerSize: id => id === 0 ? 0 : 30,
        bodyLines: id => id === 0 ? 0 : lines(id),
        lineEstimate: () => size,
        lineType: (_, i) => i < 0 ? 'group' : 'images',
    }
    return { src, open }
}

function fakeHost() {
    const placed = new Map<number, { y: number | null, size: number | undefined }>()
    // Pending timers, with the clock time they are due at.
    const timers: { fn: () => void, at: number }[] = []
    const ranges: ViewRange[] = []
    const motions: Motion[] = []
    let clock = 0
    const h = {
        scrollTop: 0,
        contentHeight: 0,
        renders: 0,
        placed, timers, ranges, motions,
        tick(ms: number) { clock += ms },
        // Runs every pending timer, due or not.
        idle() { const t = timers.splice(0); t.forEach(t => t.fn()) },
        // Moves the clock on, running the timers that fall due.
        advance(ms: number) {
            clock += ms
            for (let t; (t = timers.find(t => t.at <= clock));) {
                timers.splice(timers.indexOf(t), 1)
                t.fn()
            }
        },
    }
    const host: ViewHost = {
        viewportHeight: () => VH,
        scrollTop: () => h.scrollTop,
        setScrollTop: px => { h.scrollTop = px },
        setContentHeight: px => { h.contentHeight = px },
        createSlot: (id, type) => {
            // Counts the renders a Vue slot would do: one per new line value.
            let value: LineRef | null = null
            return {
                id, type, key: null, top: 0, size: 0,
                line: {
                    get value() { return value },
                    set value(v) { if (v !== value) { value = v; if (v) h.renders++ } },
                },
            } as Slot
        },
        place: (slot, y, size) => { placed.set(slot.id, { y, size }) },
        range: r => { ranges.push(r) },
        motion: m => { motions.push(m) },
        now: () => clock,
        setTimer: (fn, ms) => { const t = { fn, at: clock + ms }; timers.push(t); return t },
        clearTimer: t => { const i = timers.indexOf(t as typeof timers[number]); if (i >= 0) timers.splice(i, 1) },
    }
    return { h, host }
}

const options = { overscan: 100, lead: 1, measured: false, tail: 0, fastSpeed: 3, idleDelay: 120 }

function setup(groups = 200, lines: (id: number) => number = () => 5, maxHeight?: number) {
    const { src, open } = groupsSource(groups, lines)
    const layout = new ScrollLayout(src)
    layout.rebuild()
    const { h, host } = fakeHost()
    const view = new VirtualView(layout, host, { ...options }, maxHeight)
    view.relayout()
    const scroll = (top: number, dt = 50) => {
        h.tick(dt)
        h.scrollTop = top
        view.onScroll()
    }
    return { layout, view, h, src, open, scroll }
}

/** Mounted slots: each shows a distinct line, at its layout offset (physical), covering the viewport. */
function assertPlaced(s: ReturnType<typeof setup>) {
    const { view, layout, h } = s
    const seen = new Set<string>()
    let minTop = Infinity, maxBottom = -Infinity
    for (const slot of view.slots) {
        const p = h.placed.get(slot.id)
        if (slot.key === null) {
            assert.equal(p?.y ?? null, null, `free slot ${slot.id} is hidden`)
            continue
        }
        const ref = slot.line.value!
        assert.equal(lineKey(ref), slot.key)
        assert.ok(!seen.has(slot.key), `line ${slot.key} mounted twice`)
        seen.add(slot.key)
        assert.equal(p!.y, layout.offsetOf(ref) - view.pager.offset, `slot of ${slot.key} placed at its offset`)
        assert.equal(p!.size, layout.sizeOf(ref))
        minTop = Math.min(minTop, layout.offsetOf(ref))
        maxBottom = Math.max(maxBottom, layout.offsetOf(ref) + layout.sizeOf(ref))
    }
    const top = view.virtualTop
    assert.ok(minTop <= top, 'the viewport top is covered')
    assert.ok(maxBottom >= Math.min(layout.height, top + VH), 'the viewport bottom is covered')
}

test('V2: scrolling re-renders only the lines that come into range', () => {
    const s = setup()
    assertPlaced(s)
    const slotsAfterMount = s.view.slots.length
    const rendersAfterMount = s.h.renders
    const refs = new Map(s.view.slots.filter(x => x.key).map(x => [x.key, x.line.value]))
    s.scroll(40)
    assertPlaced(s)
    // A line still in range keeps its very LineRef object (Vue sees no change).
    for (const slot of s.view.slots) {
        if (slot.key && refs.has(slot.key)) assert.equal(slot.line.value, refs.get(slot.key))
    }
    let y = 40
    for (let k = 0; k < 300; k++) {
        y += 37
        s.scroll(y)
        assertPlaced(s)
    }
    const scrolled = y - 40
    // Renders: about one per line scrolled into range, never all mounted lines per step.
    const linesScrolled = scrolled / 46
    assert.ok(s.h.renders - rendersAfterMount < linesScrolled * 1.5 + 30, `${s.h.renders - rendersAfterMount} renders for ~${linesScrolled} lines`)
    // The pool does not grow with the distance scrolled.
    assert.ok(s.view.slots.length <= slotsAfterMount * 3, `${s.view.slots.length} slots after scrolling, ${slotsAfterMount} at mount`)
})

test('V2: opening a group above the viewport keeps what is on screen in place', () => {
    const s = setup()
    s.scroll(5000)
    const top = s.layout.locate(s.view.virtualTop)!
    const screenY = s.layout.offsetOf(top) - s.view.virtualTop
    const before = new Map(s.view.slots.filter(x => x.key).map(x => [x.key, x.line.value]))
    const renders = s.h.renders
    // Close group 3 (above the viewport).
    s.open.delete(3)
    s.layout.refreshNode(3)
    s.view.relayout()
    assertPlaced(s)
    assert.equal(s.layout.offsetOf(top) - s.view.virtualTop, screenY, 'the top line did not move on screen')
    assert.equal(s.h.renders, renders, 'nothing re-rendered: the same lines are in range')
    for (const slot of s.view.slots) if (slot.key) assert.equal(slot.line.value, before.get(slot.key))
})

test('V2: relayout with rerender hands every mounted slot a new LineRef; scale anchor keeps the fraction', () => {
    const { src } = groupsSource(100, () => 5)
    let size = 50
    src.lineEstimate = () => size
    const layout = new ScrollLayout(src)
    layout.rebuild()
    const { h, host } = fakeHost()
    const view = new VirtualView(layout, host, { ...options })
    view.relayout()
    h.scrollTop = 3000 + 25
    view.onScroll()
    const at = layout.locate(view.virtualTop)!
    const within = view.virtualTop - at.top
    const oldSize = layout.sizeOf(at)
    const mounted = view.slots.filter(x => x.key).length
    const renders = h.renders
    size = 100
    layout.refresh()
    view.relayout({ anchor: 'scale', rerender: true })
    assert.equal(view.virtualTop, layout.offsetOf(at) + within * layout.sizeOf(at) / oldSize)
    assert.ok(h.renders - renders >= mounted - 2, 're-rendered the mounted lines')
})

test('V2: relayout with rerender gives the range again, even over the same lines', () => {
    // The owners read their instance ids off the range: after a rebuild the same lines can hold
    // other images, and a range kept back as unchanged would leave those images unloaded.
    const s = setup()
    s.scroll(3000)
    s.h.idle()
    const n = s.h.ranges.length
    s.view.relayout()
    assert.equal(s.h.ranges.length, n, 'a plain relayout over the same lines gives no range')
    s.view.relayout({ rerender: true })
    assert.equal(s.h.ranges.length, n + 1, 'a rerender gives the range again')
    assert.notEqual(s.h.ranges.at(-1), s.h.ranges.at(-2), 'as a new object, so a shallowRef sees it')
})

test('V2: a list past the height limit is paged, and every line can still be reached', () => {
    // 100k groups of 5 lines: ~28M px.
    const s = setup(100_000, () => 5, 2_000_000)
    assert.ok(s.view.pager.paged)
    assert.equal(s.h.contentHeight, 2_000_000)
    // Small steps across a page boundary keep content still and placed.
    let y = 0
    for (let k = 0; k < 200; k++) {
        y += 300
        s.scroll(y)
        if (s.h.scrollTop !== y) y = s.h.scrollTop
        assertPlaced(s)
    }
    // Jump to the very end (scrollbar drag).
    s.scroll(2_000_000 - VH)
    assertPlaced(s)
    assert.ok(Math.abs(s.view.virtualTop - (s.layout.height - VH)) < 1, 'the end is reachable')
    // scrollTo a group deep down.
    s.view.scrollTo(77_777)
    assertPlaced(s)
    assert.equal(s.view.virtualTop, s.layout.offsetOf({ node: 77_777, index: HEADER }))
})

test('V2: ranges are emitted on change only, held while flinging; free slots empty out when idle', () => {
    const s = setup()
    const n0 = s.h.ranges.length
    s.scroll(1, 50)
    s.scroll(2, 50)
    assert.ok(s.h.ranges.length - n0 <= 1, 'a pixel of scrolling is not a new range')
    // Fling: 20px/ms.
    const held = s.h.ranges.length
    for (let k = 1; k <= 10; k++) s.scroll(2 + k * 320, 16)
    assert.equal(s.h.motions.at(-1), 'fast')
    assert.equal(s.h.ranges.length, held, 'no range while flinging')
    // The fling goes on (a momentum glide): the latest range is given every fastRangeEvery ms.
    s.h.advance(100)
    assert.equal(s.h.motions.at(-1), 'fast')
    assert.equal(s.h.ranges.length, held + 1, 'the latest range is given while the fling goes on')
    assert.equal(lineKey(s.h.ranges.at(-1)!.visible[0]), lineKey(s.layout.locate(s.view.virtualTop)!))
    for (let k = 11; k <= 15; k++) s.scroll(2 + k * 320, 16)
    assert.equal(s.h.ranges.length, held + 1, 'one range per fastRangeEvery ms at most')
    s.h.advance(100)
    assert.equal(s.h.ranges.length, held + 2)
    s.h.idle()
    assert.equal(s.h.motions.at(-1), 'idle')
    assert.ok(s.h.ranges.length > held, 'the range is given once the fling stops')
    const last = s.h.ranges.at(-1)!
    assert.equal(lineKey(last.visible[0]), lineKey(s.layout.locate(s.view.virtualTop)!))
    for (const slot of s.view.slots) if (slot.key === null) assert.equal(slot.line.value, null, 'idle free slots render nothing')
})

test('V2: the prefetch range leads in the scroll direction', () => {
    const s = setup()
    // Slowly (1px/ms): a fling would hold the range.
    for (let y = 100; y <= 4000; y += 100) s.scroll(y, 100)
    let r = s.h.ranges.at(-1)!
    assert.equal(r.direction, 1)
    assert.ok(s.layout.offsetOf(r.prefetch[1]) >= s.view.virtualTop + VH * 2 - 100)
    for (let y = 3900; y >= 3000; y -= 100) s.scroll(y, 100)
    r = s.h.ranges.at(-1)!
    assert.equal(r.direction, -1)
    assert.ok(s.layout.offsetOf(r.prefetch[0]) <= s.view.virtualTop - VH + 100)
})
