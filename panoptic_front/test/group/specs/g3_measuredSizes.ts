/**
 * G3 — grid rows fit their content: measured heights are applied in one batch, in place, and the
 * line at the top of the viewport stays where it is on screen.
 *
 * The old adaptive rows froze the table: each cell measured itself with a forced layout, each
 * report refreshed the scroller (a new list, every mounted row re-rendered), which moved the
 * window, mounted more rows that measured again. Now one ResizeObserver per scroller reports the
 * rows whose height changed, all at once (RowHeights), and usePagedLines.updateSizes lays the
 * same window out again (RecycleScroller's `restoreCache(null)`, see its header) unless the window
 * no longer covers what the scroller mounts.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { effectScope, nextTick, shallowRef } from 'vue'
import { usePagedLines, PAD_TYPE } from '@/components/scrollers/usePagedLines'
import { RowHeights, RowHeightsEnv, entryHeight } from '@/components/scrollers/grid/rowHeights'
import type { ScrollerLine } from '@/components/scrollers/types'

const VH = 900

interface Line { id: number, type: string, size: number }

const rows = (n: number, size = 28): Line[] => Array.from({ length: n }, (_, id) => ({ id, type: 'image', size }))

function setup(lines: Line[]) {
    let onScroll: (() => void) | undefined
    const el = {
        scrollTop: 0,
        addEventListener: (_: string, f: () => void) => { onScroll = f },
        removeEventListener: () => { },
    }
    const calls = { restoreCache: 0, updateVisibleItems: 0 }
    const scroller = {
        $el: el,
        restoreCache: (snapshot: unknown) => { assert.equal(snapshot, null); calls.restoreCache++ },
        updateVisibleItems: (force: boolean) => { assert.equal(force, false); calls.updateVisibleItems++ },
    }
    const scope = effectScope()
    const paged = scope.run(() => usePagedLines<Line>({ scroller: shallowRef(scroller), viewportHeight: () => VH, minBuffer: 300 }))!
    paged.setLines(lines)
    return {
        paged, el, calls,
        scroll(top: number) { el.scrollTop = top; onScroll!() },
        stop: () => scope.stop(),
    }
}

/** On-screen y of line `i`'s top, as the scroller would draw it now. */
const screenTop = (s: ReturnType<typeof setup>, i: number) => s.paged.lineOffset(i) - s.paged.getScrollTop()

test('G3: measured sizes are applied in place — same window, no new list, the scroller re-reads its sizes', async () => {
    const lines = rows(2000)
    const s = setup(lines)
    await nextTick()    // setLines' own scrollTop, before scrolling
    s.scroll(28 * 500)
    await nextTick()
    const before = s.paged.windowLines.value
    const { start } = s.paged.windowRange.value
    const changed = s.paged.updateSizes(() => {
        for (let i = 500; i < 510; i++) lines[i].size = 80
        return true
    })
    assert.ok(changed)
    assert.equal(s.paged.windowLines.value, before, 'the same array: RecycleScroller keeps every view on its line')
    assert.equal(s.calls.restoreCache, 1)
    assert.equal(s.paged.lineOffset(510), 28 * 510 + 52 * 10)
    // The pads hold the space above and below the window: still exactly the rest of the list.
    const items = s.paged.windowLines.value
    const top = items[0], bottom = items[items.length - 1]
    assert.equal(top.type, PAD_TYPE)
    assert.equal(top.size, s.paged.lineOffset(start))
    assert.equal(bottom.type, PAD_TYPE)
    const total = s.paged.lineOffset(lines.length)
    assert.equal(items.reduce((a, l) => a + l.size, 0), total)
    await nextTick()
    assert.equal(s.calls.updateVisibleItems, 0, 'rows below the top line changed: scrollTop stays, nothing more to do')
    s.stop()
})

test('G3: rows above the viewport changing do not move what is on screen', async () => {
    const lines = rows(2000)
    const s = setup(lines)
    await nextTick()    // setLines' own scrollTop, before scrolling
    s.scroll(28 * 500 + 10)    // line 500 is at the top, 10px of it scrolled past
    await nextTick()
    const anchorY = screenTop(s, 500), belowY = screenTop(s, 520)
    // In the buffer above the viewport: grows. On screen below the anchor: grows too.
    s.paged.updateSizes(() => {
        for (let i = 490; i < 500; i++) lines[i].size = 100
        lines[505].size = 60
        return true
    })
    assert.equal(screenTop(s, 500), anchorY, 'the top line keeps its place')
    assert.equal(screenTop(s, 520), belowY + 32, 'lines below a grown row move down by its growth only')
    await nextTick()
    assert.equal(s.el.scrollTop, s.paged.getScrollTop(), 'scrollTop set to the anchored position')
    assert.equal(s.calls.updateVisibleItems, 1, 'and the scroller brought there in the same frame')

    // Shrinking above: same.
    s.paged.updateSizes(() => {
        for (let i = 490; i < 500; i++) lines[i].size = 28
        return true
    })
    assert.equal(screenTop(s, 500), anchorY)
    s.stop()
})

test('G3: nothing changed, nothing done; a window that no longer covers is rebuilt', async () => {
    const lines = rows(2000, 200)
    const s = setup(lines)
    await nextTick()    // setLines' own scrollTop, before scrolling
    s.scroll(200 * 1000)
    await nextTick()
    assert.equal(s.paged.updateSizes(() => false), false)
    assert.equal(s.calls.restoreCache, 0)
    // Every line collapses to 28px: the window (sized for 200px lines) no longer reaches the
    // bottom of what the scroller mounts, so it gets a new one.
    const before = s.paged.windowLines.value
    s.paged.updateSizes(() => { for (const l of lines) l.size = 28; return true })
    assert.notEqual(s.paged.windowLines.value, before)
    const { start, end } = s.paged.windowRange.value
    const top = s.paged.getScrollTop()
    assert.ok(s.paged.lineOffset(start) <= top - 300 && s.paged.lineOffset(end + 1) >= top + VH + 300)
    s.stop()
})

// ── RowHeights ───────────────────────────────────────────────────────────────

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
