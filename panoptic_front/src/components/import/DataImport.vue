<script setup lang="ts">
import { usePanopticStore } from '@/data/stores/panopticStore';
import PropertyIcon from '../properties/PropertyIcon.vue';
import CsvDropZone from './CsvDropZone.vue';
import { computed, Ref, ref, watch } from 'vue';
import { ModalId, PropertyMode, UploadConfirm } from '@/data/models';
import { objValues } from '@/utils/utils';
import { apiParseImport, apiConfirmImport, apiUploadPropertyCsv } from '@/data/api/projectApi';

const panoptic = usePanopticStore()

const fusionModes = ['first', 'last', 'all', 'new']
const helpTypes = ['multi_tags', 'tag', 'number', 'text', 'checkbox', 'color', 'date', 'url']
const helpExample = 'path;categories[multi_tags];score[number]\nimages/cat.jpg;animal,cute;12\nimages/car.jpg;vehicle;7'
// Unmatched rows can number in the thousands; the list only needs to show the first ones.
const MISSING_SHOWN = 500

const file = ref<File | null>(null)
const uploading = ref(false)
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

const columns = computed(() => {
    if (!uploadConfirm.value) return []
    return Object.entries(uploadConfirm.value.colToProperty).map(([col, prop]) => ({ col: Number(col), prop }))
})

const takenCount = computed(() => columns.value.filter(c => take.value[c.col]).length)
const allTaken = computed(() => takenCount.value == columns.value.length)

const canImport = computed(() => uploadConfirm.value && !uploadHasKeyError.value && takenCount.value > 0 && !loading.value)

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

function toggleAll() {
    const value = !allTaken.value
    columns.value.forEach(c => take.value[c.col] = value)
}

async function importFile() {
    loading.value = true
    try {
        const res = await apiParseImport(params.value)
        missing.value = res.missingRows
    } finally {
        loading.value = false
    }
    proposeReparse.value = false
    if (!missing.value.length) {
        await confirmImport()
    }
}

async function confirmImport() {
    loading.value = true
    try {
        await apiConfirmImport(params.value)
    } finally {
        loading.value = false
    }
    panoptic.hideModal(ModalId.IMPORT)
}

function onPrimary() {
    if (missing.value?.length) confirmImport()
    else importFile()
}

async function setFile(f: File | null) {
    clear()
    if (!f) return
    file.value = f
    uploading.value = true
    try {
        uploadConfirm.value = await apiUploadPropertyCsv(f)
    } finally {
        uploading.value = false
    }
    Object.keys(uploadConfirm.value.colToProperty).forEach(k => take.value[k] = true)
}

function clear() {
    file.value = null
    uploadConfirm.value = null
    take.value = {}
    relative.value = true
    fusion.value = 'first'
    loading.value = false
    missing.value = null
    proposeReparse.value = false
}

watch(relative, () => proposeReparse.value = true)
</script>

