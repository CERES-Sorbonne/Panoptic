<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useDataStore } from '@/data/dataStore'
import { useColumnStore } from '@/data/columnStore'
import { useInstanceStore } from '@/data/instanceStore'
import { TabManager } from '@/core/TabManager'

const vClickOutside = {
    mounted(el: HTMLElement & { _coHandler?: (e: MouseEvent) => void }, binding: { value: () => void }) {
        el._coHandler = (e: MouseEvent) => { if (!el.contains(e.target as Node)) binding.value() }
        document.addEventListener('click', el._coHandler)
    },
    unmounted(el: HTMLElement & { _coHandler?: (e: MouseEvent) => void }) {
        if (el._coHandler) document.removeEventListener('click', el._coHandler)
    },
}

const props = defineProps<{ tab: TabManager }>()

const dataStore     = useDataStore()
const columnStore   = useColumnStore()
const instanceStore = useInstanceStore()
const open = ref(false)
const triggerEl = ref<HTMLElement>()
// The panel is position:fixed (to escape the toolbar's overflow:hidden), so its
// coordinates are derived from the trigger button each time it opens.
const panelStyle = ref<Record<string, string>>({})

function toggle() {
    open.value = !open.value
    if (open.value) nextTick(positionPanel)
}

function positionPanel() {
    const r = triggerEl.value?.getBoundingClientRect()
    if (!r) return
    panelStyle.value = { top: `${r.bottom + 4}px`, left: `${r.left}px` }
}

const instanceCount = computed(() => columnStore.instanceCount)

// ── Live load progress (merged from ColumnLoadProgress) ──────────────────
const systemIds = computed(() => {
    const s = columnStore.systemProps
    return new Set([s.INSTANCE_ID, s.SHA1, s.FILE_ID])
})

// Base (id/sha1/file) loading from init()
const basePct = computed(() => {
    const p = columnStore.baseProgress
    if (!p.loading || !p.max) return null
    return Math.min(100, Math.round((p.counter / p.max) * 100))
})

// Other columns loading via requireFullColumn(), one at a time
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
// Progress shown on the trigger bar: the base load takes priority, else the current column.
const primaryPct = computed(() => columnStore.baseProgress.loading ? basePct.value : otherPct.value)

// Columns currently required by the tab: visible properties + active filter/sort/group.
const requestedIds = computed(() => {
    const ids = new Set<number>()
    const col = props.tab.collection

    // Properties rendered under each image in this tab
    for (const [idStr, visible] of Object.entries(props.tab.state.visibleProperties ?? {})) {
        if (visible) ids.add(Number(idStr))
    }

    // Properties needed for filter / sort / group computation
    for (const id of col.filterManager.getRequiredColumns()) ids.add(id)
    for (const id of col.sortManager.getRequiredColumns())   ids.add(id)
    for (const id of col.groupManager.getRequiredColumns())  ids.add(id)

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
            // requested first, then by status (loading → empty → loaded), then name
            if (a.requested !== b.requested) return a.requested ? -1 : 1
            const order = { loading: 0, empty: 1, loaded: 2 }
            const diff = order[a.status] - order[b.status]
            return diff !== 0 ? diff : a.name.localeCompare(b.name)
        })
)

const loadedCount   = computed(() => columns.value.filter(c => c.status === 'loaded').length)
const loadingCount  = computed(() => columns.value.filter(c => c.status === 'loading').length)
const emptyCount    = computed(() => columns.value.filter(c => c.status === 'empty').length)
const requestedCount    = computed(() => requestedIds.value.size)
const trackedInstances  = computed(() => instanceStore.registeredInstanceCount)
</script>

