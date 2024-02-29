<script setup lang="ts">

import { apiExportProperties, apiImportFile } from '@/data/api';
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

const properties = computed(() => panoptic.modalData as PropertyDescription[])
const ignore = ref({})

const importOptions = computed(() => {
    const res = {}
    properties.value.forEach(p => {
        if(p.col == 0) return
        if(p.id != undefined) return
        res[p.col] = {}
        if (ignore.value[p.col]) {
            res[p.col].ignored
            return
        }
        res[p.col].mode = p.mode
    })
    return res
})

async function importFile() {
    await apiImportFile(importOptions.value)
    panoptic.hideModal()
    store.reload()
}
</script>


<template>
    <Modal :id="ModalId.IMPORT" ref="modalElem">
        <template #title>
            {{ $t('modals.import.title') }}
        </template>
        <template #content>
            <div class="p-2">
                <table>
                    <tr>
                        <th class="border">Ignore</th>
                        <th class="border">Col</th>
                        <th class="border">Property</th>
                        <th class="border">Exist</th>
                        <th class="border">Mode</th>
                    </tr>

                    <tr v-for="p in properties" class="border" :class="ignore[p.col] ? 'dimmed' : ''">
                        <td class="border text-center"><input type="checkbox" v-model="ignore[p.col]" /></td>
                        <td class="border text-center">{{ p.col }}</td>
                        <td class="border">
                            <PropertyIcon :type="p.type" /> {{ p.name }}
                        </td>
                        <td class="border text-center">
                            <div v-if="p.id != null" class="exist"></div>
                        </td>
                        <td class="border">
                            <span v-if="p.id == null">
                                <select id="base" name="base" v-model="p.mode">
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
                <div class="d-flex mt-2">
                    <div class="base-btn" @click="importFile">Import</div>
                </div>

                {{ importOptions }}
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
    border: 1px solid var(--border-color);
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