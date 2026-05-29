<script setup lang="ts">
import { computed } from 'vue'
import { useColumnStore } from '@/data/columnStore'
import { useDataStore } from '@/data/dataStore'

const columnStore = useColumnStore()
const dataStore   = useDataStore()

const loadingColumns = computed(() =>
    Object.entries(columnStore.fullColumnStatus)
        .filter(([, s]) => s === 'loading')
        .map(([idStr]) => {
            const id = Number(idStr)
            return { id, name: dataStore.properties[id]?.name ?? `#${id}` }
        })
)

const current = computed(() => loadingColumns.value[0] ?? null)
const remaining = computed(() => loadingColumns.value.length)
</script>

<template>
    <div v-if="current" class="col-progress-btn" :title="`Loading: ${current.name}`">
        <i class="bi bi-database-fill-gear me-1" />
        <span class="col-progress-name">{{ current.name }}</span>
        <span v-if="remaining > 1" class="col-progress-queue">+{{ remaining - 1 }}</span>
        <div class="col-progress-track">
            <div class="col-progress-fill" />
        </div>
    </div>
</template>

<style scoped>
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
    width: 60px;
    height: 5px;
    background: #e9ecef;
    border-radius: 3px;
    overflow: hidden;
}

.col-progress-fill {
    height: 100%;
    width: 40%;
    background: #f0a500;
    border-radius: 3px;
    animation: indeterminate 1.2s ease-in-out infinite;
}

@keyframes indeterminate {
    0%   { transform: translateX(-100%); }
    100% { transform: translateX(350%); }
}
</style>
