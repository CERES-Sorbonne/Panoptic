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
                        <div v-if="page == ''" class="h-100 w-100">
                            <div class="d-flex flex-wrap h-100 justify-content-center">

                                <div class="bb align-self-center m-4" style="width: 120px;"
                                    @click="selectedPage = PAGE.Local">
                                    <div class="border rounded p-2 text-center">
                                        <div><i class="bi bi-folder" style="font-size: 50px;" /></div>
                                        <div>Local folder</div>
                                    </div>
                                </div>

                                <div class="bb align-self-center m-4" style="width: 120px;"
                                    @click="selectedPage = PAGE.Iiif">
                                    <div class="border rounded p-2 text-center">
                                        <div><i class="bi bi-globe2" style="font-size: 50px;" /></div>
                                        <div>IIIF</div>
                                    </div>
                                </div>
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
</style>
