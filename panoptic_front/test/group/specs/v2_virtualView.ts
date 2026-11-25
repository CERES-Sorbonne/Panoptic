/**
 * V2 — the slot pool behind VirtualScroller: lines that stay in range keep their slot and are not
 * re-rendered, entering lines reuse freed slots, the top line stays put on a relayout, and lists
 * past the browser's height limit are paged.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { HEADER, LayoutSource, LineRef, ScrollLayout, lineKey } from '@/components/scrollers/virtual/scrollLayout'
import { Motion, Slot, Stick, ViewHost, ViewRange, VirtualView } from '@/components/scrollers/virtual/virtualView'

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
    const placed = new Map<number, { y: number | null, size: number | undefined, stick?: Stick }>()
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
        place: (slot, y, size, stick) => { placed.set(slot.id, { y, size, stick }) },
        range: r => { ranges.push(r) },
        motion: m => { motions.push(m) },
        now: () => clock,
        setTimer: (fn, ms) => { const t = { fn, at: clock + ms }; timers.push(t); return t },
        clearTimer: t => { const i = timers.indexOf(t as typeof timers[number]); if (i >= 0) timers.splice(i, 1) },
    }
    return { h, host }
}

const options = { overscan: 100, lead: 1, measured: false, tail: 0, fastSpeed: 3, idleDelay: 120 }

/**
 * Nested groups under root 0 (no header): `outer` groups 1..outer, each with `inner` groups
 * (id = 100 * outer + k), each a leaf of `lines` lines of 50px. Every group has a 30px header.
 */
function nestedSetup(outer = 3, inner = 3, lines = 40, maxHeight?: number, leaves: number[] = []) {
    // Outer groups in `leaves` show their lines themselves, without subgroups.
    const kids = (id: number) => id === 0 ? Array.from({ length: outer }, (_, i) => i + 1)
        : id <= outer && !leaves.includes(id) ? Array.from({ length: inner }, (_, k) => 100 * id + k + 1) : []
    const src: LayoutSource = {
        root: () => 0,
        childCount: id => kids(id).length,
        child: (id, i) => kids(id)[i],
        isOpen: () => true,
        headerSize: id => id === 0 ? 0 : 30,
        bodyLines: id => id > outer || leaves.includes(id) ? lines : 0,
        lineEstimate: () => 50,
        lineType: (_, i) => i < 0 ? 'group' : 'images',
    }
    const layout = new ScrollLayout(src)
    layout.rebuild()
    const { h, host } = fakeHost()
    const view = new VirtualView(layout, host, { ...options, sticky: true }, maxHeight)
    view.relayout()
    const scroll = (top: number, dt = 50) => {
        h.tick(dt)
        h.scrollTop = top
        view.onScroll()
    }
    const placedOf = (ref: LineRef) => {
        const slot = view.slots.find(x => x.key === lineKey(ref))
        return slot && h.placed.get(slot.id)
    }
    return { layout, view, h, scroll, placedOf }
}

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

test('V2: sticky headers span to the end of their parent\'s group, and the header of the group at the top stays mounted', () => {
    const s = setup(20, () => 100)
    s.view.options.sticky = true
    s.view.relayout()
    // Deep into group 3 (header at 2 * 5030), its header far above the mounted range.
    const g3 = s.layout.offsetOf({ node: 3, index: HEADER })
    for (const top of [g3 + 10, g3 + 2000, g3 + 4990]) {
        s.scroll(top)
        const mounted = s.view.slots.filter(x => x.key !== null)
        const header = mounted.find(x => x.key === lineKey({ node: 3, index: HEADER }))
        assert.ok(header, `header of group 3 mounted at ${top}`)
        const p = s.h.placed.get(header!.id)!
        assert.equal(p.y, g3 - s.view.pager.offset, 'placed at its own offset')
        assert.equal(p.size, s.layout.height - g3, 'spans down to the end of its parent, the root')
        assert.equal(p.stick?.top, 0)
        assert.equal(p.stick?.depth, 0)
        // Body lines keep their own size; the range does not start at the pinned header.
        for (const x of mounted) if (x.line.value!.index >= 0) assert.equal(s.h.placed.get(x.id)!.size, 50)
        assert.notDeepEqual(s.h.ranges[s.h.ranges.length - 1].mounted[0], { node: 3, index: HEADER })
    }
    // Closed, the same: down to the end of its parent.
    s.open.delete(3)
    s.layout.refreshNode(3)
    s.view.relayout()
    s.view.scrollTo(3)
    const header = s.view.slots.find(x => x.key === lineKey({ node: 3, index: HEADER }))!
    assert.equal(s.h.placed.get(header.id)!.size, s.layout.height - g3)
})

