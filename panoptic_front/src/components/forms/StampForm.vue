<script setup lang="ts">
import { isReadonly, PropertyType } from '@/data/models';
import { computed, onMounted, reactive, ref } from 'vue';
import { PropertyGroupId } from '@/data/models';
import { useCurrentTab } from '@/data/composables/useCurrentTab';
import Dropdown from '../dropdowns/Dropdown.vue';
import PropertySelection from '../inputs/PropertySelection.vue';
import { useI18n } from 'vue-i18n';

import PropertyIcon from '../properties/PropertyIcon.vue';
import wTT from '../tooltips/withToolTip.vue'
import { isTag } from '@/utils/utils';
import { useDataStore } from '@/data/stores/dataStore';
import CellTagInput from '../property_cell_input/CellTagInput.vue';
import CheckboxInput from '../property_inputs/CheckboxInput.vue';
import CellColorInput from '../property_cell_input/CellColorInput.vue';
import RowDateInput from '../property_row_input/RowDateInput.vue';
import RowNumberInput from '../property_row_input/RowNumberInput.vue';
import CellTextInput from '../property_cell_input/CellTextInput.vue';
import CellUrlInput from '../property_cell_input/CellUrlInput.vue';

const data = useDataStore()

const props = defineProps({
    values: Object as () => { [propertyId: number]: any },
    erase: Set<number>,
    modes: Object as () => { [pId: number]: number }
})
const emits = defineEmits(['blur'])
const { t } = useI18n()
const tab = useCurrentTab()

// Stampable properties (computed / readonly / special ids excluded)
const stampable = computed(() => data.propertyList.filter(p => p.id >= 0 && !isReadonly(p)))
const stampableIds = computed(() => new Set(stampable.value.map(p => p.id)))

// The "stamp set": properties shown in the form. Reset to the tab's visible properties on each open.
const chosen = reactive(new Set<number>())

function setChosen(ids: number[]) {
    chosen.clear()
    ids.filter(id => stampableIds.value.has(id)).forEach(id => chosen.add(id))
    dropPending()
}
function resetToVisible() {
    setChosen((tab.value?.getVisibleProperties() ?? []).map(p => p.id))
}
function selectAll() { setChosen(stampable.value.map(p => p.id)) }
function clearSet() { setChosen([]) }
function addProperty(id: number) {
    if (stampableIds.value.has(id)) chosen.add(id)
    addElem.value?.hide()
}
function removeProperty(id: number) {
    chosen.delete(id)
    dropPending()
}
// Forget values / modes / erase flags of properties no longer in the set, so they aren't applied
function dropPending() {
    Object.keys(props.values).map(Number).forEach(id => { if (!chosen.has(id)) delete props.values[id] })
    Object.keys(props.modes).map(Number).forEach(id => { if (!chosen.has(id)) delete props.modes[id] })
    Array.from(props.erase).forEach(id => { if (!chosen.has(id)) props.erase.delete(id) })
}
onMounted(resetToVisible)
defineExpose({ resetToVisible })

const addElem = ref(null)
const ignoreIds = computed(() => [
    ...chosen,
    ...data.propertyList.filter(p => !stampableIds.value.has(p.id)).map(p => p.id)
])

function groupName(groupId: number): string {
    if (groupId === PropertyGroupId.DEFAULT) return t('common.properties.default')
    if (groupId === PropertyGroupId.METADATA) return t('common.properties.metadata')
    return data.propertyGroups[groupId]?.name ?? ''
}

// Chosen properties grouped like the sidebar (propertyTree order)
const groups = computed(() => {
    const res = [] as { groupId: number, name: string, properties: typeof stampable.value }[]
    for (const node of data.propertyTree) {
        const properties = node.propertyIds.filter(id => chosen.has(id)).map(id => data.properties[id]).filter(Boolean)
        if (properties.length) res.push({ groupId: node.groupId, name: groupName(node.groupId), properties })
    }
    return res
})
const showGroupHeaders = computed(() => groups.value.length > 1 || (groups.value[0] && groups.value[0].groupId !== PropertyGroupId.DEFAULT))
const properties = computed(() => groups.value.flatMap(g => g.properties))

