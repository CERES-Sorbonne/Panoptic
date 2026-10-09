<script setup lang="ts">
import CellColorInput from '@/components/property_cell_input/CellColorInput.vue';
import CellTagInput from '@/components/property_cell_input/CellTagInput.vue';
import CellTextInput from '@/components/property_cell_input/CellTextInput.vue';
import CellUrlInput from '@/components/property_cell_input/CellUrlInput.vue';
import CheckboxInput from '@/components/property_inputs/CheckboxInput.vue';
import DBInput from '@/components/property_inputs/DBInput.vue';
import TextInput from '@/components/property_inputs/TextInput.vue';
import RowDateInput from '@/components/property_row_input/RowDateInput.vue';
import RowNumberInput from '@/components/property_row_input/RowNumberInput.vue';
import TagBadge from '@/components/tagtree/TagBadge.vue';
import { useDataStore } from '@/data/stores/dataStore';
import { Property, PropertyType } from '@/data/models';
import { InstanceEntry } from '@/data/stores/instanceStore';
import { isNumeric, isTag } from '@/utils/utils';
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { keyState } from '@/data/composables/keyState';

const data = useDataStore()

const props = defineProps<{
    instance: InstanceEntry
    property: Property
    minHeight: number
    width: number
    // Show the value on one line, clipped (for rows of a fixed height). Editing is unchanged.
    singleLine?: boolean
    // Editor mode (the grid, which draws its cells with GridCellView and mounts this only for the
    // cell being edited): opens the editor on mount, and reports `close` once the edit is over and
    // `tab` (with whether shift was held) when Tab is pressed in it.
    open?: boolean
}>()
const emits = defineEmits<{
    'update:height': [height: number]
    close: []
    tab: [backwards: boolean]
}>()

defineExpose({
    focus,
    waitForDbAction
})

const dbInput = ref(null)
const inputElem = ref(null)

const type = computed(() => props.property.type)
function emitHeight(height) {
    emits('update:height', height+4)
}

function focus() {
    if (!inputElem.value) return
    inputElem.value.focus()
}

async function waitForDbAction() {
    return dbInput.value.waitForDbAction()
}

function onClose() {
    if (props.open) emits('close')
}

function onTab() {
    if (props.open) emits('tab', keyState.shift)
}

// The checkbox has no edit to finish: reached by Tab, it is done once focus leaves it.
function onCheckboxFocusOut() {
    onClose()
}

onMounted(async () => {
    if (!props.open) return
    // the dropdown editors place their popup on the cell, so let it be laid out first
    await nextTick()
    focus()
})

// Unmounted by its row before it closed (the row was recycled to another image): the cell must
// not stay open, or its editor would pop up again whenever that image is next drawn. A second
// close is a no-op for the grid.
onBeforeUnmount(onClose)

</script>

<template>
    <div>
        <DBInput :instance="props.instance" :property-id="props.property.id" ref="dbInput">
            <template #default="{ value, set }">
                <div style="padding: 2px 0px">
                    <CellTagInput v-if="isTag(type)" :property="props.property" :model-value="value" :instance-id="props.instance.id" :can-create="true" :can-delete="true" :can-customize="true"
                        :no-wrap="props.singleLine" @update:model-value="set" @update:height="emitHeight" :min-height="props.minHeight"
                        :teleport="true" :width="props.width" :auto-focus="true" ref="inputElem"
                        @hide="onClose" @tab="onTab" />

                    <CellTextInput v-else-if="type == PropertyType.string" :model-value="value" @update:model-value="set"
                        @update:height="emitHeight" :min-height="props.minHeight" :width="props.width"
                        ref="inputElem" @hide="onClose" @tab="onTab" />

                    <CellUrlInput v-else-if="type == PropertyType.url" :model-value="value" @update:model-value="set"
                        @update:height="emitHeight" :min-height="props.minHeight" :url-mode="true" :width="props.width"
                        ref="inputElem" @hide="onClose" @tab="onTab" />

                    <CheckboxInput v-else-if="type == PropertyType.checkbox" :model-value="value"
                        @update:model-value="set" @update:height="emitHeight" ref="inputElem"
                        @focusout="onCheckboxFocusOut" @keydown.tab="e => { if (props.open) { e.preventDefault(); onTab() } }" />

                    <CellColorInput v-else-if="type == PropertyType.color" :model-value="value" @update:model-value="set" @update:height="emitHeight"
                        :min-height="props.minHeight -2" :width="props.width" ref="inputElem" :teleport="true"
                        @hide="onClose" />

                    <RowDateInput v-else-if="type == PropertyType.date" :model-value="value" @update:model-value="set" :teleport="true"
                        @update:height="emitHeight" ref="inputElem" @hide="onClose" />

                    <RowNumberInput v-else-if="type == PropertyType.number" :model-value="value" @update:model-value="set"
                        @update:height="emitHeight" ref="inputElem" :height="27" @hide="onClose" @tab="onTab" />


                    <div v-else-if="property.type == PropertyType._folders" :style="{ height: props.minHeight + 'px' }"
                        class="ps-1 overflow-hidden">
                        <span v-if="props.instance.properties[property.id] != undefined">
                            <TagBadge :name="data.folders[props.instance.properties[property.id]].name" :color="-1" />
                        </span>
                    </div>
                    <!-- Read-only values: on one line, a plain text node is all it takes. -->
                    <div v-else-if="props.singleLine" class="text-truncate" style="padding: 0 2px;" :class="{ num: isNumeric(type) }">{{ value }}</div>
                    <TextInput v-else :model-value="value" @update:model-value="set" @update:height="emitHeight"
                        :min-height="props.minHeight" :editable="false" :class="{ num: isNumeric(type) }" />
                </div>

            </template>
        </DBInput>
    </div>
</template>

<style scoped></style>