/**
 * G2 — the window handed to the RecycleScroller is rebuilt rarely, and always holds what it mounts.
 *
 * vue-virtual-scroller 2.0.1 takes a new `items` array as a new list: it releases every view and
 * hands them back out in reverse order, so each line on screen re-renders with another line's
 * data. The window used to follow the viewport line by line, i.e. a new array on almost every
 * scroll event. usePagedLines now keeps it while it covers the scroller's mounted range
 * (viewport ± `buffer`) plus half a viewport, and rebuilds it with two viewports of slack on each
 * side.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { effectScope, shallowRef } from 'vue'
import { usePagedLines, PAD_TYPE } from '@/components/scrollers/usePagedLines'

const VH = 900

interface Line { id: number, type: string, size: number }

/** A tree-like list: a 30px group line, then `perGroup` card lines of `card` px. */
function treeList(groups: number, perGroup: number, card: number): Line[] {
    const lines: Line[] = []
    let id = 0
    for (let g = 0; g < groups; g++) {
        lines.push({ id: id++, type: 'group', size: 30 })
        for (let i = 0; i < perGroup; i++) lines.push({ id: id++, type: 'images', size: card })
    }
    return lines
}

/** usePagedLines on a fake scrolling element; `scroll(top)` fires its scroll handler. */
function setup(lines: Line[], minBuffer?: number) {
    let onScroll: (() => void) | undefined
    const el = {
        scrollTop: 0,
        addEventListener: (_: string, f: () => void) => { onScroll = f },
        removeEventListener: () => { },
    }
    const scope = effectScope()
    const paged = scope.run(() => usePagedLines<Line>({
        scroller: shallowRef({ $el: el }), viewportHeight: () => VH, minBuffer,
    }))!
    paged.setLines(lines)
    let rebuilds = 0
    let last = paged.windowLines.value
    return {
        paged,
        scroll(top: number) {
            el.scrollTop = top
            onScroll!()
            if (paged.windowLines.value !== last) { rebuilds++; last = paged.windowLines.value }
        },
        get rebuilds() { return rebuilds },
        stop: () => scope.stop(),
    }
}

/** The window's lines, in order, without the pads. */
function windowLineIds(w: { type?: string, id: string | number }[]) {
    return w.filter(l => l.type !== PAD_TYPE).map(l => l.id as number)
}

/** Fails unless every line crossing [from, to] is in the window. */
function assertCovers(lines: Line[], s: ReturnType<typeof setup>, from: number, to: number) {
    const { start, end } = s.paged.windowRange.value
    let y = 0
    for (let i = 0; i < lines.length; i++) {
        const top = y
        y += lines[i].size
        if (y <= from || top >= to) continue
        assert.ok(i >= start && i <= end, `line ${i} [${top}, ${y}) crosses [${from}, ${to}] but the window is ${start}..${end}`)
    }
}

test('G2: the buffer is the tallest line, at least minBuffer', () => {
    const tall = setup(treeList(10, 5, 466), 300)
    assert.equal(tall.paged.buffer.value, 466)
    tall.stop()
    const short = setup(treeList(10, 5, 106), 300)
    assert.equal(short.paged.buffer.value, 300)
    short.stop()
})

test('G2: wheel scrolling keeps the mounted range in the window, rebuilding once per screen and a half', () => {
    const lines = treeList(400, 6, 330)
    const total = lines.reduce((a, l) => a + l.size, 0)
    const s = setup(lines, 300)
    const buffer = s.paged.buffer.value
    const span = 40_000
    for (let top = 0; top <= span; top += 120) {
        s.scroll(top)
        // The mounted range, and the half screen of lead beyond it whose instances are loaded.
        assertCovers(lines, s, top - buffer - VH / 2, Math.min(total, top + VH + buffer + VH / 2))
    }
    // The old window (800px around the viewport) was rebuilt about twice per 330px line here.
    assert.ok(s.rebuilds <= Math.ceil(span / (1.5 * VH)) + 1, `${s.rebuilds} rebuilds over ${span}px`)
    assert.ok(s.rebuilds >= 1)

    // Back up: same rule.
    const before = s.rebuilds
    for (let top = span; top >= 0; top -= 120) {
        s.scroll(top)
        assertCovers(lines, s, top - buffer - VH / 2, top + VH + buffer + VH / 2)
    }
    assert.ok(s.rebuilds - before <= Math.ceil(span / (1.5 * VH)) + 1)
    s.stop()
})

test('G2: a jump lands inside a fresh window; a small move after it does not rebuild', () => {
    const lines = treeList(400, 6, 330)
    const s = setup(lines, 300)
    const buffer = s.paged.buffer.value
    s.scroll(250_000)
    assertCovers(lines, s, 250_000 - buffer, 250_000 + VH + buffer)
    const n = s.rebuilds
    const w = windowLineIds(s.paged.windowLines.value)
    s.scroll(250_000 + 500)
    assert.equal(s.rebuilds, n)
    assert.deepEqual(windowLineIds(s.paged.windowLines.value), w)
    s.stop()
})

test('G2: setLines and scrollToPosition always hand a new window', () => {
    const lines = treeList(50, 6, 330)
    const s = setup(lines, 300)
    const w = s.paged.windowLines.value
    s.paged.scrollToPosition(0)
    assert.notEqual(s.paged.windowLines.value, w)
    const w2 = s.paged.windowLines.value
    s.paged.setLines(lines.map(l => ({ ...l, size: l.type === 'images' ? 400 : l.size })))
    assert.notEqual(s.paged.windowLines.value, w2)
    assert.equal(s.paged.buffer.value, 400)
    s.stop()
})
