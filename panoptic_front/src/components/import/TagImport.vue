<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useDataStore } from '@/data/dataStore';
import { usePanopticStore } from '@/data/panopticStore';
import { ModalId, Property, PropertyType } from '@/data/models';
import PropertyDropdown from '../properties/PropertyDropdown.vue'; // Using your existing component
import wTT from '@/components/tooltips/withToolTip.vue'; // Using the tooltip wrapper
import { apiUploadTagsCsv } from '@/data/apiProjectRoutes';

// Placeholder API import
// import { apiImportTags } from '@/data/apiProjectRoutes'; 

const data = useDataStore()
const panoptic = usePanopticStore()

const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const selectedProperty = ref<Property | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

// --- File Handling Logic ---

function onFileChange(event: Event) {
    const target = event.target as HTMLInputElement
    if (target.files && target.files.length > 0) {
        selectedFile.value = target.files[0]
        error.value = null
    }
}

function clearFile() {
    selectedFile.value = null
    if (fileInput.value) {
        fileInput.value.value = ''
    }
}

// --- Property Logic (Adapted from your example) ---

const hasProperties = computed(() => data.propertyList.length > 0)

// Check if the selected property is valid for tag import
const isPropertyValid = computed(() => {
    if (!selectedProperty.value) return false
    return ['tag', 'multi_tags'].includes(selectedProperty.value.type)
})

function initValues() {
    // Try to find the first tag/multi_tags property to pre-select
    const validProps = data.propertyList.filter(p => ['tag', 'multi_tags'].includes(p.type))

    if (validProps.length > 0) {
        selectedProperty.value = validProps[0]
    } else if (data.propertyList.length > 0) {
        // Fallback to first property if no tags found (user will see validation error)
        selectedProperty.value = data.propertyList[0]
    }
}

// --- Import Logic ---

const canImport = computed(() => {
    return selectedFile.value && selectedProperty.value && isPropertyValid.value && !loading.value
})

async function triggerImport() {
    if (!canImport.value) return

    loading.value = true
    error.value = null

    try {
        await apiUploadTagsCsv(selectedFile.value, selectedProperty.value.id)
        panoptic.hideModal(ModalId.IMPORT)
        clearFile()
    } catch (e) {
        console.error(e)
        error.value = "Import failed."
    } finally {
        loading.value = false
    }
}

onMounted(initValues)

</script>

<template>
    <div class="h-100 d-flex flex-column p-4" style="max-width: 600px; margin: 0 auto;">

        <div class="mb-4">
            <div class="d-flex align-items-center">
                <input type="file" ref="fileInput" accept=".csv" @change="onFileChange" hidden />

                <div v-if="!selectedFile" class="sbc w-100 text-center p-2" @click="fileInput?.click()">
                    {{ $t('modals.import.upload_file') }}
                    <i class="bi bi-file-earmark-arrow-up ms-2" />
                </div>

                <div v-else class="sbb w-100 d-flex justify-content-between align-items-center p-2" @click="clearFile">
                    <span>{{ selectedFile.name }}</span>
                    <i class="bi bi-x-lg text-danger" />
                </div>
            </div>
        </div>

        <div v-if="selectedFile" class="mb-4">
            <label class="form-label fw-bold">{{ $t('modals.import.target_property') }}</label>


            <div class="d-flex">
                <PropertyDropdown v-model="selectedProperty"
                    :acceptable-types="[PropertyType.tag, PropertyType.multi_tags]" />

            </div>

            <div v-if="selectedProperty && !isPropertyValid" class="text-danger small mt-2">
                <i class="bi bi-exclamation-triangle me-1"></i>
                {{ $t('modals.import.invalid_type') || 'Selected property must be of type Tag or Multi-Tags.' }}
            </div>
        </div>

        <div v-if="error" class="alert alert-danger py-2 mb-3">
            {{ error }}
        </div>

        <div class="">
            <div class="d-flex justify-content-center">
                <button class="bbb w-50 text-center p-2" :class="{ 'disabled': !canImport }" @click="triggerImport">
                    <span v-if="loading" class="spinner-border spinner-border-sm me-2" role="status"></span>
                    {{ $t('modals.import.import_tags') }}
                </button>
            </div>
        </div>

    </div>
</template>

<style scoped>
.disabled {
    pointer-events: none;
    opacity: 0.7;
}
</style>