const propertyColor = computed(() => {
    const res = {} as { [pId: number]: String }
    properties.value.forEach(p => {
        if (props.erase.has(p.id)) {
            res[p.id] = 'text-warning'
            return
        }
        if (props.values[p.id] == undefined) {
            res[p.id] = 'text-secondary'
            return
        }
        res[p.id] = 'text-success'
    })
    return res
})

function setMode(propId: number, mode: number) {
    props.modes[propId] = mode
}

</script>

<template>
    <div class="form-title">{{ $t('modals.tagging.title') }}</div>
    <div class="stamp-toolbar">
        <Dropdown ref="addElem" :teleport="true" :auto-focus="false" fit-content>
            <template #button>
                <button type="button" class="st-tool st-add"><i class="bi bi-plus-lg" />{{ $t('modals.tagging.add_property') }}</button>
            </template>
            <template #popup>
                <PropertySelection :ignore-ids="ignoreIds" @select="addProperty" />
            </template>
        </Dropdown>
        <div class="flex-grow-1"></div>
        <button type="button" class="st-tool" @click="resetToVisible">{{ $t('modals.tagging.visible_set') }}</button>
        <button type="button" class="st-tool" @click="selectAll">{{ $t('modals.tagging.all_set') }}</button>
        <button type="button" class="st-tool" :disabled="!chosen.size" @click="clearSet">{{ $t('modals.tagging.clear_set') }}</button>
    </div>
    <div v-if="!properties.length" class="stamp-empty">{{ $t('modals.tagging.empty') }}</div>
    <table v-else class="stamp-table">
        <tbody v-for="group in groups" :key="group.groupId">
            <tr v-if="showGroupHeaders" class="group-row">
                <td colspan="5" class="group-header">{{ group.name }}</td>
            </tr>
            <tr v-for="property in group.properties" :key="property.id" class="prop-row">
                <template v-if="property.id >= 0">
                    <td :class="propertyColor[property.id]" class="text-nowrap prop-name">
                        <wTT :message="property.name" class="d-block">
                            <div class="prop-name-inner">
                                <PropertyIcon :type="property.type" />
                                {{ property.name }}
                            </div>
                        </wTT>
                    </td>
                    <template v-if="!props.erase.has(property.id)">
                        <td class="w-100 prop-input">
                            <CellTagInput v-if="isTag(property.type)" :property="property"
                                v-model="props.values[property.id]" :teleport="false" :auto-focus="true"
                                :can-create="true" ref="inputElem" />

                            <CellTextInput v-else-if="property.type == PropertyType.string"
                                v-model="props.values[property.id]" ref="inputElem" :min-height="20" />

                            <CellUrlInput v-else-if="property.type == PropertyType.url"
                                v-model="props.values[property.id]" :url-mode="true" ref="inputElem" />

                            <CheckboxInput v-else-if="property.type == PropertyType.checkbox"
                                v-model="props.values[property.id]" />

                            <CellColorInput v-else-if="property.type == PropertyType.color"
                                v-model="props.values[property.id]" ref="inputElem" :min-height="22" />

                            <RowDateInput v-else-if="property.type == PropertyType.date"
                                v-model="props.values[property.id]" />

                            <RowNumberInput v-else-if="property.type == PropertyType.number"
                                v-model="props.values[property.id]" :height="30" />
                        </td>
                        <td class="mode-col">
                            <div v-if="property.type == PropertyType.multi_tags && props.values[property.id]"
                                class="d-flex mode-switch">
                                <div class="mode-option" :class="{ selected: !props.modes[property.id] }"
                                    @click="setMode(property.id, 0)">
                                    <wTT message="dropdown.stamp.add"><i class="bi bi-plus-lg" /></wTT>
                                </div>
                                <div class="mode-option" :class="{ selected: props.modes[property.id] == 1 }"
                                    @click="setMode(property.id, 1)">
                                    <wTT message="dropdown.stamp.set"><i class="bi bi-arrow-repeat" /></wTT>
                                </div>
                                <div class="mode-option" :class="{ selected: props.modes[property.id] == 2 }"
                                    @click="setMode(property.id, 2)">
                                    <wTT message="dropdown.stamp.del"><i class="bi bi-dash-lg" /></wTT>
                                </div>
                            </div>
                        </td>
                    </template>

                    <template v-if="!props.erase.has(property.id)">
                        <td v-if="props.values[property.id] == undefined" class="action-col">
                            <wTT message="modals.tagging.erase_tooltip">
                                <i class="bi bi-trash sb" @click="erase.add(property.id)" />
                            </wTT>
                        </td>

                        <td v-else class="action-col">
                            <wTT message="modals.tagging.erase_tooltip">
                                <i class="bi bi-arrow-counterclockwise sb"
                                    @click="delete props.values[property.id]"></i>
                            </wTT>
                        </td>
                    </template>

                    <template v-else>
                        <td class="w-100"></td>
                        <td class="text-warning erase-label">{{ $t("modals.tagging.erase") }}</td>

                        <td class="action-col">
                            <wTT message="modals.tagging.cancel_tooltip">
                                <i class="bi bi-arrow-counterclockwise sb" @click="erase.delete(property.id)"></i>
                            </wTT>
                        </td>
                    </template>

                    <td class="remove-col">
                        <wTT message="modals.tagging.remove_from_set">
                            <i class="bi bi-x-lg" @click="removeProperty(property.id)" />
                        </wTT>
                    </td>
                </template>
            </tr>
        </tbody>
    </table>
