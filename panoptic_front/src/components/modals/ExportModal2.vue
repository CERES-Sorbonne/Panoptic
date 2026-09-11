<script setup lang="ts">

import { ref, computed, reactive } from 'vue';
import { useI18n } from 'vue-i18n';
import { ModalId, PropertyGroupId } from '@/data/models';
import { sleep } from '@/utils/utils';
import PropertyIcon from '../properties/PropertyIcon.vue';
import { useDataStore } from '@/data/dataStore';
import { useTabStore } from '@/data/tabStore';
import { useColumnStore } from '@/data/columnStore';
import Modal2 from './Modal2.vue';
import { apiExportProperties } from '@/data/apiProjectRoutes';

const data = useDataStore()
const tabStore = useTabStore()
const col = useColumnStore()
const { t } = useI18n()

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
// Counted once on show: the filter result is a plain class, not reactive.
const filteredCount = ref(0)

const all = computed(() => properties.value.every(p => state.properties[p.id]))

// Same grouping and ordering as the Properties panel (PropertyGroupPanel):
// user groups first, then the default group, then metadata.
const propertyGroups = computed(() => data.propertyTree
    .filter(n => n.groupId < 0 || data.propertyGroups[n.groupId])
    .map(n => ({
        groupId: n.groupId,
        name: groupName(n.groupId),
        properties: n.propertyIds.map(id => data.properties[id]).filter(Boolean)
    }))
    .filter(g => g.properties.length))

const properties = computed(() => propertyGroups.value.flatMap(g => g.properties))

const selectedPropertyCount = computed(() => properties.value.filter(p => state.properties[p.id]).length)

function groupName(groupId: number) {
    if (groupId == PropertyGroupId.DEFAULT) return t('common.properties.default')
    if (groupId == PropertyGroupId.METADATA) return t('common.properties.metadata')
    return data.propertyGroups[groupId]?.name
}

function groupSelectedCount(group) {
    return group.properties.filter(p => state.properties[p.id]).length
}

function toggleGroup(group) {
    const select = groupSelectedCount(group) < group.properties.length
    group.properties.forEach(p => {
        if (select) state.properties[p.id] = true
        else delete state.properties[p.id]
    })
}

const selectedCount = computed(() => {
    col.selectionVersion  // reactive dep on global selection (step 2)
    return col.selectedCount()
})



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
    const properties = tabStore.getMainTab()?.getVisibleProperties() ?? []
    properties.forEach(p => state.properties[p.id] = true)
    filteredCount.value = tabStore.getMainTab()?.collection?.filterManager?.result?.slots?.length ?? 0
    // state.properties[-1] = true
}

// The filter pipeline works on slots now, so map them back to instance ids.
function getFilteredIds() {
    const collection = tabStore.getMainTab()?.collection
    if (!collection) return []
    const ids = col.instanceIds()
    return Array.from(collection.filterManager.result.slots).map(s => ids[s])
}

async function buildRequest() {
    const req = { exportImages: state.exportImages, properties: undefined, images: undefined, name: undefined, key: 'id' }
    req.properties = Object.keys(state.properties).map(Number).filter(k => state.properties[k])
    req.properties.sort((a, b) => properties.value.findIndex(p => p.id == a) - properties.value.findIndex(p => p.id == b))
    if (state.name && state.name != '') {
        req.name = state.name
    }
    if (state.selection == 'selected') {
        req.images = col.getSelectedIds()
    }
    if (state.selection == 'filtered') {
        req.images = getFilteredIds()
    }
    req.key = state.key
    isLoading.value = true
    await sleep(100)
    try {
        await apiExportProperties(req.name, req.images, req.key, req.properties, req.exportImages)
    } finally {
        isLoading.value = false
    }
    modalElem.value.hide()
}

</script>


