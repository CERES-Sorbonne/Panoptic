/**
 * The simulated world: the reference Model beside a REAL GroupManager over the headless stores.
 *
 * Nothing under test is reimplemented here. The world only does what CollectionManager does
 * between a state change and the group engine — recompute the present set, hand a full
 * `group()` the sorted slots, or split a data change into the updated / removed pair
 * `updateSelection` takes — minus the debounce, so a step is one synchronous, reproducible
 * transition.
 */
import { GroupManager } from '@/core/GroupManager'
import { Group, GroupType, GroupSortType } from '@/core/group/types'
import { ClusterContainer, ClusterNode } from '@/core/group/ClusterOverlay'
import { DateUnit, PropertyType } from '@/data/models'
import { SortDirection } from '@/core/SortManager'
import {
    columnStub, setSha1s, addSlots, writeValue, selectedSlots,
} from '../harness/stubs/columnStore'
import { resetData, setProperty, setTagProperty } from '../harness/stubs/dataStore'
import { resetAction } from '../harness/stubs/actionStore'
import { resetConsole } from '../harness/console'
import { Rng } from './rng'
import {
    Model, SimInstance, EncVal, GroupLevel, decode,
    P, ALL_PROPS, PROP_TYPE, TAG_PARENTS, TAG_IDS, STRINGS, NUMBERS, DATES, SHA1S,
} from './model'

export class World {
    model = new Model()
    gm: GroupManager
    /** The slots the last full group() was handed — the display order everything is ordered by. */
    lastPresent: number[] = []
    /**
     * A clustering run that has been started and not yet answered. The tree keeps changing
     * while it is in flight, which is the race the async ops are here for.
     */
    pendingCluster: { promise: Promise<void>, groups: Group[] } | null = null

    constructor(gm: GroupManager) { this.gm = gm }

    // ── data ─────────────────────────────────────────────────────────────────

    write(inst: SimInstance, propId: number, value: EncVal) {
        inst.values[propId] = value
        writeValue(propId, inst.slot, decode(propId, value))
    }

    /**
     * A data change, as CollectionManager.setDirty delivers it: the dirty instances that pass
     * the filter are "updated" (which is also how an arrival gets in), the rest are "removed".
     */
    dirty(ids: number[]) {
        const updated = new Set<number>()
        const removed = new Set<number>()
        for (const id of ids) {
            const inst = this.model.byId(id)
            if (!inst) continue
            if (!inst.deleted && this.model.passesFilter(inst)) updated.add(id)
            else removed.add(id)
        }
        this.gm.updateSelection(updated, removed)
    }

    /** A full filter → sort → group pass. */
    async regroup() {
        const slots = this.model.sortedSlots()
        this.lastPresent = slots.slice()
        await this.gm.group(new Int32Array(slots), true)
    }

    /** GroupManager.update(): re-group from root.slots, whatever they currently are. */
    async update() {
        this.lastPresent = this.gm.result.root ? this.gm.result.root.slots.slice() : []
        await this.gm.update(true)
    }

    // ── grouping configuration ───────────────────────────────────────────────

    /** Put both the model and the manager on `levels` (order included). */
    setGroupBy(levels: GroupLevel[]) {
        for (const propId of [...this.gm.state.groupBy]) this.gm.delGroupOption(propId)
        this.model.groupBy = levels.map(l => ({ ...l }))
        for (const level of levels) {
            this.gm.setGroupOption(level.propId, {
                direction: SortDirection.Ascending,
                type: GroupSortType.Property,
                stepSize: level.stepSize,
                stepUnit: level.stepUnit,
            })
        }
    }

    /** Display position of a slot, exactly as slotOrder.slotPosition defines it. */
    position(slot: number): number {
        const i = this.lastPresent.indexOf(slot)
        return i >= 0 ? i : this.lastPresent.length + slot
    }

    // ── candidate enumeration (deterministic order, so a plan replays) ────────

    /** Every group reachable from the root, in DFS order. */
    dfsGroups(): Group[] {
        const out: Group[] = []
        const seen = new Set<Group>()
        const walk = (g: Group) => {
            if (!g || seen.has(g)) return
            seen.add(g)
            out.push(g)
            g.children.forEach(walk)
        }
        walk(this.gm.result.root)
        return out
    }

    /** Leaves of the displayed tree, in DFS order. */
    leaves(): Group[] {
        return this.dfsGroups().filter(g => g.children.length === 0)
    }

    /** Leaves that are NOT cluster piles: the grouping buckets a clustering can divide. */
    groupingLeaves(): Group[] {
        return this.leaves().filter(g => g.type !== GroupType.Cluster)
    }

