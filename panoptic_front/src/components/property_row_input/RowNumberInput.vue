<script setup lang="ts">
import { ref, onMounted, watch, nextTick, computed } from 'vue'
import NumberPreview from '../property_preview/NumberPreview.vue';
import NumberInput from '../property_inputs/NumberInput.vue';

const props = defineProps<{
    modelValue?: number
    width?: number
    height?: number
    inputOffset?: number
}>()
const emits = defineEmits(['update:modelValue'])

defineExpose({ focus })

const inputElem = ref(null)
const localValue = ref(undefined)

const inputOffset = ref(props.inputOffset ?? 0)
const inputLineHeight = computed(() => props.height - 8)

function loadValue() {
    localValue.value = props.modelValue
}

function emitValue(value) {
    if (value === '') value = undefined
    else if (isNaN(value)) value = undefined

    emits('update:modelValue', value)
}

async function edit() {
    if (localValue.value === undefined) localValue.value = ''
    await nextTick()
    if (!inputElem.value) return
    inputElem.value.focus()
}

function focus() {
    edit()
}

onMounted(loadValue)
watch(props, loadValue)

</script>

<template>
    <div>
        <NumberPreview v-if="localValue === undefined" :number="props.modelValue"
            style="font-size: inherit; cursor: pointer;" @click="edit" :width="props.width" />
        <div v-else :style="{ lineHeight: inputLineHeight + 'px', top: inputOffset + 'px', position: 'relative' }">
            <NumberInput :model-value="props.modelValue" @update:model-value="emitValue" :width="props.width"
                @keydown.esc.stop @blur="loadValue" ref="inputElem" class="reduced" />
        </div>
    </div>
</template>

<style scoped></style>