<script setup lang="ts">
import { computed } from 'vue'
import PropertyIcon from '@/components/properties/PropertyIcon.vue';
import { Property, PropertyType, Instance } from '@/data/models';
import { deletedID, useDataStore } from '@/data/dataStore';
import { isTag } from '@/utils/utils';
import TagBadge from '@/components/tagtree/TagBadge.vue';
import DBInput from '@/components/property_inputs/DBInput.vue';
import CellTagInput from '@/components/property_cell_input/CellTagInput.vue';
import CellColorInput from '@/components/property_cell_input/CellColorInput.vue';
import RowTextInput from '@/components/property_row_input/RowTextInput.vue';
import CheckboxInput from '@/components/property_inputs/CheckboxInput.vue';
import RowDateInput from '@/components/property_row_input/RowDateInput.vue';
import RowUrlInput from '@/components/property_row_input/RowUrlInput.vue';
import RowNumberInput from '@/components/property_row_input/RowNumberInput.vue';

const data = useDataStore()

const props = defineProps<{
    instance: Instance,
    property: Property
    width: number
}>()

const emits = defineEmits(['resize', 'update:selected'])

const width = computed(() => (props.width ?? 100) - 22)


</script>

<template>
    <DBInput v-if="props.instance.id != deletedID" :instance="props.instance" :property-id="props.property.id">
        <template #default="{ value, set }">
            <div class="d-flex text-nowrap overflow-hidden" style="height: 26px; line-height: 26px;font-size: 14px;">
                <PropertyIcon v-if="props.property.type != PropertyType.checkbox && property.id > 0"
                    :type="property.type" style="margin-right: 2px;" />

                <CellTagInput v-if="isTag(property.type)" :model-value="value" @update:model-value="set" :no-wrap="true"
                    :auto-focus="true" :can-create="true" :can-customize="true" :property="props.property"
                    :teleport="true" :width="width" />

                <CellColorInput v-else-if="props.property.type == PropertyType.color" :model-value="value"
                    @update:model-value="set" :width="width" :rounded="true" :min-height="20" :teleport="true" :offset="4" />

                <RowNumberInput v-else-if="props.property.type == PropertyType.number" :model-value="value"
                    @update:model-value="set" :width="width" :height="26" :input-offset="3"/>

                <RowTextInput v-else-if="props.property.type == PropertyType.string" :model-value="value"
                    @update:model-value="set" :width="width" :teleport="true" style="height: 25px;" />

                <RowUrlInput v-else-if="props.property.type == PropertyType.url" :model-value="value"
                    @update:model-value="set" :width="width" :teleport="true"/>

                <CheckboxInput v-else-if="props.property.type == PropertyType.checkbox" :model-value="value"
                    @update:model-value="set" :label="props.property.name" :width="width" />

                <RowDateInput v-else-if="props.property.type == PropertyType.date" :model-value="value" :teleport="true"
                    @update:model-value="set" :width="width" />

                <div v-else class="d-flex flex-row overflow-hidden text-nowrap">
                    <PropertyIcon :type="property.type" style="margin-right: 3px;" />
                    <span v-if="property.type == PropertyType._folders">
                        <TagBadge
                            :name="data.folders[data.instances[props.instance.id].properties[props.property.id]].name"
                            :color="-1" />
                    </span>
                    <span v-else>{{ data.instances[props.instance.id].properties[props.property.id] }}</span>
                </div>
            </div>
        </template>
    </DBInput>
</template>

<style scoped></style>