<template>
    <div class="import-page">
        <div class="import-body">

            <div class="field">
                <div class="field-label">{{ $t('modals.import.file') }}</div>
                <CsvDropZone :file="file" :loading="uploading" @update:file="setFile">
                    <template #meta>
                        <span v-if="uploadConfirm?.key">
                            {{ $t('modals.import.key') }} <code>{{ uploadConfirm.key }}</code>
                        </span>
                    </template>
                </CsvDropZone>
            </div>

            <!-- Format reference, shown until a file is chosen -->
            <div v-if="!file" class="field">
                <div class="field-label">{{ $t('modals.import.format') }}</div>
                <div class="help-card">
                    <div>{{ $t('modals.import.help.0') }}</div>
                    <ul>
                        <li>{{ $t('modals.import.help.1') }}</li>
                        <li>
                            {{ $t('modals.import.help.2') }}
                            <ul>
                                <li>{{ $t('modals.import.help.3') }}</li>
                                <li>{{ $t('modals.import.help.4') }}</li>
                            </ul>
                        </li>
                        <li>{{ $t('modals.import.help.5') }} <code>name[type]</code></li>
                        <li>{{ $t('modals.import.help.7') }}</li>
                    </ul>
                    <pre class="help-example">{{ helpExample }}</pre>
                    <div>{{ $t('modals.import.help.8') }}</div>
                    <div class="type-grid">
                        <div v-for="type in helpTypes" :key="type" class="type-item">
                            <PropertyIcon :type="type" class="type-icon" />
                            <span class="type-name">{{ $t('modals.properties.' + type) }}</span>
                            <code>{{ type }}</code>
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="uploadHasError" class="callout" :class="uploadHasKeyError ? 'ko' : 'warn'">
                <i class="bi bi-exclamation-triangle callout-icon" />
                <div class="callout-body">
                    <div class="callout-title">
                        {{ uploadHasKeyError ? $t('modals.import.key_error') : $t('modals.import.errors') }}
                    </div>
                    <div v-for="error, col in uploadConfirm.errors" :key="col" class="callout-line">
                        <span v-if="Number(col) > 0">{{ $t('modals.import.column') }} <span class="num">{{ col }}</span> · </span>
                        {{ error }}
                    </div>
                </div>
            </div>

            <div v-if="uploadConfirm && !uploadHasKeyError && columns.length" class="field">
                <div class="label-row">
                    <span class="field-label">{{ $t('modals.import.columns') }}</span>
                    <span class="count num">{{ takenCount }} / {{ columns.length }}</span>
                </div>
                <div class="column-table">
                    <table>
                        <thead>
                            <tr>
                                <th class="cell-check">
                                    <input type="checkbox" class="checkbox" :checked="allTaken"
                                        :indeterminate="takenCount > 0 && !allTaken" @change="toggleAll" />
                                </th>
                                <th class="cell-col">{{ $t('modals.import.col') }}</th>
                                <th>{{ $t('modals.import.property') }}</th>
                                <th>{{ $t('modals.import.type') }}</th>
                                <th>{{ $t('modals.import.status') }}</th>
                                <th>{{ $t('modals.import.mode') }}</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="{ col, prop } in columns" :key="col" :class="{ dimmed: !take[col] }">
                                <td class="cell-check">
                                    <input type="checkbox" class="checkbox" v-model="take[col]" />
                                </td>
                                <td class="cell-col num">{{ col }}</td>
                                <td class="cell-name">
                                    <PropertyIcon :type="prop.type" class="type-icon" />
                                    <span class="prop-name">{{ prop.name }}</span>
                                </td>
                                <td class="cell-type">
                                    {{ helpTypes.includes(prop.type) ? $t('modals.properties.' + prop.type) : prop.type }}
                                </td>
                                <td>
                                    <span v-if="prop.id > 0" class="badge existing">
                                        <i class="bi bi-check2" />{{ $t('modals.import.existing') }}
                                    </span>
                                    <span v-else class="badge new">
                                        <i class="bi bi-plus" />{{ $t('modals.import.new') }}
                                    </span>
                                </td>
                                <td>
                                    <div v-if="prop.id < 0" class="segmented mini"
                                        :class="{ disabled: !take[col] }">
                                        <div class="segment" :class="{ selected: prop.mode == PropertyMode.sha1 }"
                                            @click="prop.mode = PropertyMode.sha1">
                                            {{ $t('modals.import.mode_image') }}
                                        </div>
                                        <div class="segment" :class="{ selected: prop.mode == PropertyMode.id }"
                                            @click="prop.mode = PropertyMode.id">
                                            {{ $t('modals.import.mode_instance') }}
                                        </div>
                                    </div>
                                    <span v-else class="mode-text">
                                        {{ prop.mode == 'id' ? $t('modals.import.mode_instance') : $t('modals.import.mode_image') }}
                                    </span>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <template v-if="uploadConfirm?.key == 'path' && !uploadHasKeyError">
                <div class="field">
                    <div class="field-label">{{ $t('modals.import.fusion.title') }}</div>
                    <div class="segmented">
                        <div v-for="mode in fusionModes" :key="mode" class="segment"
                            :class="{ selected: fusion == mode }" @click="fusion = mode">
                            {{ $t('modals.import.fusion.' + mode) }}
                        </div>
                    </div>
                    <div class="field-hint">{{ $t('modals.import.fusion.' + fusion + '_tooltip') }}</div>
                </div>

                <label class="switch-row">
                    <div>
                        <div>{{ $t('modals.import.fusion.path') }}</div>
                        <div class="field-hint">{{ $t('modals.import.fusion.path_tooltip') }}</div>
                    </div>
                    <input type="checkbox" class="switch" v-model="relative" />
                </label>
            </template>

            <div v-if="missing?.length" class="callout warn">
                <i class="bi bi-exclamation-triangle callout-icon" />
                <div class="callout-body">
                    <div class="callout-title">
                        <span class="num">{{ missing.length }}</span> {{ $t('modals.import.not_found') }}
                    </div>
                    <div class="missing-list">
                        <div v-for="line in missing.slice(0, MISSING_SHOWN)" :key="line[0]" class="missing-row">
                            <span class="missing-line num">{{ $t('modals.import.row') }} {{ line[0] + 1 }}</span>
                            <span class="missing-key">{{ line[1] }}</span>
                        </div>
                        <div v-if="missing.length > MISSING_SHOWN" class="missing-row count num">
                            … +{{ missing.length - MISSING_SHOWN }}
                        </div>
                    </div>
                </div>
            </div>

        </div>

        <div class="import-footer">
            <div v-if="missing?.length && proposeReparse" class="btn-action" :class="{ disabled: loading }"
                @click="importFile">
                <i class="bi bi-arrow-repeat" />
                {{ $t('modals.import.reparse') }}
            </div>
            <div class="btn-action primary" :class="{ disabled: !canImport }" @click="onPrimary">
                <span v-if="loading" class="spinner-border spinner-border-sm" role="status" />
                <i v-else class="bi" :class="missing?.length ? 'bi-check2' : 'bi-box-arrow-in-down'" />
                {{ missing?.length ? $t('confirm') : $t('modals.import.import') }}
            </div>
        </div>
    </div>
