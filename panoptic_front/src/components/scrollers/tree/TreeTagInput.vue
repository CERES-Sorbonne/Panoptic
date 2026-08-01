<script setup lang="ts">
// Tag property row of a tree cell. The tag picker itself is the shared CellTagInput (tag
// creation, linking, colours — far more than a row shell should own); this only wraps it in
// the tree frame and lets it fill the cell instead of being sized in pixels.
import { ref } from 'vue'
import TreeCellFrame from './TreeCellFrame.vue'
import CellTagInput from '@/components/property_cell_input/CellTagInput.vue'
import { Property } from '@/data/models'

const props = defineProps<{
    modelValue?: any
    property: Property
    instanceId: number
}>()

const emits = defineEmits(['update:modelValue', 'focus', 'blur', 'tab'])

const inputElem = ref(null)
const isOpen = ref(false)

function focus() {
    inputElem.value?.focus()
}

defineExpose({ focus })
</script>

<template>
    <!-- focus lives in the teleported popup, so the frame is told when to look active -->
    <TreeCellFrame :type="props.property.type" :active="isOpen" @click="focus">
        <!-- no :width — it defaults to 100% of the frame -->
        <CellTagInput ref="inputElem" :model-value="props.modelValue" :property="props.property"
            :instance-id="props.instanceId" @update:model-value="v => emits('update:modelValue', v)" :no-wrap="true"
            :auto-focus="true" :can-create="true" :can-customize="true" :teleport="true"
            @show="isOpen = true; emits('focus')" @hide="isOpen = false; emits('blur')"
            @tab="emits('tab')" />
    </TreeCellFrame>
</template>

<style scoped></style>
