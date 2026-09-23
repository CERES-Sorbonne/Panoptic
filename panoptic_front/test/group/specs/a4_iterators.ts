/**
 * A4 — an iterator for a group that is gone is a dead end, not a crash.
 *
 * Recycled virtual-scroller lines hold ids that outlive the group they pointed at. The iterator
 * constructor has to resolve to an invalid handle rather than throw, traversal from it has to
 * return undefined, and the navigator's iterator methods have to no-op on it.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { GroupIterator, ImageIterator } from '@/core/group/GroupIterator'
import { GroupNavigator } from '@/core/group/GroupNavigator'
import { handTree } from '../harness/world'
import { selectedSlots } from '../harness/stubs/columnStore'

const MISSING = 999999

test('A4: an iterator for a missing id is truthy but isValid === false', () => {
    const { m } = handTree()
    const it = m.result.getGroupIterator(MISSING)
    assert.ok(it, 'the constructor returns a handle rather than throwing')
    assert.equal(it.isValid, false)
    assert.equal(it.group, undefined)
})

test('A4: an ImageIterator for a missing id is truthy but isValid === false', () => {
    const { m } = handTree()
    const it = m.result.getImageIterator(MISSING, 0)
    assert.ok(it)
    assert.equal(it.isValid, false)
    assert.equal(it.slots, undefined, 'no slots are assigned to an invalid handle')
    assert.equal(it.slot, undefined)
})

test('A4: nextGroup/prevGroup on an invalid iterator return undefined instead of throwing', () => {
    const { m } = handTree()
    const it = m.result.getGroupIterator(MISSING)
    assert.equal(it.nextGroup(), undefined)
    assert.equal(it.prevGroup(), undefined)
})

test('A4: nextGroup/prevGroup on an invalid ImageIterator return undefined', () => {
    const { m } = handTree()
    const it = m.result.getImageIterator(MISSING, 0)
    assert.equal(it.nextGroup(), undefined)
    assert.equal(it.prevGroup(), undefined)
})

// nextImages/prevImages used to be the only traversal methods without the `if (!this.isValid)
// return undefined` guard nextGroup/prevGroup have: they read positionCount(current.group) with
// `group` undefined and threw `Cannot read properties of undefined (reading 'id')`. Never
// reachable through the app (both call sites check isValid first), but the same
// defensive-contract asymmetry, so the guard is there now.
test('A4: nextImages/prevImages on an invalid ImageIterator return undefined', () => {
    const { m } = handTree()
    const it = m.result.getImageIterator(MISSING, 0)
    assert.equal(it.nextImages(), undefined)
    assert.equal(it.prevImages(), undefined)
})

// ImageIterator.fromGroupIterator dereferenced `it.group.id` before resolving anything, so an
// unresolved source threw instead of reaching its own `if (!imageIt.isValid) return undefined`
// tail — the same dead-end answer it already gives for a group holding no image.
test('A4: fromGroupIterator on an invalid GroupIterator returns undefined', () => {
    const { m } = handTree()
    const bad = m.result.getGroupIterator(MISSING)
    assert.equal(ImageIterator.fromGroupIterator(bad), undefined)
    assert.equal(ImageIterator.fromGroupIterator(undefined as unknown as GroupIterator), undefined)
})

test('A4: fromGroupIterator on a valid group iterator resolves to its first image', () => {
    const { m, a } = handTree()
    const it = ImageIterator.fromGroupIterator(m.result.getGroupIterator(a.id as number))
    assert.ok(it)
    assert.equal(it!.slot, 0)
})

test('A4: a group deleted under a live iterator makes traversal a dead end, not a crash', () => {
    const { m, b } = handTree()
    const it = m.result.getGroupIterator(b.id as number)
    assert.equal(it.isValid, true)
    // The recycled line keeps its id; the tree moved on.
    const stale = m.result.getGroupIterator(b.id as number)
    delete m.result.index[b.id as number]
    const afterDelete = m.result.getGroupIterator(b.id as number)
    assert.equal(afterDelete.isValid, false)
    assert.equal(afterDelete.nextGroup(), undefined)
    assert.equal(stale.isValid, true, 'a handle taken before the delete keeps its captured node')
})

test('A4: the navigator\'s iterator methods no-op on an invalid iterator', () => {
    const { m } = handTree()
    const nav = new GroupNavigator(m.result)
    const badGroup = m.result.getGroupIterator(MISSING)
    const badImage = m.result.getImageIterator(MISSING, 0)

    nav.selectGroupIterator(badGroup)
    nav.unselectGroupIterator(badGroup)
    nav.toggleGroupIterator(badGroup)
    nav.selectImageIterator(badImage)
    nav.unselectImageIterator(badImage)
    nav.toggleImageIterator(badImage)

    assert.deepEqual(selectedSlots(), [], 'no junk key reached the selection mask')
})

test('A4: the navigator\'s iterator methods no-op on undefined', () => {
    const { m } = handTree()
    const nav = new GroupNavigator(m.result)
    nav.selectGroupIterator(undefined as unknown as GroupIterator)
    nav.toggleGroupIterator(undefined as unknown as GroupIterator)
    nav.selectImageIterator(undefined as unknown as ImageIterator)
    nav.toggleImageIterator(undefined as unknown as ImageIterator)
    assert.deepEqual(selectedSlots(), [])
})

test('A4: findImageIterator returns undefined for a group that no longer holds the image', () => {
    const { m, a } = handTree()
    assert.ok(m.result.findImageIterator(a.id as number, 1000), 'precondition: bucket A holds 1000')
    assert.equal(m.result.findImageIterator(MISSING, 1000), undefined, 'missing group')
    assert.equal(m.result.findImageIterator(a.id as number, 1009), undefined, 'image is elsewhere')
    assert.equal(m.result.findImageIterator(a.id as number, 424242), undefined, 'unknown instance')
})
