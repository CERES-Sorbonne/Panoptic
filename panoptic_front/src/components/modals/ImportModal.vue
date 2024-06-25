<script setup lang="ts">

import { apiConfirmImport, apiUploadPropertyCsv } from '@/data/api';
import { usePanopticStore } from '@/data/panopticStore';
import { useProjectStore } from '@/data/projectStore';
import Modal from './Modal.vue';
import PropertyIcon from '../properties/PropertyIcon.vue';
import { onMounted, ref } from 'vue';
import { ModalId } from '@/data/models';

const panoptic = usePanopticStore()
const project = useProjectStore()

// const properties = computed(() => panoptic.modalData as PropertyDescription[])
const inputElem = ref(null)
const filename = ref(null)
const properties = ref(null)
const take = ref({})
const loading = ref(false)
const fusion = ref('new')
const relative = ref(true)

async function importFile() {
    // console.log(importOptions.value)
    loading.value = true
    const exclude = Object.keys(properties.value.properties).filter(i => !take.value[i]).map(Number)
    const params = {
        fusion: fusion.value,
        properties: properties.value.properties,
        exclude: exclude,
        relative: relative.value
    }
    await apiConfirmImport(params)
    clear()
    panoptic.hideModal()
    project.reload()
}

async function uploadFile(e) {
    const file = e.target.files[0]
    if (file == undefined) return

    const res = await apiUploadPropertyCsv(file)
    filename.value = file.name
    properties.value = res
    Object.keys(properties.value.properties).forEach(k => take.value[k] = true)
}

function clear() {
    filename.value = null
    properties.value = null
    inputElem.value.value = null
    take.value = {}
    relative.value = true
    fusion.value = 'new'
    loading.value = false
}

</script>


<template>
    <Modal :id="ModalId.IMPORT" ref="modalElem">
        <template #title>
            {{ $t('modals.import.title') }}
        </template>
        <template #content>
            <div class="d-flex p-2">
                <div class="me-1">File</div>
                <input type="file" ref="inputElem" accept="text/csv" @change="uploadFile" hidden />
                <div v-if="filename" class="sbb" @click="clear">{{ filename }}</div>
                <div v-else class="sbc" @click="inputElem.click()">Upload <i class="bi bi-file-earmark-arrow-up" />
                </div>
            </div>
            <div v-if="filename" class="p-2">
                <table>
                    <tr>
                        <th class="border">Import</th>
                        <th class="border">Col</th>
                        <th class="border">Property</th>
                        <th class="border">Exist</th>
                        <th class="border">Mode</th>
                    </tr>

                    <tr v-for="p, i in properties.properties" class="border" :class="!take[i] ? 'dimmed' : ''">
                        <td class="border text-center"><input v-if="i != 0" type="checkbox" v-model="take[i]" /></td>
                        <td class="border text-center">{{ i }}</td>
                        <td class="border">
                            <PropertyIcon :type="p.type" /> {{ p.name }}
                        </td>
                        <td class="border text-center">
                            <div v-if="p.id > 0" class="exist"></div>
                        </td>
                        <td class="border">
                            <span v-if="p.id < 0">
                                <select id="base" name="base" v-model="p.mode" :disabled="!take[i]">
                                    <option value="sha1">Image</option>
                                    <option value="id">Instance</option>
                                </select>
                            </span>
                            <span v-else>
                                <span v-if="p.mode == 'id'">Instance</span>
                                <span v-if="p.mode == 'sha1'">Image</span>
                            </span>
                        </td>
                    </tr>
                    <tr v-if="properties.key == 'path'" >
                        <td colspan="3" class="pt-2">
                            <div class="d-flex">
                                <div class="me-1">Fusion Mode</div>
                                <select v-model="fusion" :disabled="loading">
                                    <option value="first">First</option>
                                    <option value="last">Last</option>
                                    <option value="new">New</option>
                                    <option value="all">All</option>
                                </select>
                            </div>
                        </td>
                        <td colspan="2" class="pt-2">
                            Relatif Path
                            <input type="checkbox" v-model="relative"/>
                        </td>
                    </tr>
                    <tr>
                        <td colspan="5" class="">
                            <div class="d-flex mt-2 flex-center w-100">
                                <div v-if="!loading" class="bbb text-center w-100" @click="importFile">Import
                                </div>
                                <div v-if="loading" class="text-center w-100 border rounded">
                                    <div class="spinner-border spinner-border-sm"
                                        style="position: relative; top: -1px" role="status">
                                    </div>
                                </div>
                            </div>
                        </td>
                    </tr>

                </table>

            </div>
        </template>
    </Modal>
</template>

<style scoped>
.exist {
    width: 10px;
    height: 10px;
    background-color: green;
    border-radius: 50%;
    display: inline-block;
}

.base-btn {
    /* border: 1px solid var(--border-color); */
    background-color: hsl(0, 0%, 95%);
}

.dimmed {
    background-color: rgb(214, 214, 214);
    color: grey;
}

td {
    padding: 2px 3px;
}

th {
    padding: 2px 3px;
}
</style>