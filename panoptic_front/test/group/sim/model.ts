/**
 * The reference model.
 *
 * A plain-JS picture of the same collection the GroupManager holds: one record per instance
 * plus the filter / sort / grouping configuration. From it the simulation derives, WITHOUT
 * looking at the implementation, which instances are in the collection and which bucket keys
 * each of them belongs to. Everything here is written for obviousness, not for speed — it is
 * the oracle, so a clever version of it would only move the bug.
 *
 * Cluster membership is deliberately NOT modelled: it is authored, not derivable. The
 * simulation checks the overlay's structural rules instead (see check.ts).
 */
import { DateUnit, PropertyType } from '@/data/models'

// ── properties ───────────────────────────────────────────────────────────────

export const P = {
    num: 1,
    str: 2,
    date: 3,
    check: 4,
    tag: 5,
    mtag: 6,
} as const

export const PROP_TYPE: { [id: number]: PropertyType } = {
    [P.num]: PropertyType.number,
    [P.str]: PropertyType.string,
    [P.date]: PropertyType.date,
    [P.check]: PropertyType.checkbox,
    [P.tag]: PropertyType.tag,
    [P.mtag]: PropertyType.multi_tags,
}

export const ALL_PROPS = [P.num, P.str, P.date, P.check, P.tag, P.mtag]

/**
 * Tag hierarchies, as `allParents` (every ancestor, which is what the engine reads).
 * Depth two on purpose: a child tag puts its instance in its own bucket AND in its parent's,
 * which is the multi-leaf membership the whole membership invariant is about.
 */
export const TAG_PARENTS: { [propId: number]: { [tagId: number]: number[] } } = {
    [P.tag]: { 10: [], 11: [], 12: [10], 13: [10], 14: [11] },
    [P.mtag]: { 20: [], 21: [], 22: [20], 23: [21], 24: [] },
}

export const TAG_IDS: { [propId: number]: number[] } = {
    [P.tag]: [10, 11, 12, 13, 14],
    [P.mtag]: [20, 21, 22, 23, 24],
}

export const STRINGS = ['alpha', 'beta', 'gamma', '']
export const NUMBERS = [0, 1, 2, 3, 7]
// Two months, two days apart, so Day / Month / Year bucketing all produce more than one bucket.
export const DATES = [
    Date.UTC(2021, 0, 1), Date.UTC(2021, 0, 2), Date.UTC(2021, 1, 15),
    Date.UTC(2022, 5, 30), Date.UTC(2022, 5, 30, 13, 45),
]

export const SHA1S = ['s0', 's1', 's2', 's3', 's4']

// ── encoded values (serialisable, so an op log can be replayed) ──────────────

export type EncVal =
    | { k: 'u' }
    | { k: 'n', v: number }
    | { k: 's', v: string }
    | { k: 'd', v: number }
    | { k: 'b', v: boolean }
    | { k: 't', v: number[] }

/** The raw value the column buffer holds for an encoded value. */
export function decode(propId: number, e: EncVal): any {
    if (e.k === 'u') {
        // One "unset" spelling per column kind, matching what the real store stores.
        switch (PROP_TYPE[propId]) {
            case PropertyType.number: return NaN
            default: return null
        }
    }
    if (e.k === 'd') return new Date(e.v)
    if (e.k === 't') return e.v.slice()
    return (e as any).v
}

// ── instances ────────────────────────────────────────────────────────────────

export interface SimInstance {
    id: number
    slot: number
    sha1: string
    deleted: boolean
    values: { [propId: number]: EncVal }
}

export interface GroupLevel {
    propId: number
    stepSize: number
    stepUnit: DateUnit
}

export interface Filter {
    /** 'none' keeps everything; 'exclude' drops the instances whose number key is listed. */
    mode: 'none' | 'exclude'
    /** Encoded number keys; `null` stands for the unset bucket. */
    values: (number | null)[]
}

export class Model {
    instances: SimInstance[] = []
    groupBy: GroupLevel[] = []
    filter: Filter = { mode: 'none', values: [] }
    sortMode = 0
    sha1Mode = false

    byId(id: number): SimInstance | undefined {
        return this.instances.find(i => i.id === id)
    }

    /** Does this instance pass the current filter (deletion aside)? */
    passesFilter(inst: SimInstance): boolean {
        if (this.filter.mode === 'none') return true
        const e = inst.values[P.num]
        const key = !e || e.k === 'u' ? null : (e as any).v as number
        return !this.filter.values.includes(key)
    }

