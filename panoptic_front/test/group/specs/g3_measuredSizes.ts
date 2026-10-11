/**
 * G3 — grid rows fit their content: measured heights are applied in one batch, and the line at
 * the top of the viewport stays where it is on screen.
 *
 * The old adaptive rows froze the table: each cell measured itself with a forced layout, each
 * report refreshed the scroller (a new list, every mounted row re-rendered), which moved the
 * window, mounted more rows that measured again. Now one ResizeObserver per scroller reports the
 * rows whose height changed, all at once (RowHeights); VirtualScroller hands them to
 * ScrollLayout.setMeasured (one leaf each, O(log)) and lays the slots out again in one relayout:
 * no slot is given another line by it.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { RowHeights, RowHeightsEnv, entryHeight } from '@/components/scrollers/grid/rowHeights'
import type { ScrollerLine } from '@/components/scrollers/types'
import { LayoutSource, LineRef, ScrollLayout, lineKey } from '@/components/scrollers/virtual/scrollLayout'
import { Slot, ViewHost, VirtualView } from '@/components/scrollers/virtual/virtualView'

const VH = 900

/** VirtualScroller's measuring loop on a flat list of `n` rows of 28px, minus the DOM. */
function measuredView(n: number) {
    const src: LayoutSource = {
        root: () => 0, childCount: () => 0, child: () => 0, isOpen: () => true, headerSize: () => 0,
        bodyLines: () => n, lineEstimate: () => 28, lineType: () => 'image',
    }
    const layout = new ScrollLayout(src)
    layout.rebuild()
    let scrollTop = 0, renders = 0
    const host: ViewHost = {
        viewportHeight: () => VH,
        scrollTop: () => scrollTop,
        setScrollTop: px => { scrollTop = px },
        setContentHeight: () => { },
        createSlot: (id, type) => {
            let value: LineRef | null = null
            return {
                id, type, key: null, top: 0, size: 0,
                line: { get value() { return value }, set value(v) { if (v !== value) { value = v; if (v) renders++ } } },
            } as Slot
        },
        place: () => { },
        now: () => 0,
        setTimer: () => 0,
        clearTimer: () => { },
    }
    const view = new VirtualView(layout, host, { overscan: 300, lead: 1, measured: true, tail: 0, fastSpeed: 3, idleDelay: 120 })
    view.relayout()
    // What the component does with a batch.
    const apply = (changes: Map<LineRef, number>) => {
        let changed = false
        for (const [line, px] of changes) changed = layout.setMeasured(line, px) || changed
        if (changed) view.relayout()
        return changed
    }
    return {
        layout, view, apply,
        get renders() { return renders },
        scroll(top: number) { scrollTop = top; view.onScroll() },
        mounted: () => view.slots.filter(s => s.key !== null),
    }
}

test('G3: measured sizes are applied in one relayout; no mounted row is handed another line', () => {
    const s = measuredView(2000)
    s.scroll(28 * 500)
    const before = new Map(s.mounted().map(slot => [slot.key, slot.line.value]))
    const renders = s.renders
    const changes = new Map<LineRef, number>()
    for (const slot of s.mounted()) if (slot.line.value!.index < 510) changes.set(slot.line.value!, 80)
    assert.ok(s.apply(changes))
    // Rows still in range keep their slot and LineRef; rows that grew push others out of range.
    for (const slot of s.mounted()) if (before.has(slot.key)) assert.equal(slot.line.value, before.get(slot.key))
    assert.ok(s.renders - renders <= 2, 'growing rows only drops lines out of range')
    for (const [line] of changes) assert.equal(s.layout.sizeOf(line), 80)
})

test('G3: rows above the viewport changing do not move what is on screen', () => {
    const s = measuredView(2000)
    s.scroll(28 * 500 + 10)
    const top = s.layout.locate(s.view.virtualTop)!
    const screenY = s.layout.offsetOf(top) - s.view.virtualTop
    // Rows 490..499, mounted in the overscan above the viewport, measure taller.
    const above = s.mounted().map(slot => slot.line.value!).filter(l => l.index >= 490 && l.index < 500)
    assert.ok(above.length > 0)
    s.apply(new Map(above.map(l => [l, 60])))
    assert.equal(s.layout.offsetOf(top) - s.view.virtualTop, screenY, 'the top row did not move on screen')
    assert.equal(s.layout.height, 2000 * 28 + above.length * 32)
})