<template>
    <div class="col-status-root me-1" v-click-outside="() => open = false">
        <!-- Trigger button -->
        <button ref="triggerEl" class="col-status-btn" :class="{ active: open, loading: isLoading }" @click="toggle" title="Column status">
            <i class="bi bi-database-fill-gear" />
            <span class="col-status-summary">
                <span class="instance-count">{{ instanceCount.toLocaleString() }}</span>
                <span class="separator">|</span>
                <span class="dot dot-loaded" />{{ loadedCount }}
                <span v-if="loadingCount" class="dot dot-loading ms-1" />
                <span v-if="loadingCount">{{ loadingCount }}</span>
                <span v-if="emptyCount" class="dot dot-empty ms-1" />
                <span v-if="emptyCount">{{ emptyCount }}</span>
            </span>
            <!-- Live load progress on the right -->
            <span v-if="isLoading" class="trigger-progress">
                <span class="separator">|</span>
                <span class="trigger-progress-track">
                    <span class="trigger-progress-fill" :style="{ width: (primaryPct ?? 0) + '%' }" />
                </span>
                <span v-if="primaryPct !== null" class="trigger-progress-pct">{{ primaryPct }}%</span>
            </span>
        </button>

        <!-- Panel -->
        <div v-if="open" class="col-status-panel shadow-sm" :style="panelStyle">
            <!-- Loading now (merged from ColumnLoadProgress) -->
            <div v-if="isLoading" class="loading-section">
                <div v-if="columnStore.baseProgress.loading" class="load-row" title="Loading: id, sha1, file">
                    <span class="load-name">id, sha1, file</span>
                    <div class="load-track">
                        <div class="load-fill" :style="{ width: (basePct ?? 0) + '%' }" />
                    </div>
                    <span v-if="basePct !== null" class="load-pct">{{ basePct }}%</span>
                </div>
                <div v-if="otherCurrent" class="load-row" :title="`Loading: ${otherCurrent.name}`">
                    <span class="load-name">{{ otherCurrent.name }}</span>
                    <span v-if="otherRemaining > 1" class="load-queue">+{{ otherRemaining - 1 }}</span>
                    <div class="load-track">
                        <div class="load-fill" :style="{ width: (otherPct ?? 0) + '%' }" />
                    </div>
                    <span v-if="otherPct !== null" class="load-pct">{{ otherPct }}%</span>
                </div>
            </div>

            <!-- Header stats -->
            <div class="col-status-header">
                <div class="stat-row">
                    <i class="bi bi-images me-1 text-secondary" />
                    <span class="text-secondary">Instances loaded</span>
                    <span class="stat-val">{{ instanceCount.toLocaleString() }}</span>
                </div>
                <div class="stat-row">
                    <i class="bi bi-columns me-1 text-secondary" />
                    <span class="text-secondary">Columns tracked</span>
                    <span class="stat-val">{{ columns.length }}</span>
                </div>
                <div class="stat-row">
                    <i class="bi bi-eye me-1 text-secondary" />
                    <span class="text-secondary">Instances in view</span>
                    <span class="stat-val">{{ trackedInstances.toLocaleString() }}</span>
                </div>
                <div class="stat-row">
                    <i class="bi bi-arrow-repeat me-1 text-secondary" />
                    <span class="text-secondary">Columns in use</span>
                    <span class="stat-val">{{ requestedCount }}</span>
                </div>
                <div class="legend-row">
                    <span class="legend-item"><span class="dot dot-requested" />in use</span>
                    <span class="legend-item"><span class="dot dot-loading" />loading</span>
                    <span class="legend-item"><span class="dot dot-empty" />empty</span>
                    <span class="legend-item"><span class="dot dot-loaded" />loaded</span>
                </div>
            </div>

            <!-- Column list -->
            <div class="col-list">
                <div v-if="columns.length === 0" class="col-empty-msg text-secondary">
                    No columns registered yet.
                </div>
                <div v-for="col in columns" :key="col.id" class="col-row" :class="{ 'col-row-active': col.requested }">
                    <span v-if="col.requested" class="dot dot-requested flex-shrink-0" />
                    <span v-else class="dot-spacer" />
                    <span class="col-name">{{ col.name }}</span>
                    <span class="col-badge" :class="`badge-${col.status}`">{{ col.status }}</span>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.col-status-root {
    position: relative;
    display: inline-flex;
    align-items: center;
}

/* ── Trigger ─────────────────────────────────────────────────────────── */
.col-status-btn {
    position: relative;
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 4px 8px;
    border: 1px solid var(--border-color, #dee2e6);
    border-radius: 5px;
    background: transparent;
    cursor: pointer;
    font-size: 12px;
    color: var(--text-primary, #1a1a1a);
    white-space: nowrap;
    transition: background 0.15s;
}
.col-status-btn:hover,
.col-status-btn.active {
    background: rgba(137, 176, 205, 0.25);
}

/* Inline live-load indicator on the right of the trigger */
.trigger-progress {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
}
.trigger-progress-track {
    position: relative;
    display: inline-block;
    width: 50px;
    height: 5px;
    background: var(--border-light, #e9ecef);
    border-radius: 3px;
    overflow: hidden;
}
.trigger-progress-fill {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 0;
    background: #f0a500;
    transition: width 0.2s linear;
}
.trigger-progress-pct {
    color: var(--text-secondary, #888);
    min-width: 30px;
    text-align: right;
    font-variant-numeric: tabular-nums;
}

.col-status-summary {
    display: flex;
    align-items: center;
    gap: 2px;
    font-size: 11px;
    color: var(--text-secondary, #666);
}
.instance-count {
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    color: var(--text-primary, #444);
}
.separator {
    margin: 0 3px;
    color: #ccc;
}

/* ── Panel ───────────────────────────────────────────────────────────── */
.col-status-panel {
    position: fixed;
    z-index: 999;
    width: 250px;
    max-height: 400px;
    display: flex;
    flex-direction: column;
    background: var(--bg-primary, #fff);
    color: var(--text-primary, #333);
    border: 1px solid var(--border-color, #dee2e6);
    border-radius: 6px;
    overflow: hidden;
    font-size: 12px;
}

/* The panel renders in a context whose inherited color may be light; anchor the
   muted-label colour explicitly rather than relying on Bootstrap utilities. */
.col-status-panel .text-secondary {
    color: var(--text-secondary, #666) !important;
}

/* ── Loading now (merged from ColumnLoadProgress) ────────────────────── */
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

/* ── Column list ─────────────────────────────────────────────────────── */
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