<template>
    <Modal2 :id="ModalId.EXPORT" @show="show" ref="modalElem" :max-width="560" :max-height="660">
        <template #title>
            <div class="modal-title">
                <i class="bi bi-box-arrow-up me-2" />{{ $t('modals.export.title') }}
            </div>
        </template>
        <template #content>
            <div class="export-modal">
                <div class="export-body">

                    <div class="field">
                        <label class="field-label" for="export-name">{{ $t('modals.export.name') }}</label>
                        <input id="export-name" class="field-input" type="text"
                            :placeholder="$t('modals.export.name_placeholder')" v-model="state.name" />
                    </div>

                    <div class="field">
                        <div class="field-label">{{ $t('modals.export.selection_label') }}</div>
                        <div class="segmented">
                            <div class="segment" :class="getClass(state.selection, 'all')"
                                @click="set('selection', 'all')">
                                {{ $t('modals.export.selection_all') }}
                            </div>
                            <div class="segment" v-if="selectedCount > 0" :class="getClass(state.selection, 'selected')"
                                @click="set('selection', 'selected')">
                                {{ $t('modals.export.selection_selected') }}
                                <span class="segment-count">{{ selectedCount }}</span>
                            </div>
                            <div class="segment" :class="getClass(state.selection, 'filtered')"
                                @click="set('selection', 'filtered')">
                                {{ $t('modals.export.selection_filtered') }}
                                <span class="segment-count" v-if="filteredCount > 0">{{ filteredCount }}</span>
                            </div>
                        </div>
                    </div>

                    <div class="field">
                        <div class="field-label">{{ $t('modals.export.key_label') }}</div>
                        <div class="segmented">
                            <div class="segment" :class="getClass(state.key, 'id')" @click="set('key', 'id')">
                                {{ $t('modals.export.id') }}
                            </div>
                            <div class="segment" :class="getClass(state.key, 'local_path')"
                                @click="set('key', 'local_path')">
                                {{ $t('modals.export.local_path') }}
                            </div>
                            <div class="segment" :class="getClass(state.key, 'global_path')"
                                @click="set('key', 'global_path')">
                                {{ $t('modals.export.global_path') }}
                            </div>
                        </div>
                    </div>

                    <div class="field">
                        <div class="label-row">
                            <span class="field-label">{{ $t('modals.export.properties_label') }}</span>
                            <label class="all-toggle">
                                <input type="checkbox" class="checkbox" :checked="all"
                                    :indeterminate="selectedPropertyCount > 0 && !all" @change="toggleAll" />
                                {{ $t('modals.export.properties_all') }}
                                <span class="count">{{ selectedPropertyCount }} / {{ properties.length }}</span>
                            </label>
                        </div>
                        <div class="property-list">
                            <div v-for="group in propertyGroups" :key="group.groupId" class="property-group">
                                <label class="group-header">
                                    <input type="checkbox" class="checkbox"
                                        :checked="groupSelectedCount(group) == group.properties.length"
                                        :indeterminate="groupSelectedCount(group) > 0 && groupSelectedCount(group) < group.properties.length"
                                        @change="toggleGroup(group)" />
                                    <span class="group-name">{{ group.name }}</span>
                                </label>
                                <label v-for="p in group.properties" :key="p.id" class="property-item">
                                    <input type="checkbox" class="checkbox" v-model="state.properties[p.id]" />
                                    <PropertyIcon :type="p.type" class="property-icon" />
                                    <span class="property-name">{{ p.name }}</span>
                                </label>
                            </div>
                        </div>
                    </div>

                    <label class="field switch-row">
                        <span class="field-label mb-0">{{ $t('modals.export.export_images') }}</span>
                        <input type="checkbox" class="switch" v-model="state.exportImages" />
                    </label>

                </div>

                <div class="export-footer">
                    <div class="export-btn" :class="{ disabled: isLoading }" @click="!isLoading && buildRequest()">
                        <span v-if="isLoading" class="spinner-border spinner-border-sm me-2" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </span>
                        <i v-else class="bi bi-download me-2" />
                        {{ $t('modals.export.export') }}
                    </div>
                </div>

            </div>
        </template>
    </Modal2>
