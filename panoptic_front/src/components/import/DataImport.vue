<script setup lang="ts">
import { usePanopticStore } from '@/data/panopticStore';
import PropertyIcon from '../properties/PropertyIcon.vue';
import { computed, Ref, ref, watch } from 'vue';
import { ModalId, UploadConfirm } from '@/data/models';
import { useDataStore } from '@/data/dataStore';
import wTT from '@/components/tooltips/withToolTip.vue'
import FusionModeDropdown from '../dropdowns/FusionModeDropdown.vue';
import { objValues } from '@/utils/utils';
import { apiParseImport, apiConfirmImport, apiUploadPropertyCsv } from '@/data/apiProjectRoutes';

const panoptic = usePanopticStore()
const data = useDataStore()

const lastFile = ref(null)
const inputElem = ref(null)
const filename = ref(null)
const uploadConfirm: Ref<UploadConfirm> = ref(null)
const take = ref({})
const loading = ref(false)
const fusion = ref('first')
const relative = ref(true)
const proposeReparse = ref(false)

const missing = ref(null)

const uploadHasError = computed(() => {
    if (uploadConfirm.value == null) return false
    if (objValues(uploadConfirm.value.errors).length) return true
    return false
})

const uploadHasKeyError = computed(() => {
    if (uploadConfirm.value == null) return false
    if (uploadConfirm.value.errors[0]) return true
    return false
})

const params = computed(() => {
    const properties = uploadConfirm.value.colToProperty
    const exclude = Object.keys(properties).filter(i => !take.value[i]).map(Number)
    const params = {
        fusion: fusion.value,
        properties: properties,
        exclude: exclude,
        relative: relative.value
    }
    return params
})

async function importFile() {
    loading.value = true
    const properties = uploadConfirm.value.colToProperty
    const exclude = Object.keys(properties).filter(i => !take.value[i]).map(Number)
    const res = await apiParseImport(params.value)
    missing.value = res.missingRows
    loading.value = false
    if (!missing.value.length) {
        confirmImport()
    }
    proposeReparse.value = false
}

async function reParse() {
    importFile()
}

async function confirmImport() {
    loading.value = true
    await apiConfirmImport(params.value)
    loading.value = false
    clear()
    panoptic.hideModal(ModalId.IMPORT)
}

async function updloadFileClick(e) {
    const file = e.target.files[0]
    if (file == undefined) return
    await uploadFile(file)
}

async function uploadFile(file) {
    lastFile.value = file
    const res = await apiUploadPropertyCsv(file)
    uploadConfirm.value = res
    filename.value = file.name
    Object.keys(uploadConfirm.value.colToProperty).forEach(k => take.value[k] = true)
}

function clear() {
    uploadConfirm.value = null
    filename.value = null
    inputElem.value.value = null
    take.value = {}
    relative.value = true
    fusion.value = 'first'
    loading.value = false
    missing.value = null
    lastFile.value = null
    proposeReparse.value = false
}

watch(relative, () => proposeReparse.value = true)
</script>