test('V2: nested sticky headers stack, each spanning down to the end of its parent\'s group', () => {
    const s = nestedSetup()
    const inner = 3 * (30 + 40 * 50), outer = 30 + inner
    // Deep into group 2's second subgroup (202): both headers far above the mounted range.
    const g202 = s.layout.offsetOf({ node: 202, index: HEADER })
    for (const top of [g202 + 10, g202 + 1000, g202 + 1990]) {
        s.scroll(top)
        const p2 = s.placedOf({ node: 2, index: HEADER })
        const p202 = s.placedOf({ node: 202, index: HEADER })
        assert.ok(p2 && p202, `both headers mounted at ${top}`)
        assert.equal(p2!.y, s.layout.offsetOf({ node: 2, index: HEADER }))
        assert.equal(p2!.size, s.layout.height - s.layout.offsetOf({ node: 2, index: HEADER }), 'the outer header spans to the end of the root')
        assert.deepEqual(p2!.stick, { top: 0, depth: 0, order: 0 })
        assert.equal(p202!.y, g202)
        assert.equal(p202!.size, s.layout.height - g202, 'the inner one too: every group has subgroups to take its place')
        assert.equal(p202!.stick?.top, 30, 'the inner header sticks below its parent')
        assert.equal(p202!.stick?.depth, 1)
        // Nothing else from groups 1 or 3 stays mounted.
        assert.equal(s.placedOf({ node: 1, index: HEADER }), undefined)
    }
    // The stuck headers over a line at the top, and scrollTo landing below them.
    assert.equal(s.view.stuckOver({ node: 202, index: 5 }), 60)
    assert.equal(s.view.stuckOver({ node: 202, index: HEADER }), 30)
    assert.equal(s.view.stuckOver({ node: 2, index: HEADER }), 0)
    s.view.scrollTo(202)
    assert.equal(s.view.virtualTop, g202 - 30)
    s.view.scrollTo({ node: 202, index: 5 })
    assert.equal(s.view.virtualTop, s.layout.offsetOf({ node: 202, index: 5 }) - 60)
    // Without the option, nothing sticks and nothing is covered.
    s.view.options.sticky = false
    assert.equal(s.view.stuckOver({ node: 202, index: 5 }), 0)
})

test('V2: headers deeper than the sticky band scroll by without sticking', () => {
    const s = nestedSetup()
    // 40px of a 600px viewport: room for one 30px header.
    s.view.options.stickyMax = 40 / VH
    const g202 = s.layout.offsetOf({ node: 202, index: HEADER })
    s.scroll(g202 + 1000)
    assert.deepEqual(s.placedOf({ node: 2, index: HEADER })!.stick, { top: 0, depth: 0, order: 0 })
    assert.equal(s.placedOf({ node: 202, index: HEADER }), undefined, 'not stuck, so not mounted that far below its header')
    assert.equal(s.view.stuckOver({ node: 202, index: 5 }), 30)
    s.scroll(g202 - 10)
    const p202 = s.placedOf({ node: 202, index: HEADER })!
    assert.equal(p202.stick, undefined)
    assert.equal(p202.size, 30, 'a header that does not stick spans itself only')
})

test('V2: a sticky header of a group starting pages above is cut to the page', () => {
    // 3 outer groups of 3 * 2030 + 30 px, paged at 4000 px.
    const s = nestedSetup(3, 3, 40, 4000)
    assert.ok(s.view.pager.paged)
    const g3 = s.layout.offsetOf({ node: 3, index: HEADER })
    s.view.scrollToOffset(g3 + 5000)
    const off = s.view.pager.offset
    assert.ok(off > g3, 'the group starts before the page')
    const p = s.placedOf({ node: 3, index: HEADER })!
    assert.ok(p.stick)
    assert.ok(p.y! <= 0 && p.y! >= -30, `starts at the page top (${p.y})`)
    assert.ok(p.y! + p.size! <= s.view.pager.physicalHeight, 'ends within the page')
    assert.equal(p.y! + p.size!, Math.min(s.layout.height - off, s.view.pager.physicalHeight), 'ends with its parent, the root')
})

