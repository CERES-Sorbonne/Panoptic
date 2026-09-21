<script setup lang="ts">
import { isReadonly, PropertyType } from '@/data/models';
import { computed } from 'vue';

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

const properties = computed(() => {
    return data.propertyList.filter(p => p.id >= 0 && !isReadonly(p))
})

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
    <table class="stamp-table">
        <tbody>
            <tr v-for="property in properties" class="">
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

tr:hover td {
    background-color: var(--light-grey);
}

tr td:first-child {
    border-radius: 6px 0 0 6px;
}

tr td:last-child {
    border-radius: 0 6px 6px 0;
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
    background-color: var(--light-grey);
    border-radius: 6px;
    padding: 2px;
    gap: 2px;
}

.mode-option {
    padding: 0px 6px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    line-height: 18px;
    opacity: 0.7;
}

.mode-option:hover {
    opacity: 1;
}

.selected {
    background-color: var(--white, #fff);
    opacity: 1;
    font-weight: 500;
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
    background-color: var(--selected-grey);
}
</style>
