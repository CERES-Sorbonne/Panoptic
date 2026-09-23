---
tags: [inventory, frontend]
zone: graph
---
# 07 · Graph view

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the chart view that draws the collection's grouping, built on ECharts through `vue-echarts`. The chart logic is kept in pure modules (`chartModel.ts`, `chartOptions.ts`, `chartPalette.ts`) so it can be tested headless.

## Zone-level checks
- [ ] `chartModel.ts` handles every group type (date buckets, numbers, tags, "other" bucket) and reports errors through `ChartErrorKind` instead of throwing.
- [ ] The palette in `chartPalette.ts` works in both light and dark themes, if dark mode is planned.
- [ ] `ChartTooltip.vue` is rendered by Vue, not by ECharts. Check how it's positioned near the viewport edges.
- [ ] Since the builders are pure, the charts can be rendered to SVG headlessly (ECharts `ssr: true`) for regression checks.

## Files
- [ ] `src/components/graphview/GraphView.vue` · 211 L. The graph view entry, selected in `ViewPanel`: toolbar, chart, tooltip, `InstanceData` loading.
- [ ] `src/components/graphview/ChartToolbar.vue` · 143 L. One-row controls above the chart. It mutates the shared graph options.
- [ ] `src/components/graphview/LineChart.vue` · 364 L. The ECharts chart component: builds the option, handles resize and hover events.
- [ ] `src/components/graphview/ChartTooltip.vue` · 135 L. Hover readout, with `CenteredImage` thumbnails.
- [ ] `src/components/graphview/chartModel.ts` · 392 L. Group tree → chart model (buckets, series, cells, errors).
- [ ] `src/components/graphview/chartOptions.ts` · 333 L. Chart model → ECharts option: layout, `compactNumber`.
- [ ] `src/components/graphview/chartPalette.ts` · 52 L. `CHART_PALETTE`, `OTHER_COLOR`, `CHART_CHROME`, `paletteColor`.