    /** Every live node of every container, with its container and index. */
    liveNodes(): { c: ClusterContainer, idx: number, node: ClusterNode }[] {
        const out: { c: ClusterContainer, idx: number, node: ClusterNode }[] = []
        for (const c of this.gm.clusters.overlay.byGroup.values()) {
            for (let i = 1; i < c.table.length; i++) {
                const node = c.table[i]
                if (node && !node.dead) out.push({ c, idx: i, node })
            }
        }
        return out
    }

    /** Live piles currently attached to the tree — the cards a user could act on. */
    attachedPiles(): { c: ClusterContainer, idx: number, node: ClusterNode }[] {
        return this.liveNodes().filter(n => this.gm.result.index[n.node.group.id] === n.node.group)
    }

    selectedSlots(): number[] { return selectedSlots(this.gm.selectionNamespace) }
}

// ── construction ─────────────────────────────────────────────────────────────

/** A random encoded value for a property, unset about one time in five. */
export function randomValue(rng: Rng, propId: number): EncVal {
    if (rng.chance(0.18)) return { k: 'u' }
    switch (PROP_TYPE[propId]) {
        case PropertyType.number: return { k: 'n', v: rng.pick(NUMBERS) }
        case PropertyType.string: return { k: 's', v: rng.pick(STRINGS) }
        case PropertyType.date: return { k: 'd', v: rng.pick(DATES) }
        case PropertyType.checkbox: return { k: 'b', v: rng.chance(0.5) }
        case PropertyType.tag: {
            // A "tag" property still stores a list; the UI just keeps it to one entry.
            return { k: 't', v: rng.chance(0.15) ? [] : [rng.pick(TAG_IDS[propId])] }
        }
        case PropertyType.multi_tags: {
            const ids = TAG_IDS[propId]
            const picked = ids.filter(() => rng.chance(0.3))
            return { k: 't', v: picked }
        }
        default: return { k: 'u' }
    }
}

/** Declare the six properties on the data stub. */
function declareProperties() {
    resetData()
    for (const propId of ALL_PROPS) {
        const type = PROP_TYPE[propId]
        if (type === PropertyType.tag || type === PropertyType.multi_tags) {
            setTagProperty(propId, type, TAG_PARENTS[propId])
        } else {
            setProperty(propId, type)
        }
    }
}

export interface WorldOptions {
    instances: number
}

/** A fresh world: stores reset, `n` instances with random values, nothing grouped yet. */
export async function createWorld(rng: Rng, opts: WorldOptions): Promise<World> {
    resetAction()
    resetConsole()
    const n = opts.instances
    const sha1s: string[] = []
    for (let i = 0; i < n; i++) sha1s.push(rng.pick(SHA1S))
    setSha1s(sha1s)
    declareProperties()

    const world = new World(new GroupManager())
    for (let slot = 0; slot < n; slot++) {
        const inst: SimInstance = {
            id: columnStub.instanceIds()[slot],
            slot,
            sha1: sha1s[slot],
            deleted: false,
            values: {},
        }
        world.model.instances.push(inst)
        for (const propId of ALL_PROPS) world.write(inst, propId, randomValue(rng, propId))
    }

    // Start grouped one level deep more often than not — an ungrouped start would spend the
    // first steps on the root-only tree.
    if (rng.chance(0.75)) {
        world.setGroupBy([{ propId: rng.pick(ALL_PROPS), stepSize: 1, stepUnit: DateUnit.Day }])
    }
    await world.regroup()
    return world
}

/** One new instance as an op plan describes it — no randomness left at apply time. */
export interface ArrivalSpec {
    sha1: string
    values: { [propId: number]: EncVal }
}

export function randomArrival(rng: Rng): ArrivalSpec {
    const values: { [propId: number]: EncVal } = {}
    for (const propId of ALL_PROPS) values[propId] = randomValue(rng, propId)
    return { sha1: rng.pick(SHA1S), values }
}

/** Append the described instances to the store and the model, and return their ids. */
export function addInstances(world: World, specs: ArrivalSpec[]): number[] {
    const slots = addSlots(specs.length, specs.map(s => s.sha1))
    const ids: number[] = []
    for (let i = 0; i < slots.length; i++) {
        const inst: SimInstance = {
            id: columnStub.instanceIds()[slots[i]],
            slot: slots[i],
            sha1: specs[i].sha1,
            deleted: false,
            values: {},
        }
        world.model.instances.push(inst)
        for (const propId of ALL_PROPS) world.write(inst, propId, specs[i].values[propId] ?? { k: 'u' })
        ids.push(inst.id)
    }
    return ids
}

export { P, DateUnit }