    /** The instances the collection currently holds. */
    present(): SimInstance[] {
        return this.instances.filter(i => !i.deleted && this.passesFilter(i))
    }

    /** Present slots in the order the sort puts them — what a full group() is handed. */
    sortedSlots(): number[] {
        const list = this.present()
        const key = (i: SimInstance): [number | string, number] => {
            switch (this.sortMode) {
                case 1: return [-i.slot, i.slot]
                case 2: {
                    const e = i.values[P.num]
                    return [!e || e.k === 'u' ? Number.NEGATIVE_INFINITY : (e as any).v, i.slot]
                }
                case 3: return [i.sha1, i.slot]
                default: return [i.slot, i.slot]
            }
        }
        return list
            .map(i => ({ i, k: key(i) }))
            .sort((a, b) => (a.k[0] < b.k[0] ? -1 : a.k[0] > b.k[0] ? 1 : a.k[1] - b.k[1]))
            .map(x => x.i.slot)
    }

    /**
     * The bucket keys one instance produces at one grouping level. More than one only for tags:
     * a multi-valued tag (and every ancestor of each of its tags) puts the instance in several
     * buckets at once.
     */
    keysAt(inst: SimInstance, level: GroupLevel): any[] {
        const e = inst.values[level.propId] ?? { k: 'u' }
        const type = PROP_TYPE[level.propId]
        switch (type) {
            case PropertyType.number:
                return [e.k === 'u' ? undefined : (e as any).v]
            case PropertyType.string: {
                if (e.k === 'u') return [undefined]
                const v = (e as any).v as string
                return [v === '' ? undefined : v]        // the parser folds '' into "no value"
            }
            case PropertyType.checkbox:
                // Unset and false share one bucket: the parser answers false for both.
                return [e.k === 'u' ? false : !!(e as any).v]
            case PropertyType.date:
                return [e.k === 'u' ? undefined : dateKey((e as any).v as number, level.stepSize, level.stepUnit)]
            case PropertyType.tag:
            case PropertyType.multi_tags: {
                if (e.k !== 't' || (e as any).v.length === 0) return [undefined]
                const parents = TAG_PARENTS[level.propId]
                const out: number[] = []
                for (const tagId of (e as any).v as number[]) {
                    for (const id of [tagId, ...(parents[tagId] ?? [])]) {
                        if (!out.includes(id)) out.push(id)
                    }
                }
                return out.length ? out : [undefined]
            }
            default:
                return [undefined]
        }
    }

    /** Every full key path this instance belongs to, as serialised strings. */
    keyPaths(inst: SimInstance): string[] {
        let paths: any[][] = [[]]
        for (const level of this.groupBy) {
            const keys = this.keysAt(inst, level)
            const next: any[][] = []
            for (const p of paths) for (const k of keys) next.push([...p, k])
            paths = next
        }
        return paths.map(serPath)
    }

    /** instanceId → the set of key paths it must be displayed under. */
    expectedMembership(): Map<number, Set<string>> {
        const out = new Map<number, Set<string>>()
        for (const inst of this.present()) out.set(inst.id, new Set(this.keyPaths(inst)))
        return out
    }
}

// ── key serialisation ────────────────────────────────────────────────────────

/** Tagged, so `undefined`, the number 1 and the string "1" can never collide. */
export function serKey(v: any): string {
    if (v === undefined || v === null) return 'U'
    if (typeof v === 'number') return Number.isNaN(v) ? 'U' : 'N' + v
    if (typeof v === 'string') return 'S' + v
    if (typeof v === 'boolean') return 'B' + v
    return 'X' + String(v)
}

export function serPath(key: any[]): string {
    return key.map(serKey).join('|')
}

// ── date bucketing (independent of src/core/group/dateBuckets) ───────────────

const SECONDS: { [u in DateUnit]?: number } = {
    [DateUnit.Second]: 1,
    [DateUnit.Minute]: 60,
    [DateUnit.Hour]: 3600,
    [DateUnit.Day]: 86400,
    [DateUnit.Week]: 604800,
}

/** The integer bucket a timestamp falls in, written out the plain way. */
export function dateKey(ms: number, stepSize: number, unit: DateUnit): number {
    const step = stepSize || 1
    const d = new Date(ms)
    if (unit === DateUnit.Year) return Math.floor(d.getUTCFullYear() / step)
    if (unit === DateUnit.Month) return Math.floor((d.getUTCFullYear() * 12 + d.getUTCMonth()) / step)
    return Math.floor(ms / (step * SECONDS[unit]! * 1000))
}
