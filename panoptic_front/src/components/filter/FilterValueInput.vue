<script setup lang="ts">
import { Property, PropertyType } from '@/data/models';
import { isTag } from '@/utils/utils';
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
        <CellTagInput v-if="isTag(property.type)" :model-value="props.modelValue" @update:model-value="set"
            :no-wrap="true" :auto-focus="true" :can-create="false" :can-customize="false" :property="props.property"
            :teleport="false" :width="props.width" class="sb" :force-multi="true"/>

        <CellColorInput v-else-if="props.property.type == PropertyType.color" :model-value="props.modelValue"
            @update:model-value="set" :width="props.width" :rounded="true" :min-height="22" :teleport="false"
            :offset="2" class="sb" />

        <RowNumberInput v-else-if="props.property.type == PropertyType.number" :model-value="props.modelValue"
            @update:model-value="set" :width="props.width" :height="26" :input-offset="0" class="sb" />

        <RowUrlInput v-else-if="props.property.type == PropertyType.url" :model-value="props.modelValue"
            @update:model-value="set" :width="props.width" :offset="-22" class="sb" />

        <CheckboxInput v-else-if="props.property.type == PropertyType.checkbox" :model-value="props.modelValue"
            @update:model-value="set" :label="props.property.name" :width="props.width" class="sb" />

        <RowDateInput v-else-if="props.property.type == PropertyType.date" :model-value="props.modelValue"
            :teleport="false" @update:model-value="set" :width="props.width" class="sb" />

        <RowTextInput v-else :model-value="props.modelValue"
            @update:model-value="set" :width="props.width" :offset="-22" class="sb" />
    </div>
</template>

<style scoped></style>