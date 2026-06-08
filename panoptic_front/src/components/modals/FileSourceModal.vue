<script setup lang="ts">
import { ModalId } from '@/data/models';
import { ref } from 'vue';
import Modal2 from './Modal2.vue';
import PageWindow from '../utils/PageWindow.vue';
import FileExplorer from './FileExplorer.vue';
import { useDataStore } from '@/data/dataStore';
import { usePanopticStore } from '@/data/panopticStore';

const data = useDataStore()
const panoptic = usePanopticStore()

enum PAGE {
    Local = 'local',
    Iiif = 'iiif',
}

const options = ref(Object.values(PAGE))
const selectedPage = ref('')

const iiifUrl = ref('')
const iiifSubmitting = ref(false)

function close() {
    panoptic.hideModal(ModalId.FILESOURCE)
    selectedPage.value = ''
    iiifUrl.value = ''
    iiifSubmitting.value = false
}

// Local folder import — reuse the existing FileExplorer (emits the chosen path).
async function selectLocalFolder(path: string) {
    if (!path) return
    await data.addFolder(path)
    close()
}

// IIIF import — send the manifest/collection URL to the backend.
async function importIiif() {
    const url = iiifUrl.value.trim()
    if (!url || iiifSubmitting.value) return
    iiifSubmitting.value = true
    try {
        await data.importIiif(url)
        close()
    } finally {
        iiifSubmitting.value = false
    }
}
</script>

<template>
    <Modal2 :id="ModalId.FILESOURCE">
        <template #title>
            Add file source
        </template>
        <template #content>
            <div class="h-100 overflow-hidden">
                <PageWindow :options="options" v-model:page="selectedPage">

                    <template #default="{ page }">
                        <!-- Home: choose the source type -->
                        <div v-if="page == ''" class="source-home">
                            <div class="source-card" @click="selectedPage = PAGE.Local">
                                <i class="bi bi-folder source-icon" />
                                <div class="source-label">Local folder</div>
                            </div>
                            <div class="source-card" @click="selectedPage = PAGE.Iiif">
                                <i class="bi bi-globe2 source-icon" />
                                <div class="source-label">IIIF</div>
                            </div>
                        </div>

                        <!-- Local folder: reuse the file explorer from the import modal -->
                        <FileExplorer v-if="page == PAGE.Local" mode="images" @select="selectLocalFolder" />

                        <!-- IIIF: manifest / collection URL -->
                        <div v-if="page == PAGE.Iiif" class="p-4">
                            <label class="form-label">IIIF Manifest or Collection URL</label>
                            <input v-model="iiifUrl" type="url" class="form-control"
                                placeholder="https://.../manifest.json"
                                @keydown.enter="importIiif" />
                            <div class="text-secondary mt-2" style="font-size: 12px;">
                                Paste a IIIF Presentation API manifest or collection URL (v2 or v3).
                            </div>
                            <div class="d-flex justify-content-end mt-3">
                                <button class="btn btn-primary" :disabled="!iiifUrl.trim() || iiifSubmitting"
                                    @click="importIiif">
                                    <span v-if="iiifSubmitting" class="spinner-border spinner-border-sm me-1"
                                        role="status" />
                                    Import
                                </button>
                            </div>
                        </div>

                    </template>
                </PageWindow>
            </div>
        </template>
    </Modal2>
</template>

<style scoped>
.source-home {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-lg);
    height: 100%;
}

.source-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-sm);
    width: 140px;
    height: 140px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    background-color: var(--bg-secondary);
    color: var(--text-secondary);
    cursor: pointer;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
}

.source-card:hover {
    background-color: var(--primary-light);
    border-color: var(--primary);
    color: var(--primary);
}

.source-icon {
    font-size: 46px;
}

.source-label {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
}
</style>
