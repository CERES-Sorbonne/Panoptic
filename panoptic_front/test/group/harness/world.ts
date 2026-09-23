/**
 * Shared fixtures for the grouping regression suite.
 *
 * Everything here drives the REAL GroupManager / ClusterManager / ClusterOverlay; only the
 * pinia stores underneath are stubbed (see stubs/). The predicates at the bottom are the tree
 * invariants several of the regressions are about, expressed once.
 */
import { GroupManager } from '@/core/GroupManager'
import { GroupType, Group } from '@/core/group/types'
import { buildGroup, buildRoot } from '@/core/group/builders'
import { PropertyType } from '@/data/models'
import { columnStub, setSlots, setColumn, setSha1s } from './stubs/columnStore'
import { resetData, setProperty } from './stubs/dataStore'
import { resetAction } from './stubs/actionStore'
import { resetConsole, invariantBreaches } from './console'

/** The number property every grouped fixture buckets by. */
export const PROP = 1

/** Put the stores back to a known state. Called by every test. */
export function reset() {
    resetData()
    resetAction()
    resetConsole()
}

/** A manager over `n` slots, grouped by a number property whose column is `values`. */
export async function groupedBy(values: number[], present?: number[]): Promise<GroupManager> {
    reset()
    setSlots(values.length)
    setProperty(PROP, PropertyType.number)
    setColumn(PROP, values)
    const m = new GroupManager()
    m.setGroupOption(PROP)
    await m.group(new Int32Array(present ?? values.map((_, i) => i)))
    return m
}

/** A manager over `n` slots with no grouping at all. */
export async function ungrouped(n: number, present?: number[]): Promise<GroupManager> {
    reset()
    setSlots(n)
    const m = new GroupManager()
    await m.group(new Int32Array(present ?? Array.from({ length: n }, (_, i) => i)))
    return m
}

/**
 * A hand-built property tree — root over 12 slots, split into three 4-slot buckets A/B/C —
 * for the structural tests that are about the cluster layer rather than about bucketing.
 * `sha1s` seeds the slot table so sha1Mode has duplicates to pile.
 */
export function handTree(sha1s: (string | null)[] = DEFAULT_SHA1S) {
    reset()
    setSha1s(sha1s)
    const m = new GroupManager()
    const root = buildRoot([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
    m.result.root = root
    m.regsiterGroup(root)
    const a = buildGroup(1, [0, 1, 2, 3], GroupType.Property)
    const b = buildGroup(2, [4, 5, 6, 7], GroupType.Property)
    const c = buildGroup(3, [8, 9, 10, 11], GroupType.Property)
    m.setChildGroup(root, [a, b, c])
    return { m, root, a, b, c }
}

export const DEFAULT_SHA1S = ['a', 'a', 'b', 'c', 'c', 'c', 'd', 'e', 'e', 'f', 'f', 'g']

/** A cluster pile with a fixed id, as the cluster ops take them. */
export const pile = (id: number, slots: number[]) => buildGroup(id, slots, GroupType.Cluster)

export const slotsOf = (m: GroupManager, id: number) => (m.result.index[id]?.slots ?? []).slice()

/** The property leaf whose bucket value is `value`, or undefined. */
export function leafFor(m: GroupManager, value: number): Group | undefined {
    return (Object.values(m.result.index) as Group[])
        .find(g => g.meta?.propertyValues?.[0]?.value === value)
}

/** The "no value" property leaf: the bucket minted for an unset slot. */
export function emptyLeaf(m: GroupManager): Group | undefined {
    return (Object.values(m.result.index) as Group[]).find(g =>
        g.type === GroupType.Property && g.meta?.propertyValues?.[0]?.value === undefined)
}

export const countOf = (arr: number[], s: number) => arr.filter(x => x === s).length

/** Every leaf of the tree, in DFS order. */
export function leaves(m: GroupManager): Group[] {
    const out: Group[] = []
    const walk = (g: Group) => { if (!g?.children.length) { if (g) out.push(g) } else g.children.forEach(walk) }
    walk(m.result.root)
    return out
}

// ── invariants ───────────────────────────────────────────────────────────────

/**
 * The ONE meaning of imageToGroups: instanceId -> the set of tree LEAVES currently displaying
 * it. Returns the ways the current tree breaks it (empty = intact).
 */
export function i2gProblems(m: GroupManager): string[] {
    const ids = columnStub.instanceIds()
    const i2g = m.result.imageToGroups
    const expected = new Map<number, Set<number>>()
    for (const g of leaves(m)) {
        for (const s of g.slots) {
            const id = ids[s]
            let set = expected.get(id)
            if (!set) { set = new Set<number>(); expected.set(id, set) }
            set.add(g.id)
        }
    }
    const problems: string[] = []
    for (const [id, set] of i2g) {
        if (set.size === 0) problems.push(`${id} has an EMPTY membership set left behind`)
        for (const gid of set) {
            const g = m.result.index[gid]
            if (!g) { problems.push(`${id} names group ${gid}, which is not in the index`); continue }
            if (g.children.length) problems.push(`${id} names ${gid}, not a leaf (${g.children.length} children)`)
            else if (!expected.get(id)?.has(gid)) problems.push(`${id} names leaf ${gid}, which does not hold it`)
        }
    }
    for (const [id, set] of expected) {
        const actual = i2g.get(id)
        for (const gid of set) if (!actual?.has(gid)) problems.push(`leaf ${gid} holds ${id}, absent from imageToGroups`)
    }
    return problems
}

/** Every slot the root holds is displayed by exactly one leaf, and no leaf shows a foreign one. */
export function coverageProblems(m: GroupManager): string[] {
    const leafSlots = new Map<number, number>()
    for (const g of leaves(m)) for (const s of g.slots) leafSlots.set(s, (leafSlots.get(s) ?? 0) + 1)
    const problems: string[] = []
    for (const s of m.result.root.slots) if (!leafSlots.has(s)) problems.push(`root slot ${s} is in no leaf`)
    for (const s of leafSlots.keys()) if (!m.result.root.slots.includes(s)) problems.push(`leaf slot ${s} is not in root`)
    return problems
}

/** Display order as slotOrder.slotPosition defines it, from the slots the last group() ordered. */
export function displayOrdered(arr: number[], present: number[]): { ok: boolean, got: number[], want: number[] } {
    const pos = new Map<number, number>()
    present.forEach((s, i) => pos.set(s, i))
    const p = (s: number) => pos.has(s) ? pos.get(s)! : present.length + s
    const want = arr.slice().sort((a, b) => p(a) - p(b))
    return { ok: arr.join() === want.join(), got: arr.slice(), want }
}

/** Assert no ClusterOverlay invariant (I1-I5) was reported since the last reset. */
export function noInvariantBreach(): string[] { return invariantBreaches() }
