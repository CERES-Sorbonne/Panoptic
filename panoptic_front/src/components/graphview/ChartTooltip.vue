<!-- Hover readout for the graph view. Rendered by Vue (not by the chart library) so the
     thumbnails can use CenteredImage and appear as soon as the instance data lands, even
     while the pointer sits still. -->
<script setup lang="ts">
import CenteredImage from '@/components/images/CenteredImage.vue'

export interface TooltipRow {
    name: string
    color: string
    count: number
}

const props = defineProps<{
    title: string
    total: number
    rows: TooltipRow[]
    instanceIds: number[]
    /** Images in the bucket beyond the thumbnails shown. */
    more: number
}>()
</script>

<template>
    <div class="chart-tooltip">
        <div class="tt-head">
            <span class="tt-title">{{ props.title }}</span>
            <span class="tt-total">{{ props.total.toLocaleString() }}</span>
        </div>

        <!-- Values lead, labels follow: the reader already knows the series and wants the number. -->
        <div v-if="props.rows.length > 1" class="tt-rows">
            <div v-for="row in props.rows" :key="row.name" class="tt-row">
                <span class="tt-key" :style="{ background: row.color }"></span>
                <span class="tt-name">{{ row.name }}</span>
                <span class="tt-value">{{ row.count.toLocaleString() }}</span>
            </div>
        </div>

        <div v-if="props.instanceIds.length" class="tt-images">
            <CenteredImage v-for="id in props.instanceIds" :key="id" :instance-id="id" :width="42" :height="42"
                :cover="true" :no-click="true" />
            <div v-if="props.more > 0" class="tt-more">+{{ props.more }}</div>
        </div>
    </div>
</template>

<style scoped>
.chart-tooltip {
    background: #ffffff;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    box-shadow: 0 4px 16px rgba(11, 11, 11, 0.14);
    padding: 6px 8px;
    font-size: 11px;
    color: var(--text-color);
    width: 246px;
}

.tt-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid var(--border-alpha-40);
}

.tt-title {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.tt-total {
    font-variant-numeric: tabular-nums;
    color: var(--grey-text);
}

.tt-rows {
    margin-top: 4px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-height: 148px;
    overflow: hidden;
}

.tt-row {
    display: flex;
    align-items: center;
    gap: 6px;
}

/* A short stroke, not a filled box: at tooltip density a box is data-weight ink. */
.tt-key {
    width: 10px;
    height: 2px;
    border-radius: 1px;
    flex: 0 0 auto;
}

.tt-name {
    flex: 1 1 auto;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--grey-text);
}

.tt-value {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}

.tt-images {
    margin-top: 6px;
    display: grid;
    grid-template-columns: repeat(5, 42px);
    gap: 3px;
}

.tt-more {
    width: 42px;
    height: 42px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 3px;
    background: var(--grey);
    color: var(--grey-text);
    font-variant-numeric: tabular-nums;
}
</style>
