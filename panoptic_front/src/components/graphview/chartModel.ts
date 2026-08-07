/**
 * Chart model — turns the collection's group tree into something a chart can draw.
 *
 * The shape it produces is deliberately chart-library-agnostic: buckets on the x axis
 * (the first grouping level) and one series per value of the second grouping level, with
 * every cell keeping the SLOTS behind it so a click on the chart can select those images.
 *
 * It reads `result.root.children` directly instead of walking a GroupIterator: the iterator
 * follows the *display* order and skips the children of closed groups, so collapsing a group
 * in the tree view used to make series silently disappear from the chart.
 */
import { Colors, DateUnit, Property, PropertyType, Tag } from '@/data/models'
// The leaf types module, not the GroupManager barrel: the model only needs the tree's shape.
import { GroupType, type Group } from '@/core/group/types'
import type { GroupInspector } from '@/core/group/inspector'
import { isTag, pad } from '@/utils/utils'
import { CHART_PALETTE, OTHER_COLOR } from './chartPalette'

/** How the first grouping level maps onto an x axis. */
export type XKind = 'time' | 'value' | 'category'

export type ChartErrorKind = 'no-grouping' | 'no-result' | 'empty'

/** One (bucket, series) intersection: a leaf group of the tree. */
export interface ChartCell {
    groupId: number
    count: number
    /** Column-store slots — the selection payload. Shared with the tree, never copied. */
    slots: number[]
    /** First instance of the cell, kept loaded to draw the on-curve thumbnail. */
    sampleId?: number
}

/** One x position: a first-level group. */
export interface ChartBucket {
    /** Axis coordinate: epoch ms (time), the number itself (value) or the label (category). */
    x: number | string
    label: string
    count: number
    slots: number[]
    groupId: number
}

export interface ChartSeries {
    /** Stable identity across rebuilds (tag id / raw value / '__other__'). */
    key: string
    name: string
    color: string
    total: number
    /** Index-aligned with `buckets`; null where the value has no images in that bucket. */
    cells: (ChartCell | null)[]
}

export interface ChartModel {
    xKind: XKind
    /** Property driving the x axis. */
    xName: string
    /** Property driving the series, when the collection is grouped two levels deep. */
    seriesName?: string
    buckets: ChartBucket[]
    series: ChartSeries[]
    total: number
    /** Values folded into the grey "Other" series because the palette holds 12. */
    foldedSeries: number
    /** Grouping levels below the second — not chartable, reported to the user. */
    ignoredLevels: number
    /** Images whose value is empty, which a time/number axis has no place for. */
    skippedNoValue: number
    /** Instance ids to keep loaded (one per cell) for the thumbnail overlay. */
    sampleIds: number[]
}

export interface ChartModelResult {
    model?: ChartModel
    error?: ChartErrorKind
}

/** Localised strings the model needs to build labels. Passed in so this stays vue-i18n free. */
export interface ChartLabels {
    count: string
    other: string
    noValue: string
}

/**
 * The store data the model reads, passed in rather than pulled from the stores, so building a
 * chart stays a pure function of tree + data — testable, and callable outside a component.
 */
export interface ChartDataSource {
    properties: Record<number, Property>
    tags: Record<number, Tag>
    /** Slot → instance id, i.e. columnStore.instanceIds(). */
    instanceIds: Int32Array | number[]
}

/** The palette holds 12 slots; past that the smallest values fold into "Other". */
const MAX_SERIES = 12
/** Upper bound on instances we keep loaded for thumbnails, whatever the bucket count. */
const MAX_SAMPLES = 1500

const NUMERIC_TYPES = new Set<PropertyType>([
    PropertyType.number,
    PropertyType._width,
    PropertyType._height,
    PropertyType._id,
])

