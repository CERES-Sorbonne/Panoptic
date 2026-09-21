/**
 * A3 — group selection reads the union of a card's leaves.
 *
 * A sub-clustered pile carries no slots of its own — its images live in its children — so the
 * old predicates, which read group.slots directly, said "not selected" for a card showing
 * images and "selected" for an empty one, and the checkbox click became a no-op.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { groupSlots } from '@/core/group/groupSlots'
import { GroupNavigator } from '@/core/group/GroupNavigator'
import { GroupType, Group } from '@/core/group/types'
import { handTree, pile, slotsOf } from '../harness/world'
import { selectedSlots } from '../harness/stubs/columnStore'

const node = (id: any, slots: number[], children: Group[] = []): Group => {
    const g = { id, key: [], slots, type: GroupType.Cluster, children, depth: 0, order: 0, start: 0, end: 0, view: { closed: false }, meta: {} } as unknown as Group
    children.forEach((c, i) => { c.parent = g; c.parentIdx = i })
    return g
}

test('A3 groupSlots: a leaf hands back its own array, allocation-free', () => {
    const leaf = node('leaf', [1, 2, 3])
    assert.deepEqual(groupSlots(leaf), [1, 2, 3])
    assert.equal(groupSlots(leaf), leaf.slots)
})

test('A3 groupSlots: a sub-clustered parent unions its leaves, deduped, in DFS order', () => {
    const a = node('a', [10, 11])
    const b = node('b', [11, 12])
    assert.deepEqual(groupSlots(node('sub', [], [a, b])), [10, 11, 12])
})

test('A3 groupSlots: empty and nested-empty cases', () => {
    assert.deepEqual(groupSlots(node('empty', [])), [])
    const deep = node('deep', [], [node('mid', [], [node('leaf', [7, 8])]), node('empty', [])])
    assert.deepEqual(groupSlots(deep), [7, 8])
})

// ── the selection surface, on a real navigator over a real sub-clustered tree ──

function subClusteredTree() {
    const { m, b } = handTree()
    // bucket B [4,5,6,7] -> pile 101 [4,5,6] + leftover, then 101 is split into two sub-piles.
    m.clusters.addCustomGroups(b.id, [pile(101, [4, 5, 6])], false)
    m.clusters.split(101, [pile(111, [4, 5]), pile(112, [6])], false)
    const parent = m.result.index[101]
    assert.ok(parent.children.length > 0, 'precondition: pile 101 is sub-clustered')
    assert.deepEqual(parent.slots, [], 'precondition: a sub-clustered pile holds no slots itself')
    return { m, nav: new GroupNavigator(m.result), parent }
}

test('A3: selecting a sub-clustered pile selects all of its descendants', () => {
    const { nav, parent } = subClusteredTree()
    assert.equal(nav.isGroupSelected(parent), false, 'nothing selected yet')
    nav.selectGroup(parent)
    assert.deepEqual(selectedSlots(), [4, 5, 6])
    assert.equal(nav.isGroupSelected(parent), true, 'the checkbox now reads checked')
})

test('A3: a partially selected sub-clustered pile is not selected', () => {
    const { nav, parent } = subClusteredTree()
    nav.selectImages([1004, 1005])
    assert.equal(nav.isGroupSelected(parent), false)
    nav.selectImages([1006])
    assert.equal(nav.isGroupSelected(parent), true)
})

test('A3: toggling a sub-clustered pile round-trips', () => {
    const { m, nav, parent } = subClusteredTree()
    const it = () => m.result.getGroupIterator(parent.id as number)
    nav.toggleGroupIterator(it())
    assert.deepEqual(selectedSlots(), [4, 5, 6], 'first click selects every descendant slot')
    assert.equal(nav.isGroupSelected(parent), true)
    nav.toggleGroupIterator(it())
    assert.deepEqual(selectedSlots(), [], 'second click clears them')
    assert.equal(nav.isGroupSelected(parent), false)
})

test('A3: a genuinely empty group is never "selected", and toggling it does nothing', () => {
    const { m } = handTree()
    const nav = new GroupNavigator(m.result)
    const empty = node('empty', [])
    assert.equal(nav.isGroupSelected(empty), false)
    nav.selectImages([1000, 1001, 1002])
    assert.equal(nav.isGroupSelected(empty), false, 'still not selected with a non-empty mask')
    nav.clearSelection()
    nav.selectGroup(empty)
    assert.deepEqual(selectedSlots(), [], 'toggling an empty group changes nothing')
})

test('A3: a plain leaf still toggles', () => {
    const { m, a } = handTree()
    const nav = new GroupNavigator(m.result)
    const iterator = () => m.result.getGroupIterator(a.id as number)
    nav.toggleGroupIterator(iterator())
    assert.deepEqual(selectedSlots(), slotsOf(m, a.id as number))
    nav.toggleGroupIterator(iterator())
    assert.deepEqual(selectedSlots(), [])
})