<template>
    <div class="h-100 d-flex flex-column">
        <div class="d-flex p-2">
            <div class="me-1">File</div>
            <input type="file" ref="inputElem" accept="text/csv" @change="updloadFileClick" hidden />
            <div v-if="filename" class="sbb" @click="clear">{{ filename }}<i class="bi bi-x"
                    style="position:relative; top:1px" /></div>
            <div v-if="!filename" class="sbc" @click="inputElem.click()">Upload <i
                    class="bi bi-file-earmark-arrow-up" />
            </div>
            <br>
        </div>

        <div v-if="uploadConfirm" class="p-2 overflow-auto">
            <div v-if="uploadHasError" class="mb-3" :class="(uploadHasKeyError ? 'text-danger' : 'text-warning')">
                Errors:
                <div v-for="error, col in uploadConfirm.errors">
                    column: {{ Number(col) }} : {{ error }}
                </div>
            </div>
            <table v-if="!uploadHasKeyError">
                <tbody>
                    <tr>
                        <th class="border">Import</th>
                        <th class="border">Col</th>
                        <th class="border">Property</th>
                        <th class="border">Type</th>
                        <th class="border">Exist</th>
                        <th class="border">Mode</th>
                    </tr>

                    <tr v-for="p, i in uploadConfirm.colToProperty" class="border"
                        :class="!take[i] ? 'dimmed' : ''">
                        <td class="border text-center"><input v-if="i != 0" type="checkbox" v-model="take[i]" />
                        </td>
                        <td class="border text-center">{{ i }}</td>
                        <td class="border">
                            <PropertyIcon :type="p.type" /> {{ p.name }}
                        </td>
                        <td class="border">
                            {{ p.type }}
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
                </tbody>
            </table>
            <div v-if="uploadConfirm.key == 'path'">
                <div class="d-flex mt-3">
                    <div class="me-1">{{ $t('modals.import.fusion.title') }}</div>
                    <FusionModeDropdown :model-value="fusion" @update:model-value="e => fusion = e" />
                    <wTT :icon="true" message="modals.import.fusion.tooltip"></wTT>
                </div>
                <div class="d-flex mt-3">
                    {{ $t('modals.import.fusion.path') }}
                    <input type="checkbox" :style="{ 'margin-left': '0.5rem' }" v-model="relative" />
                    <wTT :icon="true" message="modals.import.fusion.path_tooltip"></wTT>
                </div>
            </div>

            <div v-if="!uploadHasKeyError">
                <div class="d-flex mt-2 flex-center w-20" style="width: 300px;">
                    <div v-if="!missing" class="d-flex mt-2 flex-center w-100">
                        <div v-if="!loading" class="bbb text-center w-100" @click="importFile">Import
                        </div>
                        <div v-if="loading" class="text-center w-100 border rounded">
                            <div class="spinner-border spinner-border-sm" style="position: relative; top: -1px"
                                role="status">
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="missing?.length">
                <div class="text-warning mb-2">
                    {{ missing.length }} {{ $t('modals.import.not_found') }}
                </div>
                <div class="d-flex flex-row">
                    <div v-if="!loading" style="width: 300px;" class="bbb text-center" @click="confirmImport">{{
                        $t('confirm') }}
                    </div>
                    <div v-if="!loading && proposeReparse" style="width: 300px;" class="bbb text-center ms-4"
                        @click="reParse">{{
                            $t('modals.import.reparse') }}
                    </div>
                </div>

                <div class="mt-2 p-2"
                    style="max-height: 200px; overflow-y: auto; border: 1px solid var(--border-color);">
                    <div v-for="lines in missing">
                        {{ $t('modals.import.row') }}: {{ lines[0] + 1 }} {{ $t('modals.import.key') }}: {{ lines[1]
                        }}
                    </div>
                </div>
            </div>

            <div v-if="loading" class="text-center w-100 border rounded">
                <div class="spinner-border spinner-border-sm" style="position: relative; top: -1px" role="status">
                </div>
            </div>

        </div>
        
        <div v-else class="m-4 overflow-auto">
            {{ $t('modals.import.help.0') }}
            <ul>
                <li>
                    {{ $t('modals.import.help.1') }}
                </li>
                <li>
                    {{ $t('modals.import.help.2') }}
                    <ul>
                        <li>
                            {{ $t('modals.import.help.3') }}
                        </li>
                        <li>
                            {{ $t('modals.import.help.4') }}
                        </li>
                    </ul>
                </li>
                <li>
                    {{ $t('modals.import.help.5') }}
                    <br>
                    {{ $t('modals.import.help.6') }}
                </li>
                <li>
                    {{ $t('modals.import.help.7') }}
                </li>
            </ul>
            {{ $t('modals.import.help.8') }}

            <table>
                <tbody>
                    <tr>
                        <th class="border">{{ $t("modals.import.help.9") }} </th>
                        <th class="border">{{ $t("modals.import.help.10") }} </th>
                    </tr>
                    <tr>
                        <td class="border text-center">{{ $t("modals.properties.multi_tags") }} </td>
                        <td class="border text-center">multi_tags</td>
                    </tr>
                    <tr>
                        <td class="border text-center">{{ $t("modals.properties.tag") }} </td>
                        <td class="border text-center">tag</td>
                    </tr>
                    <tr>
                        <td class="border text-center">{{ $t("modals.properties.number") }} </td>
                        <td class="border text-center">number</td>
                    </tr>
                    <tr>
                        <td class="border text-center">{{ $t("modals.properties.text") }} </td>
                        <td class="border text-center">text</td>
                    </tr>
                    <tr>
                        <td class="border text-center">{{ $t("modals.properties.checkbox") }} </td>
                        <td class="border text-center">checkbox</td>
                    </tr>
                    <tr>
                        <td class="border text-center">{{ $t("modals.properties.color") }} </td>
                        <td class="border text-center">color</td>
                    </tr>
                    <tr>
                        <td class="border text-center">{{ $t("modals.properties.date") }} </td>
                        <td class="border text-center">date</td>
                    </tr>
                    <tr>
                        <td class="border text-center">{{ $t("modals.properties.url") }} </td>
                        <td class="border text-center">url</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
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