<script setup lang="ts">
import { Property, PropertyType } from '@/data/models';
import { isTag } from '@/utils/utils';
import { defineProps, defineEmits } from 'vue'
import PropertyIcon from '../properties/PropertyIcon.vue';
import RowTextInput from '../property_row_input/RowTextInput.vue';
import CellTagInput from '../property_cell_input/CellTagInput.vue';
import CellColorInput from '../property_cell_input/CellColorInput.vue';
import RowUrlInput from '../property_row_input/RowUrlInput.vue';
import CheckboxInput from '../property_inputs/CheckboxInput.vue';
import RowDateInput from '../property_row_input/RowDateInput.vue';
import RowNumberInput from '../property_row_input/RowNumberInput.vue';

const props = defineProps<{
    modelValue?: any
    property: Property
    width: number
}>()
const emits = defineEmits(['update:modelValue'])

function set(value) {
    emits('update:modelValue', value)
}

</script>

<template>
    <div class="d-flex text-nowrap overflow-hidden" style="font-size: 14px;">
        <PropertyIcon v-if="props.property.type != PropertyType.checkbox" :type="property.type"
            style="margin-right: 2px;" />

        <CellTagInput v-if="isTag(property.type)" :model-value="props.modelValue" @update:model-value="set"
            :no-wrap="true" :auto-focus="true" :can-create="true" :can-customize="true" :property="props.property"
            :teleport="false" :width="props.width" />

        <CellColorInput v-else-if="props.property.type == PropertyType.color" :model-value="props.modelValue"
            @update:model-value="set" :width="props.width" :rounded="true" :min-height="20" :teleport="false"
            :offset="4" />

        <RowNumberInput v-else-if="props.property.type == PropertyType.number" :model-value="props.modelValue"
            @update:model-value="set" :width="props.width" :height="26" :input-offset="3" />

        <RowUrlInput v-else-if="props.property.type == PropertyType.url" :model-value="props.modelValue"
            @update:model-value="set" :width="props.width" :offset="-22" />

        <CheckboxInput v-else-if="props.property.type == PropertyType.checkbox" :model-value="props.modelValue"
            @update:model-value="set" :label="props.property.name" :width="props.width" />

        <RowDateInput v-else-if="props.property.type == PropertyType.date" :model-value="props.modelValue"
            :teleport="false" @update:model-value="set" :width="props.width" />

        <RowTextInput v-else-if="props.property.type == PropertyType.string" :model-value="props.modelValue"
            @update:model-value="set" :width="props.width" :offset="-22"/>
    </div>
</template>

<style scoped></style>