/**
 * ECharts option for the graph view.
 *
 * Kept as a pure function of (model, display options, render context) with no store access,
 * so the whole chart can be built — and rendered headlessly — without a running app. The
 * component feeds in the reactive parts: what is selected, what the legend hides, and which
 * thumbnails have loaded.
 *
 * The module also declares the chart features it uses, so registration can never drift from
 * the option it produces.
 */
import { use, type EChartsCoreOption } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, ScatterChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, MarkAreaComponent } from 'echarts/components'
import type { GraphOptions } from '@/data/models'
import type { ChartModel } from './chartModel'
import { CHART_CHROME } from './chartPalette'

use([
    CanvasRenderer, GridComponent, LegendComponent, DataZoomComponent, MarkAreaComponent,
    LineChart, BarChart, ScatterChart,
])

const THUMB_SIZE = 34
const DIM_OPACITY = 0.3
/** Above this many buckets, line markers become noise and the zoom slider earns its space. */
const SYMBOL_LIMIT = 30
const SLIDER_LIMIT = 24

/**
 * Plot geometry. The paddings are fixed and known rather than derived by the chart, which is
 * what lets the component compute the plot rectangle itself for the crosshair, the drag band
 * and pointer hit-testing — no reaching into chart internals.
 */
export interface ChartLayout {
    left: number
    right: number
    top: number
    bottom: number
    showLegend: boolean
    showSlider: boolean
}

export function chartLayout(model: ChartModel): ChartLayout {
    const showLegend = model.series.length > 1
    const showSlider = model.buckets.length > SLIDER_LIMIT
    return {
        left: 54,
        right: 26,
        top: showLegend ? 34 : 14,
        bottom: showSlider ? 54 : 28,
        showLegend,
        showSlider,
    }
}

export interface ChartRenderContext {
    /** [seriesIndex][bucketIndex]: does the cell hold at least one selected image. */
    selected: boolean[][]
    /** Whether anything at all is selected — drives the dimming of everything else. */
    anySelected: boolean
    isVisible: (seriesName: string) => boolean
    /** Thumbnail url of an instance, or undefined while it is still loading. */
    imageUrl: (instanceId: number) => string | undefined
    thumbnails: boolean
}

