<script setup lang="ts">
// Toolbar icon button that shows which property values are loaded in the browser.
// The icon turns amber while something loads. The panel lists every
// property with its load state and marks the ones the current tab needs.
import { computed, ref } from 'vue'
import Dropdown from './Dropdown.vue'
import wTT from '@/components/tooltips/withToolTip.vue'
import { useDataStore } from '@/data/stores/dataStore'
import { useColumnStore } from '@/data/stores/columnStore'
import { useInstanceStore } from '@/data/stores/instanceStore'
import { TabManager } from '@/core/TabManager'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ tab: TabManager }>()
const { t: $t } = useI18n()

const dataStore     = useDataStore()
const columnStore   = useColumnStore()
const instanceStore = useInstanceStore()
// Keeps the button highlighted while the panel is open.
const open = ref(false)

const instanceCount = computed(() => columnStore.instanceCount)

// ── Load progress ────────────────────────────────────────────────────────
const systemIds = computed(() => {
    const s = columnStore.systemProps
    return new Set([s.INSTANCE_ID, s.SHA1, s.FILE_ID])
})

// Progress of the first load: id, sha1 and file of every image.
const basePct = computed(() => {
    const p = columnStore.baseProgress
    if (!p.loading || !p.max) return null
    return Math.min(100, Math.round((p.counter / p.max) * 100))
})

// Other properties being loaded. The store loads them one at a time,
// so the first one in the list is the one loading now.
const otherLoadingColumns = computed(() =>
    Object.entries(columnStore.fullColumnStatus)
        .filter(([idStr, s]) => s === 'loading' && !systemIds.value.has(Number(idStr)))
        .map(([idStr]) => {
            const id = Number(idStr)
            return { id, name: dataStore.properties[id]?.name ?? `#${id}` }
        })
)
const otherCurrent = computed(() => otherLoadingColumns.value[0] ?? null)
const otherRemaining = computed(() => otherLoadingColumns.value.length)
const otherProgress = computed(() =>
    otherCurrent.value ? columnStore.columnProgress[otherCurrent.value.id] : null
)
const otherPct = computed(() => {
    const p = otherProgress.value
    if (!p || !p.max) return null
    return Math.min(100, Math.round((p.counter / p.max) * 100))
})

const isLoading = computed(() => columnStore.baseProgress.loading || !!otherCurrent.value)

// Properties the tab needs now: the ones shown under the images, and the ones
// used by the active filter, sort and grouping.
const requestedIds = computed(() => {
    const ids = new Set<number>()
    const col = props.tab.collection

    for (const [idStr, visible] of Object.entries(props.tab.state.visibleProperties ?? {})) {
        if (visible) ids.add(Number(idStr))
    }

    for (const id of col.filterManager.getRequiredColumns()) ids.add(id)
    for (const id of col.sortManager.getRequiredColumns())   ids.add(id)
    for (const id of col.getRequiredColumns())  ids.add(id)

    return ids
})

const columns = computed(() =>
    Object.entries(columnStore.fullColumnStatus)
        .map(([idStr, status]) => {
            const id = Number(idStr)
            return {
                id,
                name: dataStore.properties[id]?.name ?? `#${id}`,
                status,
                requested: requestedIds.value.has(id),
            }
        })
        .sort((a, b) => {
            // Needed properties first, then by state (loading, empty, loaded), then by name
            if (a.requested !== b.requested) return a.requested ? -1 : 1
            const order = { loading: 0, empty: 1, loaded: 2 }
            const diff = order[a.status] - order[b.status]
            return diff !== 0 ? diff : a.name.localeCompare(b.name)
        })
)

const requestedCount    = computed(() => requestedIds.value.size)
const trackedInstances  = computed(() => instanceStore.registeredInstanceCount)
</script>

<template>
    <Dropdown :offset="4" placement="bottom-end" @show="open = true" @hide="open = false">
        <template #button>
            <wTT message="dropdown.property_status.title">
            <button class="col-status-btn" :class="{ active: open, loading: isLoading }">
                <i class="bi bi-database-fill-gear" />
            </button>
            </wTT>
        </template>

        <template #popup>
            <div class="col-status-panel">
                <!-- What is loading now -->
                <div v-if="isLoading" class="loading-section">
                    <div v-if="columnStore.baseProgress.loading" class="load-row" :title="$t('dropdown.property_status.loading', { name: $t('dropdown.property_status.base_label') })">
                        <span class="load-name">{{ $t('dropdown.property_status.base_label') }}</span>
                        <div class="load-track">
                            <div class="load-fill" :style="{ width: (basePct ?? 0) + '%' }" />
                        </div>
                        <span v-if="basePct !== null" class="load-pct">{{ basePct }}%</span>
                    </div>
                    <div v-if="otherCurrent" class="load-row" :title="$t('dropdown.property_status.loading', { name: otherCurrent.name })">
                        <span class="load-name">{{ otherCurrent.name }}</span>
                        <span v-if="otherRemaining > 1" class="load-queue">+{{ otherRemaining - 1 }}</span>
                        <div class="load-track">
                            <div class="load-fill" :style="{ width: (otherPct ?? 0) + '%' }" />
                        </div>
                        <span v-if="otherPct !== null" class="load-pct">{{ otherPct }}%</span>
                    </div>
                </div>

                <!-- Counts and legend -->
                <div class="col-status-header tabular-nums">
                    <div class="stat-row">
                        <i class="bi bi-images me-1 text-secondary" />
                        <span class="text-secondary">{{ $t('dropdown.property_status.images_loaded') }}</span>
                        <span class="stat-val">{{ instanceCount.toLocaleString() }}</span>
                    </div>
                    <div class="stat-row">
                        <i class="bi bi-columns me-1 text-secondary" />
                        <span class="text-secondary">{{ $t('dropdown.property_status.properties_total') }}</span>
                        <span class="stat-val">{{ columns.length }}</span>
                    </div>
                    <div class="stat-row">
                        <i class="bi bi-eye me-1 text-secondary" />
                        <span class="text-secondary">{{ $t('dropdown.property_status.images_in_view') }}</span>
                        <span class="stat-val">{{ trackedInstances.toLocaleString() }}</span>
                    </div>
                    <div class="stat-row">
                        <i class="bi bi-arrow-repeat me-1 text-secondary" />
                        <span class="text-secondary">{{ $t('dropdown.property_status.properties_in_use') }}</span>
                        <span class="stat-val">{{ requestedCount }}</span>
                    </div>
                    <div class="legend-row">
                        <span class="legend-item"><span class="dot dot-requested" />{{ $t('dropdown.property_status.legend_in_use') }}</span>
                        <span class="legend-item"><span class="dot dot-loading" />{{ $t('dropdown.property_status.status.loading') }}</span>
                        <span class="legend-item"><span class="dot dot-empty" />{{ $t('dropdown.property_status.status.empty') }}</span>
                        <span class="legend-item"><span class="dot dot-loaded" />{{ $t('dropdown.property_status.status.loaded') }}</span>
                    </div>
                </div>

                <!-- Property list -->
                <div class="col-list">
                    <div v-if="columns.length === 0" class="col-empty-msg text-secondary">
                        {{ $t('dropdown.property_status.no_properties') }}
                    </div>
                    <div v-for="col in columns" :key="col.id" class="col-row" :class="{ 'col-row-active': col.requested }">
                        <span v-if="col.requested" class="dot dot-requested flex-shrink-0" />
                        <span v-else class="dot-spacer" />
                        <span class="col-name">{{ col.name }}</span>
                        <span class="col-badge" :class="`badge-${col.status}`">{{ $t(`dropdown.property_status.status.${col.status}`) }}</span>
                    </div>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
