/**
 * Cluster overlay — the data layer for the reworked cluster view (see cluster_view_goals.md).
 *
 * A cluster is a manual membership Set over a parent group's slots. The displayed contents are
 * *derived*: one O(|parent|) pass routes each parent slot to its cluster (in parent display order,
 * which is already filtered + sorted), leaving unrouted slots in the leftover "no-cluster" line.
 * The cluster Sets themselves are mutated only by explicit cluster edits — value changes and
 * filtering are handled for free by re-deriving over the current parent slots.
 *
 * Pure and store-agnostic: `derive` takes the parent's slot list; `badgeState` takes a value
 * reader. Nothing here touches Vue or the stores.
 */

// Reserved, predictable id for the leftover "no-cluster" line (derived membership, no stored Set).
export const LEFTOVER_ID = -1

export interface ClusterMember {
    id: number
    name?: string
    slots: Set<number>          // manual membership; mutated only by explicit cluster edits
    isLeftover?: boolean
}

export interface ClusterOverlay {
    parentId: number
    clusters: ClusterMember[]
    slotToCluster: Map<number, number>   // slot → clusterId ; O(1) routing
}

export interface DerivedLine {
    id: number
    name?: string
    isLeftover?: boolean
    slots: number[]             // this line's parent slots, in parent display order
}

/**
 * One pass over the parent's already-filtered, already-sorted slots. Returns a line per cluster
 * (plus a trailing leftover line when non-empty), each with its slots in parent order.
 */
export function derive(parentSlots: ArrayLike<number>, ov: ClusterOverlay): DerivedLine[] {
    const lines: DerivedLine[] = ov.clusters.map(c => ({ id: c.id, name: c.name, isLeftover: c.isLeftover, slots: [] as number[] }))
    const byId = new Map<number, DerivedLine>()
    for (const l of lines) byId.set(l.id, l)

    const leftover: DerivedLine = { id: LEFTOVER_ID, name: 'Unclustered', isLeftover: true, slots: [] }

    for (let i = 0; i < parentSlots.length; i++) {
        const s = parentSlots[i]
        const cid = ov.slotToCluster.get(s)
        const line = cid === undefined ? leftover : (byId.get(cid) ?? leftover)
        line.slots.push(s)
    }

    if (leftover.slots.length) lines.push(leftover)
    return lines
}

// ── Explicit cluster-edit primitives (the only things that mutate the Sets) ────────────────────

export function addMemberSlots(ov: ClusterOverlay, clusterId: number, slots: Iterable<number>): void {
    const c = ov.clusters.find(c => c.id === clusterId)
    if (!c) return
    for (const s of slots) {
        // a slot belongs to exactly one cluster: pull it from its previous owner first
        const prev = ov.slotToCluster.get(s)
        if (prev !== undefined && prev !== clusterId) ov.clusters.find(x => x.id === prev)?.slots.delete(s)
        c.slots.add(s)
        ov.slotToCluster.set(s, clusterId)
    }
}

export function removeMemberSlots(ov: ClusterOverlay, clusterId: number, slots: Iterable<number>): void {
    const c = ov.clusters.find(c => c.id === clusterId)
    if (!c) return
    for (const s of slots) {
        c.slots.delete(s)
        if (ov.slotToCluster.get(s) === clusterId) ov.slotToCluster.delete(s)
    }
}

// ── Badge (homogeneity of a cluster on the current target property) ─────────────────────────────

export type BadgeState =
    | { kind: 'empty' }
    | { kind: 'mixed'; count: number }
    | { kind: 'value'; value: unknown }

/**
 * `read(slot)` returns the raw value of the target property for that slot. For a tag-type (set-valued)
 * target, pass a `canon` that maps the raw value to a canonical comparable form (e.g. sorted-id string),
 * since raw arrays reference-compare. Empty when there are no values; the common value when homogeneous;
 * mixed (with distinct-value count) otherwise.
 */
export function badgeState(
    slots: Iterable<number>,
    read: (slot: number) => unknown,
    canon?: (v: unknown) => unknown,
): BadgeState {
    // Single pass (clusters are viewport-lazy, so bounded by what's on screen).
    const seen = new Set<unknown>()
    let common: unknown
    let hasAny = false
    for (const s of slots) {
        const raw = read(s)
        if (raw === null || raw === undefined || raw === '') continue
        if (!hasAny) { common = raw; hasAny = true }
        seen.add(canon ? canon(raw) : raw)
    }
    if (!hasAny) return { kind: 'empty' }
    if (seen.size > 1) return { kind: 'mixed', count: seen.size }
    return { kind: 'value', value: common }
}