export function buildChartOption(
    model: ChartModel,
    options: GraphOptions,
    ctx: ChartRenderContext,
): EChartsCoreOption {
    const { xKind, buckets, series } = model
    const type = options.chartType
    const stacked = options.stacked && series.length > 1
    const layout = chartLayout(model)
    const axisText = { color: CHART_CHROME.label, fontSize: 10 }

    const xAxis: any = {
        axisLine: { lineStyle: { color: CHART_CHROME.axis } },
        axisTick: { show: false },
        axisLabel: { ...axisText, hideOverlap: true },
        splitLine: { show: false },
    }
    if (xKind === 'category') {
        xAxis.type = 'category'
        xAxis.data = buckets.map(b => b.label)
        // Bands rather than ticks, in every mode: a mark then sits at the centre of its own
        // band instead of on the plot edge, and bars, points and thumbnails all share that x.
        xAxis.boundaryGap = true
    } else {
        xAxis.type = xKind === 'time' ? 'time' : 'value'
        // Pad the extent by half a bucket, the same air a category band gives. Done with
        // explicit min/max because time and value axes ignore boundaryGap here, and without it
        // the first and last marks straddle the plot edge and get half-clipped.
        const half = halfGap(model)
        xAxis.min = (buckets[0].x as number) - half
        xAxis.max = (buckets[buckets.length - 1].x as number) + half
    }

    const drawn: any[] = []

    for (let si = 0; si < series.length; si++) {
        const s = series[si]
        const data = buckets.map((bucket, bi) => {
            const count = s.cells[bi]?.count ?? 0
            const item: any = { value: xKind === 'category' ? count : [bucket.x, count] }
            if (ctx.anySelected) {
                if (ctx.selected[si]?.[bi]) item.symbolSize = 12
                else item.itemStyle = { opacity: DIM_OPACITY }
            }
            return item
        })

        if (type === 'bar') {
            drawn.push({
                id: `s${si}`,
                name: s.name,
                type: 'bar',
                stack: stacked ? 'total' : undefined,
                barMaxWidth: 24,
                barCategoryGap: '30%',
                itemStyle: {
                    color: s.color,
                    borderRadius: stacked ? [2, 2, 0, 0] : [4, 4, 0, 0],
                    // A surface-coloured border is how canvas draws the 2px gap that has to
                    // separate touching marks.
                    borderColor: CHART_CHROME.surface,
                    borderWidth: stacked ? 2 : 0,
                },
                emphasis: { focus: 'series' },
                data,
            })
        } else {
            drawn.push({
                id: `s${si}`,
                name: s.name,
                type: 'line',
                stack: stacked ? 'total' : undefined,
                symbol: 'circle',
                symbolSize: 8,
                showSymbol: buckets.length <= SYMBOL_LIMIT,
                lineStyle: { width: 2, color: s.color, cap: 'round', join: 'round' },
                // 2px surface ring, so markers stay legible where they cross a line.
                itemStyle: { color: s.color, borderColor: CHART_CHROME.surface, borderWidth: 2 },
                areaStyle: type === 'area'
                    // A wash when overlaid; stacked areas have to read as solid bands instead.
                    ? { color: s.color, opacity: stacked ? 0.45 : 0.1 }
                    : undefined,
                emphasis: { focus: 'series', scale: 1.3 },
                data,
            })
        }
    }

    if (ctx.thumbnails) {
        const tops = stacked ? stackedTops(model, ctx) : null
        for (let si = 0; si < series.length; si++) {
            const s = series[si]
            if (!ctx.isVisible(s.name)) continue
            const data: any[] = []
            for (let bi = 0; bi < buckets.length; bi++) {
                const cell = s.cells[bi]
                if (!cell || cell.sampleId === undefined) continue
                const url = ctx.imageUrl(cell.sampleId)
                if (!url) continue
                data.push({
                    // Category axes are addressed by name, not index: a zoom window filters the
                    // category list, and an index would then point at the wrong bucket.
                    value: [xKind === 'category' ? buckets[bi].label : buckets[bi].x, tops ? tops[si][bi] : cell.count],
                    symbol: `image://${url}`,
                })
            }
            drawn.push({
                id: `thumbs${si}`,
                name: `__thumbs${si}`,
                type: 'scatter',
                symbolSize: THUMB_SIZE,
                silent: true,
                legendHoverLink: false,
                animation: false,
                z: 6,
                data,
            })
        }
    }

    // The band behind the selected buckets lives on its own dataless series, so hiding a
    // series in the legend can never take the selection feedback with it.
    drawn.push({
        id: 'selection',
        name: '__selection',
        type: 'line',
        data: [],
        silent: true,
        legendHoverLink: false,
        animation: false,
        markArea: {
            silent: true,
            itemStyle: { color: CHART_CHROME.selection },
            data: selectionBands(model, ctx),
        },
    })

    return {
        // Date groups are bucketed in UTC, so the axis has to label them in UTC too.
        useUTC: true,
        animationDuration: 220,
        grid: { left: layout.left, right: layout.right, top: layout.top, bottom: layout.bottom },
        legend: {
            show: layout.showLegend,
            type: 'scroll',
            top: 6,
            left: 0,
            right: 0,
            itemGap: 14,
            itemWidth: 12,
            // Mirror the mark: a short stroke for lines, a block for bars and areas.
            itemHeight: type === 'line' ? 4 : 8,
            icon: 'roundRect',
            textStyle: { color: CHART_CHROME.ink, fontSize: 11 },
            data: series.map(s => s.name),
        },
        xAxis,
        yAxis: {
            type: 'value',
            minInterval: 1,
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: { ...axisText, formatter: compactNumber },
            splitLine: { lineStyle: { color: CHART_CHROME.grid, width: 1, type: 'solid' } },
        },
        // No tooltip component on purpose: the readout is a Vue overlay (ChartTooltip.vue).
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: 0,
                zoomOnMouseWheel: true,
                // Dragging belongs to selection; panning belongs to the slider.
                moveOnMouseMove: false,
                moveOnMouseWheel: false,
                filterMode: 'filter',
            },
            ...(layout.showSlider ? [{
                type: 'slider',
                xAxisIndex: 0,
                height: 16,
                bottom: 8,
                borderColor: 'transparent',
                backgroundColor: '#f7f9fa',
                fillerColor: 'rgba(22, 120, 194, 0.08)',
                dataBackground: {
                    lineStyle: { color: CHART_CHROME.axis },
                    areaStyle: { color: CHART_CHROME.grid },
                },
                selectedDataBackground: {
                    lineStyle: { color: CHART_CHROME.axis },
                    areaStyle: { color: CHART_CHROME.grid },
                },
                handleStyle: { color: '#fff', borderColor: CHART_CHROME.axis },
                moveHandleStyle: { color: CHART_CHROME.axis },
                textStyle: { color: CHART_CHROME.label, fontSize: 9 },
                filterMode: 'filter',
            }] : []),
        ],
        series: drawn,
    }
}

