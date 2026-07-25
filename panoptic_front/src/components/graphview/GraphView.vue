<!--
  Graph view: draws the collection's grouping as a chart.

  The first grouping level becomes the x axis (a time axis for dates, a numeric axis for
  numbers, categories for anything else) and the second becomes one series per value. This
  component owns the state around the chart — options, instance loading, empty states and
  what a selection on the chart means — while LineChart.vue owns the drawing and the pointer
  handling, and chartModel.ts the translation from group tree to chart data.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { CollectionManager } from '@/core/CollectionManager'
import { useColumnStore } from '@/data/columnStore'
import { useDataStore } from '@/data/dataStore'
import { GraphOptions, ViewState } from '@/data/models'
import { createGraphOptions } from '@/data/builder'
import InstanceData from '@/components/data/InstanceData.vue'
import LineChart from './LineChart.vue'
import ChartToolbar from './ChartToolbar.vue'
import ChartTooltip from './ChartTooltip.vue'
import {
    bucketInstanceIds, buildChartModel, thumbnailsAvailable, ChartModel, ChartErrorKind,
} from './chartModel'

/** Thumbnails shown in the hover readout (a 5-wide grid, two rows). */
const TOOLTIP_IMAGES = 10
const TOOLBAR_HEIGHT = 28
const FOOTER_HEIGHT = 18

const { t } = useI18n()
const columnStore = useColumnStore()
const dataStore = useDataStore()

const props = defineProps<{
    collection: CollectionManager
    height: number
    /** Display options live on the view when there is one, so they persist with the tab. */
    view?: ViewState
}>()

// Fallback for callers with no view state; also the target while an older persisted view has
// no graphOptions yet.
const fallbackOptions = ref<GraphOptions>(createGraphOptions())

const options = computed<GraphOptions>(() => props.view?.graphOptions ?? fallbackOptions.value)

watch(() => props.view, view => {
    if (view && !view.graphOptions) view.graphOptions = createGraphOptions()
}, { immediate: true })

// ── Chart data ───────────────────────────────────────────────────────────────
const model = ref<ChartModel | null>(null)
const error = ref<ChartErrorKind | null>(null)

function rebuild() {
    const result = buildChartModel(
        props.collection,
        {
            count: t('main.graph-view.images'),
            other: t('main.graph-view.other'),
            noValue: t('main.graph-view.no_value'),
        },
        { properties: dataStore.properties, tags: dataStore.tags, instanceIds: columnStore.instanceIds() },
    )
    model.value = result.model ?? null
    error.value = result.error ?? null
}

// The version tick is the result-change signal (note §3, step 1).
watch(() => [props.collection, props.collection.version.value], rebuild, { immediate: true })

// ── Instance loading ─────────────────────────────────────────────────────────
const hoverIndex = ref<number | null>(null)

const hoverIds = computed(() => {
    const bucket = model.value && hoverIndex.value !== null ? model.value.buckets[hoverIndex.value] : null
    return bucket ? bucketInstanceIds(bucket, TOOLTIP_IMAGES, columnStore.instanceIds()) : []
})

// One instance per data point for the on-chart thumbnails, plus the hovered bucket's strip.
const instanceIds = computed(() => [...(model.value?.sampleIds ?? []), ...hoverIds.value])

const propIds = computed(() => {
    const sha1 = columnStore.systemProps.SHA1
    return sha1 ? [sha1] : []
})

// ── Selection ────────────────────────────────────────────────────────────────
const namespace = computed(() => props.collection.selectionNamespace)

const selectedCount = computed(() => {
    columnStore.selectionTick(namespace.value)
    return columnStore.selectedCount(namespace.value)
})

function onSelect({ slots, mode }: { slots: number[]; mode: 'replace' | 'add' | 'remove' }) {
    const ns = namespace.value
    if (mode === 'remove') { columnStore.deselect(slots, ns); return }
    if (mode === 'replace') columnStore.clearSelection(ns)
    columnStore.select(slots, ns)
}

function clearSelection() {
    columnStore.clearSelection(namespace.value)
}

// ── Layout / messages ────────────────────────────────────────────────────────
const chartHeight = computed(() => Math.max(120, props.height - TOOLBAR_HEIGHT - FOOTER_HEIGHT))

const notes = computed(() => {
    const current = model.value
    if (!current) return []
    const list: string[] = []
    if (current.ignoredLevels > 0) list.push(t('main.graph-view.ignored_levels'))
    if (current.foldedSeries > 0) list.push(t('main.graph-view.folded', { count: current.foldedSeries }))
    if (current.skippedNoValue > 0) list.push(t('main.graph-view.skipped_no_value', { count: current.skippedNoValue }))
    return list
})
</script>

<template>
    <InstanceData :instance-ids="instanceIds" :prop-ids="propIds">
        <div class="graph-view" :style="{ height: props.height + 'px' }">
            <template v-if="model">
                <ChartToolbar :options="options" :series-count="model.series.length" :total="model.total"
                    :selected="selectedCount" :thumbnails-available="thumbnailsAvailable(model, options)"
                    @clear-selection="clearSelection" />

                <LineChart :model="model" :options="options" :namespace="namespace" :height="chartHeight"
                    @hover="hoverIndex = $event" @select="onSelect">
                    <template #tooltip="{ bucket, rows }">
                        <ChartTooltip :title="bucket.label" :total="bucket.count" :rows="rows"
                            :instance-ids="hoverIds" :more="Math.max(0, bucket.count - hoverIds.length)" />
                    </template>
                </LineChart>

                <div class="footer">
                    <span class="hint">{{ $t('main.graph-view.hint') }}</span>
                    <span v-for="note in notes" :key="note" class="note">
                        <i class="bi bi-info-circle"></i> {{ note }}
                    </span>
                </div>
            </template>

            <!-- Empty states: say what the view needs, not that something failed. -->
            <div v-else class="empty">
                <template v-if="error === 'no-grouping'">
                    <i class="bi bi-bar-chart-line empty-icon"></i>
                    <div class="empty-title">{{ $t('main.graph-view.no_grouping') }}</div>
                    <div class="empty-hint">{{ $t('main.graph-view.no_grouping_hint') }}</div>
                </template>
                <template v-else-if="error === 'empty'">
                    <div class="empty-title">{{ $t('main.graph-view.empty') }}</div>
                </template>
                <div v-else class="empty-hint">{{ $t('main.graph-view.loading') }}</div>
            </div>
        </div>
    </InstanceData>
</template>

<style scoped>
.graph-view {
    display: flex;
    flex-direction: column;
    min-width: 0;
}

.footer {
    display: flex;
    align-items: center;
    gap: 12px;
    height: 18px;
    font-size: 10px;
    color: var(--text-tertiary);
    overflow: hidden;
    white-space: nowrap;
}

.note {
    color: var(--grey-text);
}

.empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    color: var(--grey-text);
}

.empty-icon {
    font-size: 22px;
    color: var(--text-tertiary);
}

.empty-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
}

.empty-hint {
    font-size: 11px;
    max-width: 380px;
    text-align: center;
}
</style>
