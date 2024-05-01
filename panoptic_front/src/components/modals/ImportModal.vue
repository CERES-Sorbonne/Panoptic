<script setup lang="ts">

import { apiExportProperties, apiImportFile, apiUploadPropertyCsv } from '@/data/api';
import { usePanopticStore } from '@/data/panopticStore';
import { useProjectStore } from '@/data/projectStore';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';
import Modal from './Modal.vue';
import { ModalId, PropertyDescription } from '@/data/models';
import { sleep } from '@/utils/utils';
import PropertyIcon from '../properties/PropertyIcon.vue';

const panoptic = usePanopticStore()
const store = useProjectStore()

// const properties = computed(() => panoptic.modalData as PropertyDescription[])
const inputElem = ref(null)
const filename = ref(null)
const properties = ref([])
const take = ref({})
const loading = ref(false)

const importOptions = computed(() => {
    const res = {}
    console.log(properties.value)
    const taken = take.value
    properties.value.forEach(p => {
        res[p.col] = {}
        if(!taken[p.col]) {
            res[p.col].ignored = true
        }
        else if(p.id == null) {
            res[p.col].mode = p.mode
        }
    })
    delete res[0]
    return res
})

async function importFile() {
    console.log(importOptions.value)
    loading.value = true
    await apiImportFile(importOptions.value)
    panoptic.hideModal()
    store.reload()
}

async function uploadFile(e) {
    const file = e.target.files[0]
    if (file == undefined) return

    const res = await apiUploadPropertyCsv(file)
    filename.value = file.name
    properties.value = res
    properties.value.forEach(p => take.value[p.col] = true)
}

function clear() {
    filename.value = null
    properties.value = []
    inputElem.value.value = null
    take.value = {}
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
                <div v-else class="sbc" @click="inputElem.click()">Upload <i class="bi bi-file-earmark-arrow-up" /></div>
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

                    <tr v-for="p, i in properties" class="border" :class="!take[p.col] ? 'dimmed' : ''">
                        <td class="border text-center"><input v-if="i != 0" type="checkbox" v-model="take[p.col]" /></td>
                        <td class="border text-center">{{ p.col }}</td>
                        <td class="border">
                            <PropertyIcon :type="p.type" /> {{ p.name }}
                        </td>
                        <td class="border text-center">
                            <div v-if="p.id != null" class="exist"></div>
                        </td>
                        <td class="border">
                            <span v-if="p.id == null">
                                <select id="base" name="base" v-model="p.mode" :disabled="!take[p.col]">
                                    <option value="sha1">Image</option>
                                    <option value="id">Instance</option>
                                    <!-- Add more options as needed -->
                                </select>
                            </span>
                            <span v-else>
                                <span v-if="p.mode == 'id'">Instance</span>
                                <span v-if="p.mode == 'sha1'">Image</span>
                            </span>
                        </td>
                    </tr>
                </table>
                <div class="d-flex mt-2 flex-center">
                    <div v-if="!loading" class="bbb" @click="importFile">Import</div>
                    <div v-if="loading" class="spinner-border spinner-border-sm" style="position: relative; top: -1px" role="status">
                    </div>
                </div>
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