/** Axis labels stay narrow: 1.2K / 3.4M rather than 1200 / 3400000. */
export function compactNumber(value: number): string {
    if (value >= 1e6) return (value / 1e6).toFixed(value >= 1e7 ? 0 : 1).replace(/\.0$/, '') + 'M'
    if (value >= 1e3) return (value / 1e3).toFixed(value >= 1e4 ? 0 : 1).replace(/\.0$/, '') + 'K'
    return String(value)
}

/**
 * Half the typical distance between two buckets on a time/number axis — the axis' own idea of
 * "one bucket wide", used to pad the extent and to give selection bands their width. The median
 * rather than the mean, so one long gap in an otherwise regular series doesn't skew it.
 */
function halfGap(model: ChartModel): number {
    const { buckets, xKind } = model
    if (xKind === 'category') return 0.5
    if (buckets.length < 2) return xKind === 'time' ? 12 * 3600 * 1000 : 0.5
    const gaps: number[] = []
    for (let i = 1; i < buckets.length; i++) gaps.push((buckets[i].x as number) - (buckets[i - 1].x as number))
    gaps.sort((a, b) => a - b)
    return (gaps[Math.floor(gaps.length / 2)] || 1) / 2
}

/** Cumulative y per (series, bucket) over the visible series — where a stacked mark ends. */
function stackedTops(model: ChartModel, ctx: ChartRenderContext): number[][] {
    const running = new Array(model.buckets.length).fill(0)
    return model.series.map(s => {
        const row = new Array(model.buckets.length).fill(0)
        for (let bi = 0; bi < model.buckets.length; bi++) {
            if (ctx.isVisible(s.name)) running[bi] += s.cells[bi]?.count ?? 0
            row[bi] = running[bi]
        }
        return row
    })
}

/** Contiguous runs of selected buckets, as markArea coordinate pairs. */
function selectionBands(model: ChartModel, ctx: ChartRenderContext): any[] {
    const { buckets, series, xKind } = model
    if (!ctx.anySelected) return []

    const selected = buckets.map((_, bi) =>
        series.some((s, si) => ctx.isVisible(s.name) && ctx.selected[si]?.[bi]))

    // Half a bucket, so a single selected bucket still gets a band with width.
    const half = halfGap(model)
    const bands: any[] = []
    let start = -1
    for (let bi = 0; bi <= buckets.length; bi++) {
        if (bi < buckets.length && selected[bi]) {
            if (start < 0) start = bi
            continue
        }
        if (start < 0) continue
        const from = buckets[start]
        const to = buckets[bi - 1]
        bands.push(xKind === 'category'
            ? [{ xAxis: from.label }, { xAxis: to.label }]
            : [{ xAxis: (from.x as number) - half }, { xAxis: (to.x as number) + half }])
        start = -1
    }
    return bands
}
