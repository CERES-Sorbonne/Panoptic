<script setup lang="ts">
// Date property row of a tree cell: formatted value in the frame, the shared DateInput in a
// popup on click. Only the row shell is new — the calendar itself is the existing editor.
import { ref, watch } from 'vue'
import TreeCellFrame from './TreeCellFrame.vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import DateInput from '@/components/property_inputs/DateInput.vue'
import DatePreview from '@/components/property_preview/DatePreview.vue'
import { PropertyType } from '@/data/models'

const props = defineProps<{
    modelValue?: string
}>()

const emits = defineEmits(['update:modelValue', 'focus', 'blur', 'tab'])

const dropdownElem = ref(null)
const isOpen = ref(false)
const localValue = ref(props.modelValue)

watch(() => props.modelValue, v => localValue.value = v)

function focus() {
    dropdownElem.value?.show()
}

// The icon stops the cell's click, so the dropdown's own trigger never sees it: it has to be
// driven by hand here — and as a toggle, like a second click on the row.
function toggle() {
    if (isOpen.value) dropdownElem.value?.hide()
    else focus()
}

function submit(hide) {
    if (localValue.value !== props.modelValue) emits('update:modelValue', localValue.value)
    hide()
}

function cancel() {
    localValue.value = props.modelValue
}
</script>

<template>
    <Dropdown ref="dropdownElem" :offset="-26" :teleport="true" placement="bottom-start" @esc="cancel"
        @show="isOpen = true; emits('focus')" @hide="isOpen = false; emits('blur')">
        <template #button>
            <!-- focus lives in the teleported popup, so :focus-within never fires here -->
            <TreeCellFrame :type="PropertyType.date" :active="isOpen" :empty="!props.modelValue"
                @icon-click="toggle">
                <DatePreview v-if="props.modelValue" :date="props.modelValue" class="value" />
            </TreeCellFrame>
        </template>
        <template #popup="{ hide }">
            <div class="p-2">
                <DateInput v-model="localValue" :extended="true" :auto-focus="true" @cancel="cancel(); hide()"
                    @submit="submit(hide)" />
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
/* floating-vue's trigger wrapper is inline-block: its line box would add descender space
   under the row, which the non-dropdown property rows don't have */
:deep(.v-popper) {
    display: block;
}

.value {
    font-size: inherit;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}
</style>
