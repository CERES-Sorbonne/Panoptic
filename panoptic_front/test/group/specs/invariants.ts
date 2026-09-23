/**
 * The DEV invariants.
 *
 * ClusterOverlay.checkInvariants (I1-I5) only runs under `import.meta.env.DEV`, so the suite is
 * built with DEV pinned on and every test fails on a reported breach (harness/hooks.ts). These
 * tests prove that machinery has teeth: DEV really is on, and a deliberately corrupted container
 * really is caught.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { handTree, pile } from '../harness/world'
import { invariantBreaches, resetConsole } from '../harness/console'

test('invariants: the suite runs with import.meta.env.DEV on', () => {
    assert.equal((import.meta as any).env?.DEV, true,
        'without DEV, checkInvariants never runs and the afterEach hook is vacuous')
})

test('invariants: a corrupted container is caught and reported through console.error', () => {
    const { m, b } = handTree()
    m.clusters.addCustomGroups(b.id, [pile(201, [4, 5])], false)
    const overlay = m.clusters.overlay
    const c = overlay.container(b.id as number)!
    const node = overlay.nodeOf(201)!

    resetConsole()
    // I3: the authored total and the owner array must agree.
    ;(c as any).table[node.idx].owned = 99
    overlay.resync(c)

    const breaches = invariantBreaches()
    assert.equal(breaches.length, 1, 'the DEV check fired')
    assert.match(breaches[0], /\[ClusterOverlay\] I3 broken on bucket 2/)

    // The deliberate breach is the point of this test; clear it so the afterEach hook passes.
    resetConsole()
})

test('invariants: a healthy container reports nothing', () => {
    const { m, b } = handTree()
    m.clusters.addCustomGroups(b.id, [pile(301, [4, 5]), pile(302, [6])], false)
    const c = m.clusters.overlay.container(b.id as number)!
    resetConsole()
    m.clusters.overlay.resync(c)
    assert.deepEqual(invariantBreaches(), [])
})