/* ── Trigger ─────────────────────────────────────────────────────────── */
.col-status-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    padding: 0;
    background: none;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 14px;
    color: var(--text-primary);
    transition: background-color var(--transition-fast);
}
.col-status-btn:hover,
.col-status-btn.active {
    background-color: var(--hover-bg);
}
.col-status-btn.loading {
    color: #f0a500;
}

/* ── Panel ───────────────────────────────────────────────────────────── */
.col-status-panel {
    width: 250px;
    max-height: 400px;
    display: flex;
    flex-direction: column;
    background: var(--bg-primary, #fff);
    color: var(--text-primary, #333);
    font-size: 12px;
}

/* The panel can inherit a light text color from the toolbar.
   Set the grey label color here so labels stay readable. */
.col-status-panel .text-secondary {
    color: var(--text-secondary, #666) !important;
}

/* ── Loading now ─────────────────────────────────────────────────────── */
.loading-section {
    padding: 8px 10px;
    border-bottom: 1px solid var(--border-color, #dee2e6);
    background: var(--bg-secondary, #f5f5f5);
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.load-row {
    display: flex;
    align-items: center;
    gap: 6px;
}
.load-name {
    font-size: 11px;
    color: var(--text-primary, #444);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
}
.load-queue {
    font-size: 10px;
    color: var(--text-tertiary, #aaa);
    flex-shrink: 0;
}
.load-track {
    position: relative;
    width: 60px;
    height: 5px;
    background: var(--border-light, #e9ecef);
    border-radius: 3px;
    overflow: hidden;
    flex-shrink: 0;
}
.load-fill {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 0;
    background: #f0a500;
    transition: width 0.2s linear;
}
.load-pct {
    font-size: 10px;
    color: var(--text-secondary, #888);
    min-width: 28px;
    text-align: right;
    flex-shrink: 0;
}

/* ── Header ──────────────────────────────────────────────────────────── */
.col-status-header {
    padding: 8px 10px 6px;
    border-bottom: 1px solid var(--border-color, #dee2e6);
    flex-shrink: 0;
}

.stat-row {
    display: flex;
    align-items: center;
    margin-bottom: 3px;
    gap: 4px;
}
.stat-val {
    margin-left: auto;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}

.legend-row {
    display: flex;
    gap: 8px;
    margin-top: 6px;
    flex-wrap: wrap;
}
.legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
    color: #888;
    font-size: 11px;
}

/* ── Property list ───────────────────────────────────────────────────── */
.col-list {
    overflow-y: auto;
    flex: 1;
    padding: 4px 0;
}

.col-empty-msg {
    padding: 10px;
    text-align: center;
    font-size: 11px;
}

.col-row {
    display: flex;
    align-items: center;
    padding: 3px 10px;
    gap: 6px;
}
.col-row:hover {
    background: rgba(0, 0, 0, 0.04);
}
.col-row-active {
    background: rgba(99, 154, 195, 0.08);
}
.col-row-active:hover {
    background: rgba(99, 154, 195, 0.15);
}

.col-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-primary, #333);
}

/* ── Badges ──────────────────────────────────────────────────────────── */
.col-badge {
    flex-shrink: 0;
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 10px;
    font-weight: 500;
    text-transform: lowercase;
}
.badge-loaded  { background: #d1f0d1; color: #2a7a2a; }
.badge-loading { background: #fff3cd; color: #856404; }
.badge-empty   { background: #e9ecef; color: #6c757d; }

/* ── Dots ────────────────────────────────────────────────────────────── */
.dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
}
.dot-spacer   { display: inline-block; width: 7px; flex-shrink: 0; }
.dot-loaded   { background: #3a9e3a; }
.dot-loading  { background: #f0a500; }
.dot-empty    { background: #b0b8c1; }
.dot-requested { background: #4a90d9; }
</style>