test('G3: nothing changed, nothing done', () => {
    const s = measuredView(100)
    const line = s.mounted()[0].line.value!
    assert.equal(s.apply(new Map([[line, 28]])), false)
    assert.equal(lineKey(line), '0:0')
})

interface FakeEntry { target: object, borderBoxSize: { blockSize: number, inlineSize: number }[], contentRect: { height: number } }

function fakeEnv() {
    const observed = new Set<object>()
    const frames: (() => void)[] = []
    let callback: ((entries: any[]) => void) | undefined
    const env: RowHeightsEnv = {
        createObserver: cb => {
            callback = cb as any
            return {
                observe: (el: Element) => { observed.add(el) },
                unobserve: (el: Element) => { observed.delete(el) },
                disconnect: () => observed.clear(),
            }
        },
        nextFrame: cb => { frames.push(cb) },
    }
    const entry = (target: object, height: number): FakeEntry =>
        ({ target, borderBoxSize: [{ blockSize: height, inlineSize: 100 }], contentRect: { height } })
    return {
        env, observed, entry,
        deliver: (entries: FakeEntry[]) => callback!(entries),
        frame: () => { const f = frames.splice(0); f.forEach(cb => cb()) },
    }
}

const line = (id: number, size = 28): ScrollerLine => ({ id, type: 'image', size })

test('G3 RowHeights: one batch per delivery, only real changes, whole pixels', () => {
    const f = fakeEnv()
    const batches: Map<ScrollerLine, number>[] = []
    const r = new RowHeights(c => batches.push(c), f.env)
    const a = {}, b = {}, c = {}, hidden = {}
    const la = line(1), lb = line(2), lc = line(3), lh = line(4)
    r.observe(a as Element, () => la)
    r.observe(b as Element, () => lb)
    r.observe(c as Element, () => lc)
    r.observe(hidden as Element, () => lh)
    f.deliver([f.entry(a, 80.4), f.entry(b, 28.3), f.entry(c, 55.6), f.entry(hidden, 0)])
    assert.equal(batches.length, 1)
    assert.deepEqual([...batches[0]].map(([l, h]) => [l.id, h]), [[1, 80], [3, 56]],
        'sub-pixel noise and an unlaid-out row (0) are not changes')
    f.deliver([f.entry(b, 28)])
    assert.equal(batches.length, 1, 'no change, no call')
    assert.equal(entryHeight({ borderBoxSize: undefined as any, contentRect: { height: 41.5 } as DOMRectReadOnly }), 42)
})

test('G3 RowHeights: a recycled row is read as the line it shows now, and measured again', () => {
    const f = fakeEnv()
    const batches: Map<ScrollerLine, number>[] = []
    const r = new RowHeights(c => batches.push(c), f.env)
    const el = {} as Element
    let current = line(1)
    r.observe(el, () => current)
    current = line(2, 100)
    r.remeasure(el)
    assert.ok(f.observed.has(el), 'observed again: the browser reports it once more')
    f.deliver([f.entry(el, 60)])
    assert.deepEqual([...batches[0]].map(([l, h]) => [l.id, h]), [[2, 60]])
    assert.deepEqual([...r.mountedLines()].map(l => l.id), [2])
    r.unobserve(el)
    assert.ok(!f.observed.has(el))
    assert.equal(r.mountedLines().size, 0)
})

test('G3 RowHeights: rows mounted while a batch is applied are observed from the next frame', () => {
    const f = fakeEnv()
    const r = new RowHeights(() => {
        // The scroller mounts a row in reaction (positions moved): observing it inside the
        // delivery would leave it undelivered ("ResizeObserver loop" error).
        r.observe(late, () => line(9))
    }, f.env)
    const first = {} as Element, late = {} as Element
    r.observe(first, () => line(1))
    f.deliver([f.entry(first, 50)])
    assert.ok(!f.observed.has(late), 'held back during the delivery')
    assert.equal(r.mountedLines().size, 2, 'but already known as mounted')
    f.frame()
    assert.ok(f.observed.has(late), 'observed on the next frame')
    // Unmounted before that frame: never observed.
    const gone = {} as Element
    f.deliver([f.entry(first, 70)])
    r.unobserve(late)
    r.observe(gone, () => line(10))
    r.unobserve(gone)
    f.frame()
    assert.ok(!f.observed.has(gone))
})
