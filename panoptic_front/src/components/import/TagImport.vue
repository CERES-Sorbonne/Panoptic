<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useDataStore } from '@/data/stores/dataStore';
import { usePanopticStore } from '@/data/stores/panopticStore';
import { ModalId, Property, PropertyType } from '@/data/models';
import PropertyDropdown from '../properties/PropertyDropdown.vue';
import CsvDropZone from './CsvDropZone.vue';
import { apiUploadTagsCsv } from '@/data/api/projectApi';

const data = useDataStore()
const panoptic = usePanopticStore()
const { t } = useI18n()

const tagTypes = [PropertyType.tag, PropertyType.multi_tags]
const helpExample = 'Animal;3;\nDog;5;Animal\nPuppy;;Dog,Pet'

const selectedFile = ref<File | null>(null)
const selectedProperty = ref<Property | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

const isPropertyValid = computed(() => {
    if (!selectedProperty.value) return false
    return tagTypes.includes(selectedProperty.value.type)
})

const canImport = computed(() => {
    return selectedFile.value && isPropertyValid.value && !loading.value
})

function setFile(file: File | null) {
    selectedFile.value = file
    error.value = null
}

function initValues() {
    // Pre-select the first tag property
    selectedProperty.value = data.propertyList.find(p => tagTypes.includes(p.type)) ?? null
}

async function triggerImport() {
    if (!canImport.value) return

    loading.value = true
    error.value = null

    try {
        await apiUploadTagsCsv(selectedFile.value, selectedProperty.value.id)
        panoptic.hideModal(ModalId.IMPORT)
    } catch (e) {
        console.error(e)
        error.value = t('modals.import.import_failed')
    } finally {
        loading.value = false
    }
}

onMounted(initValues)
</script>

<template>
    <div class="import-page">
        <div class="import-body">

            <div class="field">
                <div class="field-label">{{ $t('modals.import.file') }}</div>
                <CsvDropZone :file="selectedFile" @update:file="setFile" />
            </div>

            <div class="field">
                <div class="field-label">{{ $t('modals.import.target_property') }}</div>
                <div class="property-picker">
                    <PropertyDropdown v-model="selectedProperty" :acceptable-types="tagTypes" />
                </div>
                <div v-if="selectedProperty && !isPropertyValid" class="invalid">
                    <i class="bi bi-exclamation-triangle me-1" />{{ $t('modals.import.invalid_type') }}
                </div>
                <div v-else class="field-hint">{{ $t('modals.import.target_property_hint') }}</div>
            </div>

            <div v-if="!selectedFile" class="field">
                <div class="field-label">{{ $t('modals.import.format') }}</div>
                <div class="help-card">
                    <div>{{ $t('modals.import.tags_help.intro') }}</div>
                    <ul>
                        <li><code>name</code> {{ $t('modals.import.tags_help.name') }}</li>
                        <li><code>color</code> {{ $t('modals.import.tags_help.color') }}</li>
                        <li><code>parents</code> {{ $t('modals.import.tags_help.parents') }}</li>
                    </ul>
                    <pre class="help-example">{{ helpExample }}</pre>
                </div>
            </div>

            <div v-if="error" class="callout ko">
                <i class="bi bi-exclamation-triangle callout-icon" />
                <div class="callout-body">
                    <div class="callout-title">{{ error }}</div>
                </div>
            </div>

        </div>

        <div class="import-footer">
            <div class="btn-action primary" :class="{ disabled: !canImport }" @click="triggerImport">
                <span v-if="loading" class="spinner-border spinner-border-sm" role="status" />
                <i v-else class="bi bi-tags" />
                {{ $t('modals.import.import_tags') }}
            </div>
        </div>
    </div>
</template>

<style scoped>
.property-picker {
    display: flex;
}

/* Restyle PropertyDropdown's trigger as a form input */
.property-picker :deep(.sbb) {
    min-width: 220px;
    padding: 5px 10px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    background-color: var(--bg-primary);
}

.property-picker :deep(.sbb:hover) {
    border-color: var(--primary);
}

.invalid {
    font-size: 11px;
    color: var(--error);
}
</style>