export function buildChartModel(
    inspector: GroupInspector,
    labels: ChartLabels,
    source: ChartDataSource,
): ChartModelResult {
    const groupBy = inspector.groupState?.groupBy ?? []
    if (!groupBy.length) return { error: 'no-grouping' }

    const xProp = source.properties[groupBy[0]]
    if (!xProp) return { error: 'no-grouping' }
    if (!inspector.hasResult() || !inspector.result?.root) return { error: 'no-result' }

    const seriesProp = groupBy.length > 1 ? source.properties[groupBy[1]] : undefined
    const xKind = axisKind(xProp)

    // ── First level → x buckets ──────────────────────────────────────────────
    const groups: Group[] = []
    const buckets: ChartBucket[] = []
    let skippedNoValue = 0

    for (const group of inspector.result.root.children) {
        if (group.type !== GroupType.Property) continue          // clusters/custom groups aren't values
        const propValue = group.meta.propertyValues?.[0]
        const raw = propValue?.value
        const missing = raw === undefined || raw === null

        let x: number | string
        if (xKind === 'time') {
            const time = toTime(raw)
            if (time === undefined) { skippedNoValue += group.slots.length; continue }
            x = time
        } else if (xKind === 'value') {
            const num = Number(raw)
            if (missing || !Number.isFinite(num)) { skippedNoValue += group.slots.length; continue }
            x = num
        } else {
            x = missing ? labels.noValue : formatValue(raw, xProp, source, propValue?.unit)
        }

        groups.push(group)
        buckets.push({
            x,
            label: missing ? labels.noValue : formatValue(raw, xProp, source, propValue?.unit),
            count: group.slots.length,
            slots: group.slots,
            groupId: group.id,
        })
    }

    if (!buckets.length) return { error: 'empty' }

    // A time/number axis reads left to right, so x must be sorted whatever order the tree is
    // sorted in (groups can be ordered by count). Categories keep the tree's own order.
    if (xKind !== 'category') {
        const order = buckets.map((_, i) => i).sort((a, b) => (buckets[a].x as number) - (buckets[b].x as number))
        reorder(buckets, order)
        reorder(groups, order)
    }

    // ── Second level → series ────────────────────────────────────────────────
    interface Draft { key: string; name: string; tagColor?: string; total: number; cells: (ChartCell | null)[] }
    const drafts = new Map<string, Draft>()
    const nb = buckets.length

    // One series counting each bucket's images — the shape when there is only one grouping
    // level, and the fallback when a second level turns out to hold nothing chartable.
    const countDraft = (): Draft => ({
        key: '__count__',
        name: labels.count,
        total: buckets.reduce((sum, b) => sum + b.count, 0),
        cells: groups.map(g => ({ groupId: g.id, count: g.slots.length, slots: g.slots })),
    })

    if (!seriesProp) {
        drafts.set('__count__', countDraft())
    } else {
        for (let bi = 0; bi < nb; bi++) {
            for (const child of groups[bi].children) {
                if (child.type !== GroupType.Property) continue
                const propValue = child.meta.propertyValues?.[0]
                const raw = propValue?.value
                const missing = raw === undefined || raw === null
                const key = missing ? '__novalue__' : String(raw)

                let draft = drafts.get(key)
                if (!draft) {
                    draft = {
                        key,
                        name: missing ? labels.noValue : formatValue(raw, seriesProp, source, propValue?.unit),
                        tagColor: tagColor(raw, seriesProp, source),
                        total: 0,
                        cells: new Array(nb).fill(null),
                    }
                    drafts.set(key, draft)
                }
                draft.cells[bi] = { groupId: child.id, count: child.slots.length, slots: child.slots }
                draft.total += child.slots.length
            }
        }
    }

    // The second level held nothing chartable (all clusters, or a tree caught mid-rebuild):
    // draw the bucket totals rather than an empty chart.
    if (!drafts.size) drafts.set('__count__', countDraft())

    let list = Array.from(drafts.values())
    let foldedSeries = 0

    // A numeric second level reads top to bottom like the x axis reads left to right:
    // sort the series ascending by value, whatever order the tree keeps them in.
    if (seriesProp && NUMERIC_TYPES.has(seriesProp.type)) {
        list.sort((a, b) => seriesNumericValue(a.key) - seriesNumericValue(b.key))
    }

    if (list.length > MAX_SERIES) {
        // Keep the biggest values (by image count) but leave the survivors in tree order, so
        // a colour follows its value rather than its rank.
        const keep = new Set([...list].sort((a, b) => b.total - a.total).slice(0, MAX_SERIES).map(d => d.key))
        const rest = list.filter(d => !keep.has(d.key))
        foldedSeries = rest.length

        const cells: (ChartCell | null)[] = new Array(nb).fill(null)
        for (let bi = 0; bi < nb; bi++) {
            let count = 0
            const slots: number[] = []
            for (const draft of rest) {
                const cell = draft.cells[bi]
                if (!cell) continue
                count += cell.count
                for (const slot of cell.slots) slots.push(slot)
            }
            if (count) cells[bi] = { groupId: -1, count, slots }
        }

        list = list.filter(d => keep.has(d.key))
        list.push({
            key: '__other__',
            name: `${labels.other} (${foldedSeries})`,
            total: rest.reduce((sum, d) => sum + d.total, 0),
            cells,
        })
    }

    // Tag colours are all-or-nothing: mixing them with the palette would put two unrelated
    // colour systems on one chart, where a pastel tag and a palette slot can collide.
    const useTagColors = !!seriesProp && isTag(seriesProp.type)
        && list.every(d => d.key === '__other__' || !!d.tagColor)

    // The chart addresses series by name (legend, show/hide), so names have to be unique —
    // two tags may well carry the same label.
    const usedNames = new Set<string>()
    const series: ChartSeries[] = list.map((draft, i) => {
        let name = draft.name
        for (let n = 2; usedNames.has(name); n++) name = `${draft.name} (${n})`
        usedNames.add(name)
        return {
            key: draft.key,
            name,
            total: draft.total,
            cells: draft.cells,
            color: draft.key === '__other__'
                ? OTHER_COLOR
                : (useTagColors ? draft.tagColor! : CHART_PALETTE[i % CHART_PALETTE.length]),
        }
    })

    // ── Thumbnail samples ────────────────────────────────────────────────────
    // One instance per cell, bucket by bucket, so a truncated budget still yields an even
    // spread rather than every thumbnail of the first series and none of the rest.
    const sampleIds: number[] = []
    const seen = new Set<number>()
    for (let bi = 0; bi < nb && sampleIds.length < MAX_SAMPLES; bi++) {
        for (const s of series) {
            const cell = s.cells[bi]
            if (!cell || !cell.slots.length) continue
            const id = source.instanceIds[cell.slots[0]]
            cell.sampleId = id
            if (!seen.has(id)) {
                seen.add(id)
                sampleIds.push(id)
            }
        }
    }

    return {
        model: {
            xKind,
            xName: xProp.name,
            seriesName: seriesProp?.name,
            buckets,
            series,
            total: buckets.reduce((sum, b) => sum + b.count, 0),
            foldedSeries,
            ignoredLevels: Math.max(0, groupBy.length - 2),
            skippedNoValue,
            sampleIds,
        },
    }
}

