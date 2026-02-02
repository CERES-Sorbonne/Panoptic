<script setup lang="ts">
import { PropertyType } from '@/data/models';
import { computed } from 'vue';

import PropertyIcon from '../properties/PropertyIcon.vue';
import wTT from '../tooltips/withToolTip.vue'
import { isTag } from '@/utils/utils';
import { useDataStore } from '@/data/dataStore';
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
    return data.propertyList.filter(p => p.id >= 0)
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
    <div class="p-1"><b>{{ $t('modals.tagging.title') }}</b></div>
    <table class="">
        <tbody style="border-top: 1px solid var(--border-color)">
            <tr v-for="property in properties" class="">
                <template v-if="property.id >= 0">
                    <td :class="propertyColor[property.id]" class="text-nowrap" style="padding-top: 4px;">
                        <PropertyIcon :type="property.type" />
                        {{ property.name }}
                    </td>
                    <template v-if="!props.erase.has(property.id)">
                        <td class="w-100" style="padding-top: 4px;">
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
                        <td class="pt1" style="padding-right: 2px;">
                            <div v-if="property.type == PropertyType.multi_tags && props.values[property.id]"
                                class="d-flex border rounded overflow-hidden">
                                <div class="mode-option" :class="{ selected: !props.modes[property.id] }"
                                    @click="setMode(property.id, 0)">{{ $t('dropdown.stamp.add') }}</div>
                                <div class="mode-option" :class="{ selected: props.modes[property.id] == 1 }"
                                    @click="setMode(property.id, 1)">{{ $t('dropdown.stamp.set') }}</div>
                                <div class="mode-option" :class="{ selected: props.modes[property.id] == 2 }"
                                    @click="setMode(property.id, 2)" style="border: none;">{{ $t('dropdown.stamp.del')
                                    }}</div>
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
                        <td class="text-warning" style="text-align: end; padding: 2px 2px;">{{
                            $t("modals.tagging.erase") }}</td>

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
.mode-option {
    border-right: 1px solid var(--border-color);
    padding: 0px 3px;
    cursor: pointer;
}

.selected {
    background-color: var(--selected-grey);
}

.mode-option:hover {
    background-color: var(--light-grey);
}

table {
    border-top: 1px solid var(--border-color);
    border-collapse: separate;
    border-spacing: 0px;
}

tr td {
    border-bottom: 1px solid var(--border-color);
    vertical-align: top;
    margin: 0;
    padding: 2px;
}

.pt1 {
    padding-top: 2.5px;
}

/* Add this to your <style scoped> block */
.action-col {
    width: 30px;          /* Forces a fixed width so it never moves */
    text-align: center;   /* Keeps the icon centered in that space */
    padding: 4px 0;       /* Consistent padding */
    vertical-align: top; /* Optional: centers icon vertically if row height grows */
}
</style>
