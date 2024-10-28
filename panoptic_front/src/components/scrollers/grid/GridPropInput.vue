<script setup lang="ts">
import CellColorInput from '@/components/property_cell_input/CellColorInput.vue';
import CellTagInput from '@/components/property_cell_input/CellTagInput.vue';
import CellTextInput from '@/components/property_cell_input/CellTextInput.vue';
import CellUrlInput from '@/components/property_cell_input/CellUrlInput.vue';
import CheckboxInput from '@/components/property_inputs/CheckboxInput.vue';
import DBInput from '@/components/property_inputs/DBInput.vue';
import NumberInput from '@/components/property_inputs/NumberInput.vue';
import TextInput from '@/components/property_inputs/TextInput.vue';
import RowDateInput from '@/components/property_row_input/RowDateInput.vue';
import RowNumberInput from '@/components/property_row_input/RowNumberInput.vue';
import TagBadge from '@/components/tagtree/TagBadge.vue';
import { useDataStore } from '@/data/dataStore';
import { Instance, Property, PropertyType } from '@/data/models';
import { isTag } from '@/utils/utils';
import { computed, ref } from 'vue';

const data = useDataStore()

const props = defineProps<{
    instance: Instance
    property: Property
    minHeight: number
    width: number
}>()
const emits = defineEmits(['update:height'])

defineExpose({
    focus
})

const inputElem = ref(null)

const type = computed(() => props.property.type)
function emitHeight(height) {
    emits('update:height', height+4)
}

function focus() {
    if (!inputElem.value) return
    inputElem.value.focus()
}

</script>

<template>
    <div>
        <DBInput :instance="props.instance" :property-id="props.property.id">
            <template #default="{ value, set }">
                <div style="padding: 2px 0px">
                    <CellTagInput v-if="isTag(type)" :property="props.property" :model-value="value"
                        @update:model-value="set" @update:height="emitHeight" :min-height="props.minHeight"
                        :teleport="true" :width="props.width" :auto-focus="true" ref="inputElem" />

                    <CellTextInput v-else-if="type == PropertyType.string" :model-value="value" @update:model-value="set"
                        @update:height="emitHeight" :min-height="props.minHeight" :width="props.width"
                        ref="inputElem" />

                    <CellUrlInput v-else-if="type == PropertyType.url" :model-value="value" @update:model-value="set"
                        @update:height="emitHeight" :min-height="props.minHeight" :url-mode="true" :width="props.width"
                        ref="inputElem" />

                    <CheckboxInput v-else-if="type == PropertyType.checkbox" :model-value="value"
                        @update:model-value="set" @update:height="emitHeight" ref="inputElem" />

                    <CellColorInput v-else-if="type == PropertyType.color" :model-value="value" @update:model-value="set" @update:height="emitHeight"
                        :min-height="props.minHeight+2" :width="props.width" ref="inputElem" :teleport="true" />

                    <RowDateInput v-else-if="type == PropertyType.date" :model-value="value" @update:model-value="set" :teleport="true"
                        @update:height="emitHeight" ref="inputElem" />

                    <RowNumberInput v-else-if="type == PropertyType.number" :model-value="value" @update:model-value="set"
                        @update:height="emitHeight" ref="inputElem" :height="30" />


                    <div v-else-if="property.type == PropertyType._folders" :style="{ height: props.minHeight + 'px' }"
                        class="ps-1 overflow-hidden">
                        <span v-if="props.instance.properties[property.id] != undefined">
                            <TagBadge :name="data.folders[props.instance.properties[property.id]].name" :color="-1" />
                        </span>
                    </div>
                    <TextInput v-else :model-value="value" @update:model-value="set" @update:height="emitHeight"
                        :min-height="props.minHeight" :editable="false" />
                </div>

            </template>
        </DBInput>
    </div>
</template>

<style scoped></style>