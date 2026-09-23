<!-- Controls for the graph view. Sits in one row above the chart; mutates the shared
     (per-view, persisted) GraphOptions object directly, like the other view toolbars do. -->
<script setup lang="ts">
import { GraphOptions } from '@/data/models'
import wTT from '@/components/tooltips/withToolTip.vue'

const props = defineProps<{
    options: GraphOptions
    /** Number of drawn series — stacking is meaningless below two. */
    seriesCount: number
    total: number
    selected: number
    /** False for grouped bars, where a thumbnail has no honest place to sit. */
    thumbnailsAvailable: boolean
}>()

const emits = defineEmits<{ (e: 'clear-selection'): void }>()

const types: { value: GraphOptions['chartType']; icon: string; tip: string }[] = [
    { value: 'line', icon: 'bi-activity', tip: 'main.graph-view.chart_line' },
    { value: 'area', icon: 'bi-graph-up', tip: 'main.graph-view.chart_area' },
    { value: 'bar', icon: 'bi-bar-chart-fill', tip: 'main.graph-view.chart_bar' },
]
</script>

<template>
    <div class="chart-toolbar">
        <div class="segmented">
            <wTT v-for="t in types" :key="t.value" :message="t.tip" :click="false">
                <button class="seg-btn" :class="{ active: props.options.chartType === t.value }"
                    @click="props.options.chartType = t.value">
                    <i class="bi" :class="t.icon"></i>
                </button>
            </wTT>
        </div>

        <wTT message="main.graph-view.stack" :click="false" v-if="props.seriesCount > 1">
            <button class="tool-btn" :class="{ active: props.options.stacked }"
                @click="props.options.stacked = !props.options.stacked">
                <i class="bi bi-layers-half"></i>
            </button>
        </wTT>

        <wTT :message="props.thumbnailsAvailable ? 'main.graph-view.thumbnails' : 'main.graph-view.thumbnails_grouped'"
            :click="false">
            <button class="tool-btn" :class="{ active: props.options.showThumbnails && props.thumbnailsAvailable }"
                :disabled="!props.thumbnailsAvailable"
                @click="props.options.showThumbnails = !props.options.showThumbnails">
                <i class="bi bi-images"></i>
            </button>
        </wTT>

        <div class="flex-grow-1"></div>

        <span class="count">{{ $t('main.graph-view.total_images', { count: props.total.toLocaleString() }) }}</span>

        <button v-if="props.selected > 0" class="sel-chip" @click="emits('clear-selection')">
            {{ $t('main.graph-view.selected', { count: props.selected.toLocaleString() }) }}
            <i class="bi bi-x"></i>
        </button>
    </div>
</template>

<style scoped>
.chart-toolbar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 2px 4px 4px 0;
    height: 28px;
}

.segmented {
    display: inline-flex;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
}

.seg-btn,
.tool-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 22px;
    border: none;
    background: none;
    color: var(--grey-text);
    font-size: 12px;
    line-height: 1;
    cursor: pointer;
}

.tool-btn {
    border: 1px solid var(--border-color);
    border-radius: 4px;
}

.seg-btn:hover,
.tool-btn:hover {
    background: var(--border-alpha-40);
}

.tool-btn:disabled {
    opacity: 0.4;
    cursor: default;
    background: none;
}

.seg-btn.active,
.tool-btn.active {
    background: var(--primary-light);
    color: var(--primary);
}

.count {
    font-size: 11px;
    color: var(--grey-text);
    font-variant-numeric: tabular-nums;
}

.sel-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    height: 22px;
    padding: 0 4px 0 8px;
    border: 1px solid var(--primary);
    border-radius: 11px;
    background: var(--primary-light);
    color: var(--primary);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
    cursor: pointer;
}

.sel-chip:hover {
    background: var(--primary);
    color: #fff;
}
</style>
