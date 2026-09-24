/**
 * G1 — a list taller than the browser's height limit scrolls inside a bounded scroll area.
 *
 * 220k grid rows of 104px (22.9M px) went past Firefox's ~17.9M px limit and the grid drew
 * nothing. ScrollPager keeps the DOM under MAX_SCROLL_PX and maps it onto the full list.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ScrollPager, MAX_SCROLL_PX } from '@/components/scrollers/scrollPager'

const VH = 800

test('G1: a list under the cap is not paged', () => {
    const p = new ScrollPager()
    p.setSizes(5_000_000, VH)
    assert.equal(p.paged, false)
    assert.equal(p.physicalHeight, 5_000_000)
    for (const s of [0, 1234, 4_000_000, 5_000_000 - VH]) {
        const r = p.onScroll(s)
        assert.equal(r.virtualTop, s)
        assert.equal(r.adjustTo, undefined)
        assert.equal(p.offset, 0)
    }
    assert.equal(p.scrollTo(3_000_000), 3_000_000)
})

for (const th of [22_880_000, 60_000_000]) {
    test(`G1: ${th}px stays under the cap and wheel scrolling is 1:1 to the end`, () => {
        const p = new ScrollPager()
        const start = p.setSizes(th, VH)
        assert.equal(p.paged, true)
        assert.ok(p.physicalHeight <= MAX_SCROLL_PX)
        assert.equal(start, 0)

        // Scroll like a wheel, 100px at a time, applying the adjustments like the scroller.
        let physical = 0
        let virtual = 0
        let switches = 0
        const maxPhysical = p.physicalHeight - VH
        while (virtual < th - VH) {
            const next = Math.min(physical + 100, maxPhysical)
            const r = p.onScroll(next)
            const expected = Math.min(virtual + (next - physical), th - VH)
            assert.equal(r.virtualTop, expected, `at physical ${next}`)
            physical = next
            if (r.adjustTo !== undefined) {
                switches++
                assert.ok(r.adjustTo >= 0 && r.adjustTo <= maxPhysical, `adjustTo ${r.adjustTo}`)
                physical = r.adjustTo
                // The scroll event echoing our adjustment does not move the content.
                assert.equal(p.onScroll(physical).virtualTop, expected)
            }
            // Rows are drawn at virtual - offset: the top of the viewport is at `physical`.
            assert.equal(r.virtualTop - p.offset, physical)
            virtual = r.virtualTop
        }
        assert.equal(virtual, th - VH)
        assert.ok(switches > 0)
    })

    test(`G1: ${th}px — dragging the thumb maps onto the whole list`, () => {
        const p = new ScrollPager()
        p.setSizes(th, VH)
        const maxPhysical = p.physicalHeight - VH
        assert.equal(p.onScroll(maxPhysical).virtualTop, th - VH)
        assert.equal(p.onScroll(0).virtualTop, 0)
        const mid = p.onScroll(maxPhysical / 2).virtualTop
        // Proportional, within half a page.
        assert.ok(Math.abs(mid - (th - VH) / 2) <= p.physicalHeight / 100, `mid ${mid}`)
        assert.equal(mid - p.offset, maxPhysical / 2)
    })

    test(`G1: ${th}px — scrollTo round-trips and stays in the scroll range`, () => {
        const p = new ScrollPager()
        p.setSizes(th, VH)
        const maxPhysical = p.physicalHeight - VH
        for (let v = 0; v <= th - VH; v += 7_654_321) {
            const physical = p.scrollTo(v)
            assert.ok(physical >= 0 && physical <= maxPhysical, `v ${v} -> ${physical}`)
            assert.equal(physical + p.offset, v)
            // The scroll event this causes is a no-op.
            assert.equal(p.onScroll(physical).virtualTop, v)
        }
        // Past the end is clamped.
        assert.equal(p.scrollTo(th * 2) + p.offset, th - VH)
    })
}

test('G1: resizing the list keeps the virtual position (clamped)', () => {
    const p = new ScrollPager()
    p.setSizes(40_000_000, VH)
    const physical = p.scrollTo(25_000_000)
    assert.equal(physical + p.offset, 25_000_000)
    const after = p.setSizes(41_000_000, VH)
    assert.equal(after + p.offset, 25_000_000)
    // Shrinks below the position: goes to the new end.
    const shrunk = p.setSizes(10_000_000, VH)
    assert.equal(shrunk + p.offset, 10_000_000 - VH)
    // Under the cap: back to identity.
    assert.equal(p.setSizes(3_000_000, VH), 3_000_000 - VH)
    assert.equal(p.offset, 0)
})