</template>

<style scoped>
/* --- format help --- */
.type-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 4px 16px;
}

.type-item {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
}

.type-icon {
    flex: none;
    color: var(--text-secondary);
}

.type-name {
    flex: 1;
    min-width: 0;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* --- column mapping table --- */
.column-table {
    max-height: 260px;
    overflow: auto;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
}

table {
    width: 100%;
    border-collapse: collapse;
}

th {
    position: sticky;
    top: 0;
    z-index: 1;
    padding: 6px 8px;
    font-size: 11px;
    font-weight: var(--font-weight-semibold);
    text-align: left;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-secondary);
    background-color: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
}

td {
    padding: 4px 8px;
    border-bottom: 1px solid var(--border-light);
    vertical-align: middle;
}

tbody tr:last-child td {
    border-bottom: none;
}

tbody tr:hover {
    background-color: var(--hover-bg);
}

tr.dimmed td:not(.cell-check) {
    opacity: 0.45;
}

.cell-check {
    width: 28px;
    text-align: center;
}

.cell-col {
    width: 40px;
    color: var(--text-tertiary);
}

.cell-name {
    max-width: 180px;
}

.cell-name .prop-name {
    margin-left: 4px;
}

.cell-name,
.cell-type {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.cell-type,
.mode-text {
    color: var(--text-secondary);
}

.badge {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    padding: 1px 6px 1px 4px;
    font-size: 11px;
    font-weight: var(--font-weight-medium);
    border-radius: 8px;
}

.badge.existing {
    color: var(--success);
    background-color: color-mix(in srgb, var(--success) 12%, transparent);
}

.badge.new {
    color: var(--primary);
    background-color: var(--primary-light);
}

.segmented.mini {
    display: inline-flex;
    padding: 1px;
}

.segmented.mini .segment {
    padding: 1px 8px;
    font-size: 12px;
}

.segmented.mini.disabled {
    pointer-events: none;
}

/* --- unmatched rows --- */
.missing-list {
    max-height: 160px;
    margin-top: 6px;
    overflow-y: auto;
    font-size: 12px;
    border-top: 1px solid var(--border-light);
}

.missing-row {
    display: flex;
    gap: 10px;
    padding: 2px 0;
}

.missing-line {
    flex: none;
    min-width: 64px;
    color: var(--text-tertiary);
}

.missing-key {
    font-family: var(--font-mono);
    font-size: 11px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>
