<script setup lang="ts">
import { computed } from 'vue'
import { useColumnStore } from '@/data/columnStore'
import { useDataStore } from '@/data/dataStore'

const columnStore = useColumnStore()
const dataStore   = useDataStore()

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

// Other columns loading via requireFullColumn()
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

const showAny = computed(() => columnStore.baseProgress.loading || !!otherCurrent.value)
</script>

<template>
    <div v-if="showAny" class="col-progress-wrapper">
        <!-- Initial base load: id / sha1 / file as one combined bar -->
        <div v-if="columnStore.baseProgress.loading" class="col-progress-btn" title="Loading: id, sha1, file">
            <i class="bi bi-database-fill-gear me-1" />
            <span class="col-progress-name">id, sha1, file</span>
            <div class="col-progress-track">
                <div
                    class="col-progress-fill"
                    :style="{ width: (basePct ?? 0) + '%' }"
                />
            </div>
            <span v-if="basePct !== null" class="col-progress-pct">{{ basePct }}%</span>
        </div>

        <!-- Other columns loading one at a time -->
        <div v-if="otherCurrent" class="col-progress-btn" :title="`Loading: ${otherCurrent.name}`">
            <i class="bi bi-database-fill-gear me-1" />
            <span class="col-progress-name">{{ otherCurrent.name }}</span>
            <span v-if="otherRemaining > 1" class="col-progress-queue">+{{ otherRemaining - 1 }}</span>
            <div class="col-progress-track">
                <div
                    class="col-progress-fill"
                    :style="{ width: (otherPct ?? 0) + '%' }"
                />
            </div>
            <span v-if="otherPct !== null" class="col-progress-pct">{{ otherPct }}%</span>
        </div>
    </div>
</template>

<style scoped>
.col-progress-wrapper {
    display: flex;
    gap: 6px;
}

.col-progress-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 3px 7px;
    border: 1px solid var(--border-color, #dee2e6);
    border-radius: 5px;
    font-size: 12px;
    color: var(--text-color, #444);
    white-space: nowrap;
}

.col-progress-name {
    font-size: 11px;
    color: #666;
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
}

.col-progress-queue {
    font-size: 10px;
    color: #aaa;
}

.col-progress-track {
    position: relative;
    width: 60px;
    height: 5px;
    background: #e9ecef;
    border-radius: 3px;
    overflow: hidden;
}

.col-progress-fill {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 0;
    background: #f0a500;
    transition: width 0.2s linear;
}

.col-progress-pct {
    font-size: 10px;
    color: #888;
    min-width: 28px;
    text-align: right;
}
</style>
