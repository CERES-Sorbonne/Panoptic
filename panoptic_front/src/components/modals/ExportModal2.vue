<script setup lang="ts">

import { apiExportProperties } from '@/data/api';
import { useProjectStore } from '@/data/projectStore';
import { ref, computed, reactive } from 'vue';
import Modal from './Modal.vue';
import { ModalId, PropertyID } from '@/data/models';
import { sleep } from '@/utils/utils';
import PropertyIcon from '../properties/PropertyIcon.vue';
import { useDataStore } from '@/data/dataStore';

const project = useProjectStore()
const data = useDataStore()

const state = reactive({
    name: undefined,
    mode: 'instance',
    selection: 'all',
    key: 'id',
    properties: {},
    exportImages: false
})

const modalElem = ref(null)
const isLoading = ref(false)

const all = computed(() => properties.value.every(p => state.properties[p.id]))
const properties = computed(() => {
    const tmp = Object.values(data.properties)
    tmp.sort((a, b) => a.id - b.id)
    const res = []
    const computed = tmp.filter(p => p.id < 0)
    const personal = tmp.filter(p => p.id > 0)

    return [computed.pop(), ...personal, ...computed]
})

const selectedCount = computed(() => {
    const tabManager = project.getTabManager()
    return Object.keys(tabManager.collection.groupManager.selectedImages.value).length
})

const visibleCount = computed(() => {
    const tabManager = project.getTabManager()
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

function toggleAll() {
    if (all.value) {
        properties.value.forEach(p => {
            // if(p.id == PropertyID.id) return
            delete state.properties[p.id]
        })
    }
    else {
        properties.value.forEach(p => state.properties[p.id] = true)
    }
}

function clear() {
    Object.assign(state, {
        name: undefined,
        mode: 'instance',
        selection: 'all',
        key: 'id',
        properties: {},
        exportImages: false
    })
}

function show() {
    clear()
    const properties = project.getTabManager().getVisibleProperties()
    properties.forEach(p => state.properties[p.id] = true)
    // state.properties[-1] = true
}

async function buildRequest() {
    const req = { exportImages: state.exportImages, properties: undefined, images: undefined, name: undefined, key: 'id' }
    req.properties = Object.keys(state.properties).map(Number).filter(k => state.properties[k])
    req.properties.sort((a, b) => properties.value.findIndex(p => p.id == a) - properties.value.findIndex(p => p.id == b))
    if (state.name && state.name != '') {
        req.name = state.name
    }
    if (state.selection == 'selected') {
        req.images = Object.keys(project.getTabManager().collection.groupManager.selectedImages.value).map(Number)
    }
    if (state.selection == 'filtered') {
        req.images = project.getTabManager().collection.filterManager.result.images.map(i => i.id)
    }
    req.key = state.key
    isLoading.value = true
    await sleep(100)
    console.log(req)
    await apiExportProperties(req.name, req.images, req.key, req.properties, req.exportImages)
    isLoading.value = false
    modalElem.value.hide()
}

</script>


<template>
    <Modal :id="ModalId.EXPORT" @show="show" ref="modalElem">
        <template #title>
            {{ $t('modals.export.title') }}
        </template>
        <template #content>
            <div class="d-flex flex-column p-2">
                <div>
                    <table class="main-table">
                        <tbody>
                            <tr class="">
                                <td class="option-label">{{ $t('modals.export.name') }}</td>
                                <td class="ps-1"><input type="text" style="line-height: 20px;"
                                        :placeholder="$t('modals.export.name_placeholder')" v-model="state.name" />
                                </td>
                            </tr>
                            <tr class="option-row">
                                <td class="option-label">{{ $t('modals.export.selection_label') }}</td>
                                <td class="d-flex options">
                                    <div class="option flex-grow-1" :class="getClass(state.selection, 'all')"
                                        @click="set('selection', 'all')">{{ $t('modals.export.selection_all') }}
                                    </div>
                                    <template v-if="selectedCount > 0">
                                        <div class="separator"></div>
                                        <div class="option flex-grow-1" :class="getClass(state.selection, 'selected')"
                                            @click="set('selection', 'selected')">{{
                                                $t('modals.export.selection_selected')
                                            }}
                                            ({{
                                                selectedCount }})</div>
                                    </template>
                                    <div class="separator"></div>
                                    <div class="option flex-grow-1" :class="getClass(state.selection, 'filtered')"
                                        @click="set('selection', 'filtered')">{{
                                            $t('modals.export.selection_filtered') }}</div>
                                </td>

                            </tr>
                            <tr class="option-row">
                                <td class="option-label">{{ $t('modals.export.key_label') }}</td>
                                <td class="d-flex options">
                                    <div class="option flex-grow-1" :class="getClass(state.key, 'id')"
                                        @click="set('key', 'id')">
                                        {{ $t('modals.export.id') }}
                                    </div>
                                    <div class="separator"></div>
                                    <div class="option flex-grow-1" :class="getClass(state.key, 'local_path')"
                                        @click="set('key', 'local_path')">
                                        {{ $t('modals.export.local_path') }}
                                    </div>
                                    <div class="separator"></div>
                                    <div class="option flex-grow-1" :class="getClass(state.key, 'global_path')"
                                        @click="set('key', 'global_path')">
                                        {{ $t('modals.export.global_path') }}
                                    </div>
                                </td>

                            </tr>
                            <tr class="option-row">
                                <td class="option-label">{{ $t('modals.export.properties_label') }}</td>
                                <td>
                                    <table>
                                        <tbody>
                                            <tr>
                                                <td class="text-center"><input type="checkbox" :checked="all"
                                                        @input="toggleAll" /></td>
                                                <td>All</td>
                                            </tr>
                                            <tr v-for="p in properties" class="property-table">
                                                <td class="text-center"><input type="checkbox"
                                                        v-model="state.properties[p.id]" /> </td>
                                                <td>
                                                    <PropertyIcon :type="p.type" class="me-1" />{{ p.name }}
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </td>
                            </tr>
                            <tr class="option-row">
                                <td class="option-label">{{ $t('modals.export.export_images') }}</td>
                                <td class="ps-1">
                                    <input type="checkbox" v-model="state.exportImages" />
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>

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
.option-label {
    background-color: white;
    margin-right: 2px;
}

.option {
    padding: 0 10px;
    cursor: pointer;
}

.main-table {
    border-collapse: separate;
    border-spacing: 8px;
}

.options {
    padding: 0px 0px;
    text-align: center;
    border: 1px solid var(--border-color);
    border-radius: 3px;
}

td {
    vertical-align: top;
}

.property-table td {
    border: 1px solid var(--border-color);
    padding: 3px 6px;
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