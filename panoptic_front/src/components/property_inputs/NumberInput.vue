<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';


const props = defineProps<{
    modelValue?: number | string
    width?: number
}>()
const emits = defineEmits(['update:modelValue', 'focus', 'blur'])
defineExpose({ focus })

const isFocus = ref(false)
const localValue = ref(undefined)
const inputElem = ref(null)

function loadValue() {
    localValue.value = !isNaN(Number(props.modelValue)) ? props.modelValue : undefined
}

function emit() {
    if (localValue.value === undefined || localValue.value === '') {
        emits('update:modelValue', undefined)
        return
    }
    emits('update:modelValue', localValue.value)
}

function onFocus() {
    isFocus.value = true
    emits('focus')
}

function onBlur() {
    isFocus.value = false
    emit()
    emits('blur')
}

function cancel() {
    loadValue()
    forceBlur()
}

function forceBlur() {
    inputElem.value.blur()
}

function focus() {
    if (!inputElem.value) return
    inputElem.value.focus()
}

onMounted(loadValue)
watch(() => props.modelValue, loadValue)

</script>

<template>
    <div>
        <input style="line-height: inherit" :class="isFocus ? 'dropdown-input' : ''" type="number" v-model="localValue"
            :style="{ width: props.width ? (props.width - 2) + 'px' : '100%' }" @focus="onFocus" @blur="onBlur"
            @keydown.esc="cancel" @keydown.enter="forceBlur" ref="inputElem">
    </div>
</template>

<style scoped>
/* for chrome */
input[type=number]::-webkit-inner-spin-button,
input[type=number]::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
}


/* for mozilla */
input[type=number] {
    border: none;
    text-align: left;
    -moz-appearance: textfield;
    width: 100%;
    border-radius: 5px;
}

.nb-border {
    border: 1px solid var(--border-color) !important;
    border-radius: 5px;
}
</style>