</template>

<style scoped>
.modal-title {
    padding: 2px 6px;
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.export-modal {
    display: flex;
    flex-direction: column;
    height: 100%;
    font-size: 13px;
    color: var(--text-primary);
}

.export-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

/* --- generic field --- */
.field {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.field-label {
    font-size: 11px;
    font-weight: var(--font-weight-semibold);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-secondary);
}

.field-input {
    width: 100%;
    padding: 6px 10px;
    font-size: 13px;
    color: var(--text-primary);
    background-color: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.field-input::placeholder {
    color: var(--text-tertiary);
}

.field-input:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px var(--primary-light);
}

/* --- segmented control --- */
.segmented {
    display: flex;
    gap: 2px;
    padding: 2px;
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
}

.segment {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    padding: 4px 8px;
    border-radius: 3px;
    color: var(--text-secondary);
    text-align: center;
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
    transition: background-color var(--transition-fast), color var(--transition-fast);
}

.segment:hover {
    color: var(--text-primary);
    background-color: var(--hover-bg);
}

.segment.selected {
    color: var(--text-primary);
    font-weight: var(--font-weight-medium);
    background-color: var(--bg-primary);
    box-shadow: var(--shadow-sm);
}

.segment-count {
    padding: 0 5px;
    font-size: 11px;
    line-height: 16px;
    color: var(--text-secondary);
    background-color: var(--bg-tertiary);
    border-radius: 8px;
}

.segment.selected .segment-count {
    color: var(--primary);
    background-color: var(--primary-light);
}

/* --- property picker --- */
.label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}

.all-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-secondary);
    cursor: pointer;
}

.count {
    font-size: 11px;
    color: var(--text-tertiary);
}

.property-list {
    max-height: 220px;
    overflow-y: auto;
    padding: 2px 0;
    border-top: 1px solid var(--border-light);
    border-bottom: 1px solid var(--border-light);
}

.property-group + .property-group {
    margin-top: 6px;
}

.group-header {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 22px;
    cursor: pointer;
}

.group-name {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.02em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.property-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 2px 0 2px 16px;
    cursor: pointer;
    overflow: hidden;
}

.property-item:hover .property-name {
    color: var(--primary);
}

.property-icon {
    flex: none;
    color: var(--text-secondary);
}

.property-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.checkbox {
    flex: none;
    width: 13px;
    height: 13px;
    accent-color: var(--primary);
    cursor: pointer;
}

/* --- switch row --- */
.switch-row {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
}

.switch-row:hover {
    background-color: var(--bg-secondary);
}

.switch {
    position: relative;
    flex: none;
    width: 32px;
    height: 18px;
    margin: 0;
    appearance: none;
    -webkit-appearance: none;
    background-color: var(--border-color);
    border-radius: 9px;
    cursor: pointer;
    transition: background-color var(--transition-fast);
}

.switch::after {
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 14px;
    height: 14px;
    background-color: #ffffff;
    border-radius: 50%;
    box-shadow: var(--shadow-sm);
    transition: transform var(--transition-fast);
}

.switch:checked {
    background-color: var(--primary);
}

.switch:checked::after {
    transform: translateX(14px);
}

/* --- footer --- */
.export-footer {
    display: flex;
    justify-content: flex-end;
    padding: 10px 16px;
    background-color: var(--bg-secondary);
    border-top: 1px solid var(--island-border);
}

.export-btn {
    display: flex;
    align-items: center;
    padding: 5px 16px;
    color: var(--text-inverse);
    font-weight: var(--font-weight-medium);
    background-color: var(--primary);
    border-radius: var(--radius-sm);
    cursor: pointer;
    user-select: none;
    transition: background-color var(--transition-fast);
}

.export-btn:hover {
    background-color: var(--primary-dark);
}

.export-btn.disabled {
    opacity: 0.6;
    cursor: not-allowed;
}
</style>