/**
 * Whether a thumbnail can be placed on each mark. Grouped bars sit off the band centre, so
 * there is no honest place to put one; every other combination has the mark on the bucket's x.
 */
export function thumbnailsAvailable(model: ChartModel, options: { chartType: string; stacked: boolean }): boolean {
    return options.chartType !== 'bar' || model.series.length === 1 || options.stacked
}

/** Instance ids of a bucket, capped — for the hover tooltip's thumbnail strip. */
export function bucketInstanceIds(bucket: ChartBucket, max: number, instanceIds: Int32Array | number[]): number[] {
    const ids: number[] = []
    for (let i = 0; i < bucket.slots.length && ids.length < max; i++) ids.push(instanceIds[bucket.slots[i]])
    return ids
}

function axisKind(property: Property): XKind {
    if (property.type === PropertyType.date) return 'time'
    if (NUMERIC_TYPES.has(property.type)) return 'value'
    return 'category'
}

/** Sort key for a numeric series: the raw value, with missing values last. */
function seriesNumericValue(key: string): number {
    if (key === '__novalue__') return Number.MAX_VALUE
    const n = Number(key)
    return Number.isFinite(n) ? n : Number.MAX_VALUE
}

function toTime(raw: any): number | undefined {
    if (raw === undefined || raw === null) return undefined
    const date = raw instanceof Date ? raw : new Date(raw)
    const time = date.getTime()
    return Number.isFinite(time) ? time : undefined
}

function tagColor(raw: any, property: Property, source: ChartDataSource): string | undefined {
    if (!isTag(property.type)) return undefined
    const tag = source.tags[Number(raw)]
    if (!tag || tag.color === undefined || tag.color === null) return undefined
    if (tag.color < 0 || tag.color >= Colors.length) return undefined
    return Colors[tag.color].color
}

/**
 * Human label for a group value. Dates mirror PropertyValue.vue: formatted in UTC (the
 * grouping buckets them in UTC) and truncated to the grouping's own unit, so a bucket reads
 * the same here as in the tree.
 */
function formatValue(raw: any, property: Property, source: ChartDataSource, unit?: DateUnit): string {
    switch (property.type) {
        case PropertyType.date: {
            const date = raw instanceof Date ? raw : new Date(raw)
            return Number.isFinite(date.getTime()) ? formatDate(date, unit) : String(raw)
        }
        case PropertyType.tag:
        case PropertyType.multi_tags:
            return source.tags[Number(raw)]?.value ?? String(raw)
        case PropertyType.checkbox:
            return raw ? '✓' : '✗'
        case PropertyType.color: {
            const index = Number(raw)
            return Colors[index]?.name ?? String(raw)
        }
        default:
            return String(raw)
    }
}

function formatDate(date: Date, unit?: DateUnit): string {
    let res = String(date.getUTCFullYear())
    if (unit === DateUnit.Year) return res
    res += '/' + pad(date.getUTCMonth() + 1)
    if (unit === DateUnit.Month) return res
    res += '/' + pad(date.getUTCDate())
    if (unit === DateUnit.Week || unit === DateUnit.Day) return res
    res += ' ' + pad(date.getUTCHours())
    if (unit === DateUnit.Hour) return res + 'h'
    return res + ':' + pad(date.getUTCMinutes())
}

function reorder<T>(list: T[], order: number[]) {
    const copy = list.slice()
    for (let i = 0; i < order.length; i++) list[i] = copy[order[i]]
}
