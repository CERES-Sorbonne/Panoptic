<script setup lang="ts">

import { apiExportProperties } from '@/data/api';
import { usePanopticStore } from '@/data/panopticStore';
import { useProjectStore } from '@/data/projectStore';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';
import Modal from './Modal.vue';
import { ModalId } from '@/data/models';
import { sleep } from '@/utils/utils';

const panoptic = usePanopticStore()
const store = useProjectStore()

const state = reactive({
    name: undefined,
    mode: 'instance',
    selection: 'all',
    properties: 'all',
    exportImages: false
})

const modalElem = ref(null)
const isLoading = ref(false)

const selectedCount = computed(() => {
    const tabManager = store.getTabManager()
    return Object.keys(tabManager.collection.groupManager.selectedImages).length
})

const visibleCount = computed(() => {
    const tabManager = store.getTabManager()
    if (state.mode == 'instance') { return tabManager.getVisibleProperties().length }
    return tabManager.getVisibleSha1Properties().length
})

function exportFile() {
    let images
    let properties

    apiExportProperties(images, properties)
}

function getClass(value, test) {
    if (value == test) {
        return 'selected'
    }
    return ''
}

function set(target, value) {
    // console.log('set')
    state[target] = value
}

function clear() {
    Object.assign(state, {
        name: undefined,
        mode: 'instance',
        selection: 'all',
        properties: 'all',
        exportImages: false
    })
}

async function buildRequest() {
    const req = { exportImages: state.exportImages, properties: undefined, images: undefined, name: undefined }
    if (state.properties == 'all') {
        req.properties = store.propertyList.filter(p => p.id > 0).map(p => p.id)
    }
    if (state.properties == 'visible') {
        req.properties = store.getTabManager().getVisibleProperties().filter(p => p.id > 0).map(p => p.id)
    }
    if (state.name && state.name != '') {
        req.name = state.name
    }
    if (state.selection == 'selected') {
        req.images = Object.keys(store.getTabManager().collection.groupManager.selectedImages).map(Number)
    }
    if (state.selection == 'filtered') {
        req.images = store.getTabManager().collection.filterManager.result.images.map(i => i.id)
    }
    isLoading.value = true
    await sleep(100)
    await apiExportProperties(req.name, req.images, req.properties, req.exportImages)
    isLoading.value = false
    modalElem.value.hide()
}

</script>


<template>
    <Modal :id="ModalId.EXPORT" :max-height="300" :max-width="700" @show="clear" ref="modalElem">
        <template #title>
            {{ $t('modals.export.title') }}
        </template>
        <template #content>
            <div class="d-flex flex-column p-2" style="justify-content: center;">
                <table class="">
                    <!-- <tbody> -->
                    <tr class="option-row">
                        <td class="option-label">{{ $t('modals.export.name') }}</td>
                        <td class="ps-1"><input type="text" style="line-height: 20px;"
                                :placeholder="$t('modals.export.name_placeholder')" v-model="state.name" />
                        </td>
                    </tr>
                    <!-- <tr class="option-row">
                        <td class="option-label">{{ $t('modals.export.mode_label') }}</td>
                        <td class="d-flex options">
                            <div class="option flex-grow-1" :class="getClass(state.mode, 'image')"
                                @click="set('mode', 'image')">{{ $t('modals.export.mode_image') }}</div>
                            <div class="separator"></div>
                            <div class="option flex-grow-1" :class="getClass(state.mode, 'instance')"
                                @click="set('mode', 'instance')">{{ $t('modals.export.mode_instance') }}</div>
                        </td>

                    </tr> -->
                    <tr class="option-row">
                        <td class="option-label">{{ $t('modals.export.selection_label') }}</td>
                        <td class="d-flex options">
                            <div class="option flex-grow-1" :class="getClass(state.selection, 'all')"
                                @click="set('selection', 'all')">{{ $t('modals.export.selection_all') }}
                            </div>
                            <template v-if="selectedCount > 0">
                                <div class="separator"></div>
                                <div class="option flex-grow-1" :class="getClass(state.selection, 'selected')"
                                    @click="set('selection', 'selected')">{{ $t('modals.export.selection_selected') }} ({{
                                        selectedCount }})</div>
                            </template>
                            <div class="separator"></div>
                            <div class="option flex-grow-1" :class="getClass(state.selection, 'filtered')"
                                @click="set('selection', 'filtered')">{{ $t('modals.export.selection_filtered') }}</div>
                        </td>

                    </tr>
                    <tr class="option-row">
                        <td class="option-label">{{ $t('modals.export.properties_label') }}</td>
                        <td class="d-flex options">
                            <div class="option flex-grow-1" :class="getClass(state.properties, 'all')"
                                @click="set('properties', 'all')">{{ $t('modals.export.properties_all') }}</div>

                            <template v-if="visibleCount > 0">
                                <div class="separator"></div>
                                <div class="option flex-grow-1" :class="getClass(state.properties, 'visible')"
                                    @click="set('properties', 'visible')">{{ $t('modals.export.properties_visible') }} ({{
                                        visibleCount }})
                                </div>
                            </template>
                            <div class="separator"></div>
                            <div class="option flex-grow-1" :class="getClass(state.properties, 'none')"
                                @click="set('properties', 'none')">{{ $t('modals.export.properties_none') }}</div>
                        </td>
                    </tr>
                    <tr class="option-row">
                        <td class="option-label">{{ $t('modals.export.export_images') }}</td>
                        <td class="ps-1">
                            <input type="checkbox" v-model="state.exportImages" />
                        </td>
                    </tr>
                    <!-- </tbody> -->
                </table>
                <div class="mt-2 d-flex">
                    <span class="base-hover p-1 export-btn" @click="buildRequest">Export</span>
                    <div v-if="isLoading" class="ms-5 spinner-border" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>

            </div>
        </template>
    </Modal>
</template>

<style scoped>
.option-row {
    height: 40px !important;
    line-height: 20px !important;
    padding: 0 !important;
}

.option-label {
    background-color: white;
    margin-right: 2px;
}

.option {
    padding: 0 10px;
}

.options {
    margin-top: 6px;
    margin-left: 5px;
    padding: 0px 0px;
    text-align: center;
    border: 1px solid var(--border-color);
    border-radius: 5px;
}

.separator {
    border-left: 1px solid var(--border-color);
    /* margin: 0 10px; */
}

.selected {
    background-color: var(--tab-grey);
}

.export-btn {
    border: 1px solid var(--border-color);
}
</style>