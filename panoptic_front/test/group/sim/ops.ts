/**
 * The operation catalogue.
 *
 * An operation is split in two: `plan` consumes the RNG and returns a plain, serialisable
 * record; `apply` executes that record against the world and consumes no randomness at all.
 * That split is what makes a run replayable and, more importantly, shrinkable: a plan refers to
 * its targets by position among the current candidates, so dropping an earlier operation still
 * leaves every later one executable.
 */
import { Group, GroupType, GroupSortType } from '@/core/group/types'
import { buildGroup } from '@/core/group/builders'
import { SortDirection } from '@/core/SortManager'
import { DateUnit } from '@/data/models'
import { getTmpId } from '@/utils/utils'
import { columnStub } from '../harness/stubs/columnStore'
import { actionStub, releaseAction, isActionPending } from '../harness/stubs/actionStore'
import { Rng } from './rng'
import { ALL_PROPS, NUMBERS, GroupLevel, P } from './model'
import { World, randomValue, randomArrival, addInstances, ArrivalSpec } from './world'

export interface Plan { op: string, [key: string]: any }

export interface Op {
    name: string
    weight: number
    /** null when the world offers nothing to do — the runner picks another operation. */
    plan(w: World, rng: Rng): Plan | null
    apply(w: World, plan: Plan): void | Promise<void>
}

const MAX_LEVELS = 3
const UNITS = [DateUnit.Day, DateUnit.Month, DateUnit.Year, DateUnit.Hour]

/** Position `i` among `len` candidates, so a plan survives the list changing under it. */
const at = (i: number, len: number) => (len <= 0 ? 0 : ((i % len) + len) % len)

const idOf = (slot: number) => columnStub.instanceIds()[slot]

/** `count` slots of `list`, starting at `off`. */
function take(list: number[], off: number, count: number): number[] {
    if (!list.length) return []
    const start = at(off, list.length)
    return list.slice(start, start + Math.max(1, count))
}

/** Cut `slots` into `pileCount` piles following the recorded per-slot assignment. */
function buildPiles(slots: number[], pileCount: number, parts: number[]): Group[] {
    const groups: Group[] = []
    for (let k = 0; k < pileCount; k++) {
        const g = buildGroup(getTmpId(), [], GroupType.Cluster)
        g.name = 'sim pile ' + k
        groups.push(g)
    }
    slots.forEach((s, i) => {
        const a = parts[i % parts.length]
        if (a >= 0) groups[at(a, pileCount)].slots.push(s)
    })
    return groups
}

function planPiles(rng: Rng): { piles: number, parts: number[] } {
    const piles = rng.between(1, 3)
    const parts: number[] = []
    const n = rng.between(2, 7)
    // -1 leaves the slot unowned, so it routes to the level's leftover.
    for (let i = 0; i < n; i++) parts.push(rng.chance(0.2) ? -1 : rng.int(piles))
    return { piles, parts }
}

/** Live sibling sets of a container: the piles a merge could combine. */
function siblingSets(w: World): { ids: number[] }[] {
    const out: { ids: number[] }[] = []
    for (const c of w.gm.clusters.overlay.byGroup.values()) {
        const byUp = new Map<number, number[]>()
        for (let i = 1; i < c.table.length; i++) {
            const node = c.table[i]
            if (!node || node.dead) continue
            const list = byUp.get(node.up) ?? []
            list.push(node.group.id as number)
            byUp.set(node.up, list)
        }
        for (const ids of byUp.values()) if (ids.length >= 2) out.push({ ids })
    }
    return out
}

