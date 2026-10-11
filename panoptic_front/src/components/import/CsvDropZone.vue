<script setup lang="ts">
import { ref } from 'vue';

const props = defineProps<{
    file: File | null
    loading?: boolean
}>()
const emits = defineEmits<{
    (e: 'update:file', file: File | null): void
}>()

const inputElem = ref<HTMLInputElement | null>(null)
const dragging = ref(false)

function pick(file: File | undefined) {
    if (!file) return
    emits('update:file', file)
}

function onChange(e: Event) {
    pick((e.target as HTMLInputElement).files?.[0])
}

function onDrop(e: DragEvent) {
    dragging.value = false
    pick(e.dataTransfer?.files?.[0])
}

function clear() {
    if (inputElem.value) inputElem.value.value = ''
    emits('update:file', null)
}

function formatSize(bytes: number) {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}
</script>

<template>
    <input type="file" ref="inputElem" accept=".csv,text/csv" @change="onChange" hidden />

    <div v-if="!props.file" class="drop-zone" :class="{ dragging }" @click="inputElem?.click()"
        @dragover.prevent="dragging = true" @dragleave="dragging = false" @drop.prevent="onDrop">
        <i class="bi bi-file-earmark-arrow-up drop-icon" />
        <div class="drop-label">{{ $t('modals.import.drop') }}</div>
        <div class="drop-hint">{{ $t('modals.import.drop_hint') }}</div>
    </div>

    <div v-else class="file-chip">
        <i class="bi bi-file-earmark-spreadsheet file-icon" />
        <div class="file-text">
            <div class="file-name">{{ props.file.name }}</div>
            <div class="file-meta num">
                {{ formatSize(props.file.size) }}
                <slot name="meta" />
            </div>
        </div>
        <span v-if="props.loading" class="spinner-border spinner-border-sm file-spinner" role="status" />
        <div v-else class="file-clear bi bi-x-lg" @click="clear" />
    </div>
</template>

<style scoped>
.drop-zone {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 22px 16px;
    color: var(--text-secondary);
    background-color: var(--bg-secondary);
    border: 1px dashed var(--border-color);
    border-radius: var(--radius-md);
    text-align: center;
    cursor: pointer;
    user-select: none;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
}

.drop-zone:hover,
.drop-zone.dragging {
    color: var(--primary);
    background-color: var(--primary-light);
    border-color: var(--primary);
}

.drop-icon {
    font-size: 28px;
    line-height: 1;
    margin-bottom: 4px;
}

.drop-label {
    font-weight: var(--font-weight-medium);
}

.drop-hint {
    font-size: 11px;
    color: var(--text-tertiary);
}

.file-chip {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    background-color: var(--bg-secondary);
}

.file-icon {
    flex: none;
    font-size: 20px;
    color: var(--success);
}

.file-text {
    flex: 1;
    min-width: 0;
}

.file-name {
    font-weight: var(--font-weight-medium);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.file-meta {
    display: flex;
    gap: 8px;
    font-size: 11px;
    color: var(--text-tertiary);
}

.file-clear {
    flex: none;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    font-size: 12px;
    color: var(--text-secondary);
    border-radius: var(--radius-sm);
    cursor: pointer;
}

.file-clear:hover {
    color: var(--error);
    background-color: var(--bg-tertiary);
}

.file-spinner {
    flex: none;
    color: var(--text-secondary);
}
</style>