</template>

<style scoped>
.form-title {
    padding: 6px 8px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    opacity: 0.6;
}

.stamp-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0 2px;
}

tr td {
    vertical-align: top;
    padding: 4px 4px;
    background: transparent;
    transition: background-color 0.12s ease;
}

tr.prop-row:hover td {
    background-color: var(--hover-bg);
}

tr td:first-child {
    border-radius: var(--radius-sm) 0 0 var(--radius-sm);
}

tr td:last-child {
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.prop-name {
    padding-left: 8px;
    padding-top: 6px;
}

/* Long names are cropped so the form never scrolls horizontally; the full name shows in the tooltip */
.prop-name-inner {
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
}

.prop-input {
    padding-top: 6px;
    /* width: 100% + max-width: 0 makes the cell take the remaining space without letting its
       content widen the table */
    max-width: 0;
}

/* Tags wrap first; a single tag wider than the cell is cropped (TagBadge shows the full name on hover) */
.prop-input :deep(.tag-badge) {
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    vertical-align: middle;
}

.prop-input :deep(.tag-badge .label) {
    display: inline;
}

.mode-col {
    padding-top: 5px;
}

.mode-switch {
    background-color: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    padding: 2px;
    gap: 2px;
}

.mode-option {
    padding: 0px 6px;
    border-radius: 3px;
    cursor: pointer;
    font-size: 12px;
    line-height: 18px;
    opacity: 0.7;
}

.mode-option:hover {
    opacity: 1;
}

.selected {
    background-color: var(--bg-primary);
    color: var(--primary);
    opacity: 1;
}

.erase-label {
    text-align: end;
    font-size: 12px;
    /* match the property name's padding and line box so the label sits on the same line */
    padding-top: 6px;
    line-height: 21px;
}

.action-col {
    width: 30px;
    text-align: center;
    vertical-align: top;
}

.action-col i {
    opacity: 0.45;
    border-radius: 4px;
    padding: 2px;
}

.action-col i:hover {
    opacity: 1;
    background-color: var(--bg-tertiary);
}
.stamp-toolbar {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 0 4px;
}

.st-tool {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    height: 24px;
    padding: 0 8px;
    border: none;
    border-radius: var(--radius-sm) !important;
    background: transparent;
    font-size: 12px !important;
    color: var(--text-secondary, #666);
    white-space: nowrap;
}

.st-tool:hover:not(:disabled) {
    background: var(--hover-bg);
    color: var(--text-primary, #1a1a1a);
}

.st-tool:disabled {
    opacity: 0.4;
}

.st-add {
    color: var(--primary);
}

.stamp-empty {
    padding: 14px 8px;
    text-align: center;
    font-size: 12px;
    color: var(--text-tertiary, #999);
}

.group-header {
    padding: 8px 8px 2px !important;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: var(--text-tertiary, #999);
}

.remove-col {
    width: 22px;
    padding-left: 0 !important;
    padding-top: 6px !important;
    text-align: center;
}

.remove-col i {
    font-size: 11px;
    cursor: pointer;
    opacity: 0;
    border-radius: 4px;
    padding: 2px;
}

tr.prop-row:hover .remove-col i {
    opacity: 0.45;
}

.remove-col i:hover {
    opacity: 1 !important;
    background-color: var(--bg-tertiary);
}
</style>