export const OPS: Op[] = [

    // ── data ─────────────────────────────────────────────────────────────────
    {
        name: 'setValues', weight: 16,
        plan(w, rng) {
            if (!w.model.instances.length) return null
            const prop = rng.pick(ALL_PROPS)
            const count = rng.between(1, 6)
            const targets: number[] = []
            const vals = []
            for (let i = 0; i < count; i++) {
                targets.push(rng.int(w.model.instances.length))
                vals.push(randomValue(rng, prop))
            }
            return { op: 'setValues', prop, targets, vals }
        },
        apply(w, plan) {
            const list = w.model.instances
            if (!list.length) return
            const ids: number[] = []
            plan.targets.forEach((t: number, i: number) => {
                const inst = list[at(t, list.length)]
                w.write(inst, plan.prop, plan.vals[i])
                ids.push(inst.id)
            })
            w.dirty(ids)
        },
    },
    {
        name: 'addArrivals', weight: 3,
        plan(_w, rng) {
            const specs: ArrivalSpec[] = []
            const n = rng.between(1, 3)
            for (let i = 0; i < n; i++) specs.push(randomArrival(rng))
            return { op: 'addArrivals', specs }
        },
        apply(w, plan) {
            w.dirty(addInstances(w, plan.specs))
        },
    },
    {
        name: 'delInstances', weight: 2,
        plan(w, rng) {
            if (!w.model.instances.length) return null
            const targets: number[] = []
            const n = rng.between(1, 3)
            for (let i = 0; i < n; i++) targets.push(rng.int(w.model.instances.length))
            return { op: 'delInstances', targets }
        },
        apply(w, plan) {
            const list = w.model.instances
            if (!list.length) return
            const ids: number[] = []
            for (const t of plan.targets) {
                const inst = list[at(t, list.length)]
                inst.deleted = true
                ids.push(inst.id)
            }
            w.dirty(ids)
        },
    },

    // ── grouping configuration ───────────────────────────────────────────────
    {
        name: 'groupAdd', weight: 4,
        plan(w, rng) {
            if (w.model.groupBy.length >= MAX_LEVELS) return null
            return {
                op: 'groupAdd', pick: rng.int(ALL_PROPS.length), pos: rng.int(MAX_LEVELS + 1),
                stepSize: rng.between(1, 3), stepUnit: rng.pick(UNITS),
            }
        },
        async apply(w, plan) {
            const used = new Set(w.model.groupBy.map(l => l.propId))
            const free = ALL_PROPS.filter(id => !used.has(id))
            if (!free.length || w.model.groupBy.length >= MAX_LEVELS) return
            const level: GroupLevel = { propId: free[at(plan.pick, free.length)], stepSize: plan.stepSize, stepUnit: plan.stepUnit }
            const levels = [...w.model.groupBy]
            levels.splice(at(plan.pos, levels.length + 1), 0, level)
            w.setGroupBy(levels)
            await w.regroup()
        },
    },
    {
        name: 'groupDel', weight: 3,
        plan(w, rng) {
            if (!w.model.groupBy.length) return null
            return { op: 'groupDel', idx: rng.int(w.model.groupBy.length) }
        },
        async apply(w, plan) {
            const levels = [...w.model.groupBy]
            if (!levels.length) return
            levels.splice(at(plan.idx, levels.length), 1)
            w.setGroupBy(levels)
            await w.regroup()
        },
    },
    {
        name: 'groupReorder', weight: 2,
        plan(w, rng) {
            if (w.model.groupBy.length < 2) return null
            return { op: 'groupReorder', shift: rng.between(1, 2) }
        },
        async apply(w, plan) {
            const levels = [...w.model.groupBy]
            if (levels.length < 2) return
            const k = at(plan.shift, levels.length)
            w.setGroupBy(levels.slice(k).concat(levels.slice(0, k)))
            await w.regroup()
        },
    },
    {
        name: 'groupOption', weight: 4,
        plan(w, rng) {
            if (!w.model.groupBy.length) return null
            return {
                op: 'groupOption', idx: rng.int(w.model.groupBy.length),
                kind: rng.pick(['step', 'unit', 'dir', 'type']),
                stepSize: rng.between(1, 4), stepUnit: rng.pick(UNITS),
                dir: rng.chance(0.5) ? SortDirection.Ascending : SortDirection.Descending,
                type: rng.chance(0.5) ? GroupSortType.Property : GroupSortType.Size,
            }
        },
        async apply(w, plan) {
            const levels = w.model.groupBy
            if (!levels.length) return
            const level = levels[at(plan.idx, levels.length)]
            if (plan.kind === 'step' || plan.kind === 'unit') {
                if (plan.kind === 'step') level.stepSize = plan.stepSize
                else level.stepUnit = plan.stepUnit
                w.gm.setGroupOption(level.propId, { stepSize: level.stepSize, stepUnit: level.stepUnit })
                await w.regroup()          // buckets change, so the tree is rebuilt
            } else {
                w.gm.setGroupOption(level.propId, plan.kind === 'dir' ? { direction: plan.dir } : { type: plan.type })
                w.gm.sortGroups(true)      // only the child order changes
            }
        },
    },
    {
        name: 'filterChange', weight: 4,
        plan(_w, rng) {
            const pool: (number | null)[] = [...NUMBERS, null]
            const values = pool.filter(() => rng.chance(0.3))
            return { op: 'filterChange', mode: values.length && rng.chance(0.85) ? 'exclude' : 'none', values }
        },
        async apply(w, plan) {
            w.model.filter = { mode: plan.mode, values: plan.values }
            await w.regroup()
        },
    },
    {
        name: 'sortChange', weight: 2,
        plan(_w, rng) { return { op: 'sortChange', mode: rng.int(4) } },
        async apply(w, plan) {
            w.model.sortMode = plan.mode
            await w.regroup()
        },
    },
    {
        name: 'sha1Toggle', weight: 3,
        plan() { return { op: 'sha1Toggle' } },
        apply(w) {
            w.model.sha1Mode = !w.model.sha1Mode
            w.gm.setSha1Mode(w.model.sha1Mode, true)
        },
    },

    // ── clustering ───────────────────────────────────────────────────────────
    {
        name: 'clusterLeaf', weight: 7,
        plan(w, rng) {
            if (!w.groupingLeaves().some(g => g.slots.length >= 2)) return null
            return { op: 'clusterLeaf', leafIdx: rng.int(64), ...planPiles(rng), useAction: rng.chance(0.35) }
        },
        async apply(w, plan) {
            const cands = w.groupingLeaves().filter(g => g.slots.length >= 2)
            if (!cands.length) return
            const target = cands[at(plan.leafIdx, cands.length)]
            const groups = buildPiles(target.slots.slice(), plan.piles, plan.parts)
            const isEmptyBucket = target.meta?.propertyValues?.[0]?.value === undefined
            if (plan.useAction && !isActionPending()) {
                actionStub.next = groups
                await w.gm.cluster(target.id as number, { funcId: 'sim.cluster', inputs: [] })
                actionStub.next = []
            } else if (isEmptyBucket) {
                // The undecided pile: the same grafting, plus the bucket the view routes to.
                w.gm.clusters.clusterEmptyBucket(target.id as number, groups, true)
            } else {
                w.gm.addCustomGroups(target.id as number, groups, true)
            }
        },
    },
    {
        // Start a clustering and leave it in flight: the tree goes on changing until the answer
        // comes back, which is the one race the cluster layer has to survive.
        name: 'clusterStartAsync', weight: 3,
        plan(w, rng) {
            if (w.pendingCluster || isActionPending()) return null
            if (!w.groupingLeaves().some(g => g.slots.length >= 2)) return null
            return { op: 'clusterStartAsync', leafIdx: rng.int(64), ...planPiles(rng) }
        },
        apply(w, plan) {
            if (w.pendingCluster || isActionPending()) return
            const cands = w.groupingLeaves().filter(g => g.slots.length >= 2)
            if (!cands.length) return
            const target = cands[at(plan.leafIdx, cands.length)]
            const groups = buildPiles(target.slots.slice(), plan.piles, plan.parts)
            actionStub.defer = true
            const promise = w.gm.cluster(target.id as number, { funcId: 'sim.async', inputs: [] })
            actionStub.defer = false
            w.pendingCluster = { promise, groups }
        },
    },
    {
        name: 'clusterFinishAsync', weight: 4,
        plan(w, rng) {
            if (!w.pendingCluster) return null
            return { op: 'clusterFinishAsync', empty: rng.chance(0.2) }
        },
        async apply(w, plan) {
            const pending = w.pendingCluster
            if (!pending) return
            w.pendingCluster = null
            releaseAction(plan.empty ? [] : pending.groups)
            await pending.promise
        },
    },
    {
        name: 'subCluster', weight: 4,
        plan(w, rng) {
            if (!w.attachedPiles().some(n => n.node.group.children.length === 0 && n.node.group.slots.length >= 2)) return null
            return { op: 'subCluster', pileIdx: rng.int(64), ...planPiles(rng) }
        },
        apply(w, plan) {
            const cands = w.attachedPiles().filter(n => n.node.group.children.length === 0 && n.node.group.slots.length >= 2)
            if (!cands.length) return
            const target = cands[at(plan.pileIdx, cands.length)].node.group
            w.gm.addCustomGroups(target.id as number, buildPiles(target.slots.slice(), plan.piles, plan.parts), true)
        },
    },
    {
        name: 'delCustom', weight: 3,
        plan(w, rng) {
            if (!w.gm.clusters.overlay.byGroup.size) return null
            return { op: 'delCustom', idx: rng.int(64) }
        },
        apply(w, plan) {
            const ids: number[] = [...w.gm.clusters.overlay.byGroup.keys()]
            for (const n of w.attachedPiles()) ids.push(n.node.group.id as number)
            if (!ids.length) return
            w.gm.delCustomGroups(ids[at(plan.idx, ids.length)], true)
        },
    },
    {
        name: 'mergePiles', weight: 3,
        plan(w, rng) {
            if (!siblingSets(w).length) return null
            return { op: 'mergePiles', setIdx: rng.int(32), a: rng.int(32), b: rng.int(32) }
        },
        apply(w, plan) {
            const sets = siblingSets(w)
            if (!sets.length) return
            const ids = sets[at(plan.setIdx, sets.length)].ids
            const a = at(plan.a, ids.length)
            let b = at(plan.b, ids.length)
            if (b === a) b = (a + 1) % ids.length
            w.gm.merge([ids[a], ids[b]], true)
        },
    },
    {
        name: 'deletePile', weight: 3,
        plan(w, rng) {
            if (!w.liveNodes().some(n => !n.node.leftover)) return null
            return { op: 'deletePile', idx: rng.int(32) }
        },
        apply(w, plan) {
            const cands = w.liveNodes().filter(n => !n.node.leftover)
            if (!cands.length) return
            w.gm.deletePile(cands[at(plan.idx, cands.length)].node.group.id as number, true)
        },
    },
    {
        name: 'moveImages', weight: 4,
        plan(w, rng) {
            if (!w.leaves().some(g => g.slots.length)) return null
            return { op: 'moveImages', fromIdx: rng.int(32), toIdx: rng.int(32), off: rng.int(16), count: rng.between(1, 3) }
        },
        apply(w, plan) {
            const piles = w.attachedPiles().map(n => n.node.group).filter(g => g.slots.length)
            const sources = piles.length ? piles : w.leaves().filter(g => g.slots.length)
            if (!sources.length) return
            const from = sources[at(plan.fromIdx, sources.length)]
            const targets = w.dfsGroups().filter(g => g.id !== from.id)
            if (!targets.length) return
            const to = targets[at(plan.toIdx, targets.length)]
            const ids = take(from.slots, plan.off, plan.count).map(idOf)
            w.gm.moveImagesToGroup(from.id as number, to.id as number, ids, true)
        },
    },
    {
        // Queue-drain, in the order the view does it: the images are given the value the bucket
        // is the absence of, and only then released from their pile. Draining without the value
        // write is a no-op — the resync finds them still in the bucket and hands them straight
        // back — so the write is what makes this operation mean anything.
        name: 'drain', weight: 4,
        plan(w, rng) {
            if (!w.attachedPiles().some(n => n.node.group.slots.length)) return null
            const vals: { [propId: number]: any } = {}
            for (const propId of ALL_PROPS) vals[propId] = randomValue(rng, propId)
            return { op: 'drain', idx: rng.int(32), off: rng.int(16), count: rng.between(1, 3), vals }
        },
        apply(w, plan) {
            const cands = w.attachedPiles().filter(n => n.node.group.slots.length)
            if (!cands.length) return
            const g = cands[at(plan.idx, cands.length)].node.group
            const ids = take(g.slots, plan.off, plan.count).map(idOf)
            const level = w.model.groupBy[w.model.groupBy.length - 1]
            if (level) {
                for (const id of ids) {
                    const inst = w.model.byId(id)
                    if (inst) w.write(inst, level.propId, plan.vals[level.propId])
                }
                w.dirty(ids)
            }
            w.gm.clusters.drain(g.id as number, ids, true)
        },
    },
    {
        name: 'clearCustom', weight: 1,
        plan(w) { return w.gm.clusters.overlay.byGroup.size ? { op: 'clearCustom' } : null },
        apply(w) { w.gm.clearCustomGroups(true) },
    },

    // ── view state ───────────────────────────────────────────────────────────
    {
        name: 'toggleOpen', weight: 5,
        plan(_w, rng) { return { op: 'toggleOpen', idx: rng.int(64) } },
        apply(w, plan) {
            // The root is never a card, so it is never opened or closed.
            const groups = w.dfsGroups().filter(g => g.id !== 0)
            if (!groups.length) return
            w.gm.toggleGroup(groups[at(plan.idx, groups.length)].id as number, true)
        },
    },
    {
        name: 'selectGroup', weight: 3,
        plan(_w, rng) { return { op: 'selectGroup', idx: rng.int(64), shift: rng.chance(0.4) } },
        apply(w, plan) {
            const groups = w.dfsGroups()
            if (!groups.length) return
            const g = groups[at(plan.idx, groups.length)]
            w.gm.toggleGroupIterator(w.gm.getGroupIterator(g.id as number), plan.shift)
        },
    },
    {
        name: 'selectImage', weight: 5,
        plan(_w, rng) { return { op: 'selectImage', leafIdx: rng.int(64), imgIdx: rng.int(32), shift: rng.chance(0.45) } },
        apply(w, plan) {
            const leaves = w.leaves().filter(g => g.slots.length)
            if (!leaves.length) return
            const leaf = leaves[at(plan.leafIdx, leaves.length)]
            const pile = w.gm.result.pileIndex.get(leaf.id as number)
            const count = pile ? pile.bounds.length - 1 : leaf.slots.length
            if (count <= 0) return
            const it = w.gm.getImageIterator(leaf.id as number, at(plan.imgIdx, count))
            w.gm.toggleImageIterator(it, plan.shift)
        },
    },
    {
        name: 'clearSelection', weight: 1,
        plan(_w, rng) { return { op: 'clearSelection', all: rng.chance(0.4) } },
        apply(w, plan) {
            if (plan.all) w.gm.toggleAll()
            else w.gm.clearSelection()
        },
    },

    // ── recompute ────────────────────────────────────────────────────────────
    {
        name: 'fullUpdate', weight: 3,
        plan() { return { op: 'fullUpdate' } },
        async apply(w) { await w.update() },
    },
    {
        name: 'regroup', weight: 3,
        plan() { return { op: 'regroup' } },
        async apply(w) { await w.regroup() },
    },
]

export const OP_BY_NAME = new Map(OPS.map(op => [op.name, op]))

const TOTAL_WEIGHT = OPS.reduce((sum, op) => sum + op.weight, 0)

/** Weighted pick. */
export function pickOp(rng: Rng): Op {
    let r = rng.next() * TOTAL_WEIGHT
    for (const op of OPS) { r -= op.weight; if (r <= 0) return op }
    return OPS[OPS.length - 1]
}

/** One line per operation, short enough to paste into a report. */
export function describe(plan: Plan): string {
    const { op, ...rest } = plan
    const body = JSON.stringify(rest, (_k, v) => (Array.isArray(v) && v.length > 12 ? v.slice(0, 12).concat(['…'] as any) : v))
    return `${op} ${body === '{}' ? '' : body}`
}

export { P }
