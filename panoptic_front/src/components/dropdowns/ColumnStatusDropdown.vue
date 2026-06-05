<script setup lang="ts">
import { computed, ref } from 'vue'
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

const instanceCount = computed(() => columnStore.instanceCount)

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
        <button class="col-status-btn" :class="{ active: open }" @click="open = !open" title="Column status">
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
        </button>

        <!-- Panel -->
        <div v-if="open" class="col-status-panel shadow-sm">
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
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 3px 7px;
    border: 1px solid var(--border-color, #dee2e6);
    border-radius: 5px;
    background: transparent;
    cursor: pointer;
    font-size: 12px;
    color: var(--text-color, #444);
    white-space: nowrap;
    transition: background 0.15s;
}
.col-status-btn:hover,
.col-status-btn.active {
    background: rgba(137, 176, 205, 0.25);
}

.col-status-summary {
    display: flex;
    align-items: center;
    gap: 2px;
    font-size: 11px;
    color: #666;
}
.instance-count {
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    color: #444;
}
.separator {
    margin: 0 3px;
    color: #ccc;
}

/* ── Panel ───────────────────────────────────────────────────────────── */
.col-status-panel {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    z-index: 999;
    width: 250px;
    max-height: 400px;
    display: flex;
    flex-direction: column;
    background: var(--bg-color, #fff);
    border: 1px solid var(--border-color, #dee2e6);
    border-radius: 6px;
    overflow: hidden;
    font-size: 12px;
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
    color: var(--text-color, #333);
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
