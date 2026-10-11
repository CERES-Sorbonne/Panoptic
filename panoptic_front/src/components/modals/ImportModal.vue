<script setup lang="ts">
import { ModalId } from '@/data/models';
import { ref } from 'vue';
import Modal2 from './Modal2.vue';
import DataImport from '../import/DataImport.vue';
import TagImport from '../import/TagImport.vue';

enum PAGE {
    Data = 'data',
    Tags = 'tags',
}

const pages = [
    { id: PAGE.Data, icon: 'bi-file-earmark-spreadsheet' },
    { id: PAGE.Tags, icon: 'bi-tags' },
]

// Modal2 unmounts its content on hide, so the import pages start fresh on every open.
const selectedPage = ref(PAGE.Data)
</script>

<template>
    <Modal2 :id="ModalId.IMPORT" :max-width="640" :max-height="720">
        <template #title>
            <div class="modal-title">
                <i class="bi bi-box-arrow-in-down me-2" />{{ $t('modals.import.title') }}
            </div>
        </template>
        <template #content>
            <div class="import-modal">
                <div class="import-tabs">
                    <div class="segmented">
                        <div v-for="p in pages" :key="p.id" class="segment"
                            :class="{ selected: selectedPage == p.id }" @click="selectedPage = p.id">
                            <i class="bi" :class="p.icon" />
                            {{ $t('modals.import.' + p.id) }}
                        </div>
                    </div>
                </div>
                <DataImport v-if="selectedPage == PAGE.Data" />
                <TagImport v-else />
            </div>
        </template>
    </Modal2>
</template>

<style scoped>
.modal-title {
    padding: 2px 6px;
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.import-tabs {
    flex: none;
    padding: 12px 16px 0 16px;
}
</style>

<!-- Shared by DataImport and TagImport, which render inside .import-modal. -->
<style>
.import-modal {
    display: flex;
    flex-direction: column;
    height: 100%;
    font-size: 13px;
    color: var(--text-primary);
}

.import-modal .import-page {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
}

.import-modal .import-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

/* --- generic field --- */
.import-modal .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.import-modal .field-label {
    font-size: 11px;
    font-weight: var(--font-weight-semibold);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-secondary);
}

.import-modal .field-hint {
    font-size: 11px;
    color: var(--text-tertiary);
}

.import-modal .label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}

.import-modal .count {
    font-size: 11px;
    color: var(--text-tertiary);
}

.import-modal .checkbox {
    flex: none;
    width: 13px;
    height: 13px;
    margin: 0;
    accent-color: var(--primary);
    cursor: pointer;
}

.import-modal code {
    padding: 0 4px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-primary);
    background-color: var(--bg-tertiary);
    border-radius: 3px;
}

/* --- segmented control --- */
.import-modal .segmented {
    display: flex;
    gap: 2px;
    padding: 2px;
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
}

.import-modal .segment {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 4px 8px;
    border-radius: 3px;
    color: var(--text-secondary);
    text-align: center;
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
    transition: background-color var(--transition-fast), color var(--transition-fast);
}

.import-modal .segment:hover {
    color: var(--text-primary);
    background-color: var(--hover-bg);
}

.import-modal .segment.selected {
    color: var(--text-primary);
    font-weight: var(--font-weight-medium);
    background-color: var(--bg-primary);
    box-shadow: var(--shadow-sm);
}

/* --- switch row --- */
.import-modal .switch-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 10px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
}

.import-modal .switch-row:hover {
    background-color: var(--bg-secondary);
}

.import-modal .switch {
    position: relative;
    flex: none;
    width: 32px;
    height: 18px;
    margin: 0;
    appearance: none;
    -webkit-appearance: none;
    background-color: var(--border-color);
    border-radius: 9px;
    cursor: pointer;
    transition: background-color var(--transition-fast);
}

.import-modal .switch::after {
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 14px;
    height: 14px;
    background-color: #ffffff;
    border-radius: 50%;
    box-shadow: var(--shadow-sm);
    transition: transform var(--transition-fast);
}

.import-modal .switch:checked {
    background-color: var(--primary);
}

.import-modal .switch:checked::after {
    transform: translateX(14px);
}

/* --- format help --- */
.import-modal .help-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    color: var(--text-secondary);
    line-height: var(--line-height-normal);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-sm);
}

.import-modal .help-card ul {
    margin: 0;
    padding-left: 18px;
}

.import-modal .help-example {
    margin: 0;
    padding: 8px 10px;
    font-family: var(--font-mono);
    font-size: 11px;
    line-height: 1.6;
    color: var(--text-primary);
    background-color: var(--bg-secondary);
    border-radius: var(--radius-sm);
    white-space: pre;
    overflow-x: auto;
}

/* --- callouts (errors, warnings) --- */
.import-modal .callout {
    display: flex;
    gap: 8px;
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-left-width: 3px;
    border-radius: var(--radius-sm);
    background-color: var(--bg-secondary);
}

.import-modal .callout.ko {
    border-left-color: var(--error);
}

.import-modal .callout.warn {
    border-left-color: var(--accent-orange);
}

.import-modal .callout-icon {
    line-height: 1.4;
}

.import-modal .callout.ko .callout-icon {
    color: var(--error);
}

.import-modal .callout.warn .callout-icon {
    color: var(--accent-orange);
}

.import-modal .callout-body {
    flex: 1;
    min-width: 0;
}

.import-modal .callout-title {
    font-weight: var(--font-weight-semibold);
}

.import-modal .callout-line {
    margin-top: 2px;
    font-size: 12px;
    color: var(--text-secondary);
}

/* --- footer --- */
.import-modal .import-footer {
    flex: none;
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 10px 16px;
    background-color: var(--bg-secondary);
    border-top: 1px solid var(--island-border);
}

.import-modal .btn-action {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 16px;
    font-weight: var(--font-weight-medium);
    color: var(--text-primary);
    background-color: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
    user-select: none;
    transition: background-color var(--transition-fast), border-color var(--transition-fast);
}

.import-modal .btn-action:hover {
    background-color: var(--hover-bg);
}

.import-modal .btn-action.primary {
    color: var(--text-inverse);
    background-color: var(--primary);
    border-color: var(--primary);
}

.import-modal .btn-action.primary:hover {
    background-color: var(--primary-dark);
    border-color: var(--primary-dark);
}

.import-modal .btn-action.disabled {
    opacity: 0.5;
    pointer-events: none;
}
</style>