test('V2: scrolling up, the headers stuck a viewport above the range are mounted already', () => {
    const s = nestedSetup()
    const g203 = s.layout.offsetOf({ node: 203, index: HEADER })
    s.scroll(g203 + 500)
    // Down: the range starts in 203, and nothing of 202 is mounted.
    assert.equal(s.placedOf({ node: 202, index: HEADER }), undefined)
    s.scroll(g203 + 400)
    // Up: 202's header is there before 203's slides back down over it.
    const p202 = s.placedOf({ node: 202, index: HEADER })
    assert.ok(p202?.stick, '202 mounted, stuck')
    assert.equal(p202!.stick!.top, 30)
    const keys = s.view.slots.filter(x => x.key !== null).map(x => x.key)
    assert.equal(new Set(keys).size, keys.length, 'no line mounted twice')
    // Down again: back to the headers of the range.
    s.scroll(g203 + 500)
    assert.equal(s.placedOf({ node: 202, index: HEADER }), undefined)
})

test('V2: at the end of a group, the next header is drawn over the stuck ones', () => {
    const s = nestedSetup()
    // 30px before the end of subgroup 202: its header stuck, 203's coming up right under it.
    s.scroll(s.layout.offsetOf({ node: 203, index: HEADER }) - 30 - 60)
    const p202 = s.placedOf({ node: 202, index: HEADER })!, p203 = s.placedOf({ node: 203, index: HEADER })!
    assert.equal(p202.stick!.depth, p203.stick!.depth)
    assert.ok(p203.stick!.order > p202.stick!.order, 'later over earlier at the same depth')
    // 30px before the end of group 2: its last subgroup and itself stuck, group 3 coming up.
    s.scroll(s.layout.offsetOf({ node: 3, index: HEADER }) - 30 - 60)
    const p2 = s.placedOf({ node: 2, index: HEADER })!, p3 = s.placedOf({ node: 3, index: HEADER })!
    const p203b = s.placedOf({ node: 203, index: HEADER })!
    assert.ok(p3.stick!.order > p2.stick!.order)
    assert.ok(p3.stick!.depth < p203b.stick!.depth, 'shallower over deeper')
    // Every header here has one to take its place (the next sibling, or the next group's first
    // subgroup for the last one): none is pushed out, each stays under the next.
    for (const [p, node] of [[p203b, 203], [p2, 2], [p202, 202]] as const) {
        assert.equal(p.size, s.layout.height - s.layout.offsetOf({ node, index: HEADER }), `span of ${node}`)
    }
    // Every header of the same depth mounted has its own order, in display order.
    const byDepth = new Map<number, { top: number, order: number }[]>()
    for (const slot of s.view.slots) {
        const p = s.h.placed.get(slot.id)
        if (slot.key === null || !p?.stick) continue
        const list = byDepth.get(p.stick.depth) ?? []
        list.push({ top: s.layout.offsetOf(slot.line.value!), order: p.stick.order })
        byDepth.set(p.stick.depth, list)
    }
    for (const list of byDepth.values()) {
        list.sort((a, b) => a.top - b.top)
        list.forEach((x, i) => assert.equal(x.order, i))
    }
})

test('V2: a stuck header nothing takes the place of is pushed out at the end of its group', () => {
    // Group 3 shows its lines itself: no subgroup comes after 203 to stick in its place.
    const s = nestedSetup(3, 3, 40, undefined, [3])
    const g3 = s.layout.offsetOf({ node: 3, index: HEADER })
    s.scroll(g3 - 100)
    const off = (node: number) => s.layout.offsetOf({ node, index: HEADER })
    const p203 = s.placedOf({ node: 203, index: HEADER })!
    assert.ok(p203.stick)
    assert.equal(p203.size, g3 - off(203), 'ends with its group: pushed out by group 3')
    // 202 stays under 203, as long as it does.
    s.scroll(off(203) - 100)
    assert.equal(s.placedOf({ node: 202, index: HEADER })!.size, g3 - off(202))
    // Group 2 has group 3 to take its place.
    assert.equal(s.placedOf({ node: 2, index: HEADER })!.size, s.layout.height - off(2))
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
