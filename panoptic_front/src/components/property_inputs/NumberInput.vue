<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';


const props = defineProps<{
    modelValue?: number | string
}>()
const emits = defineEmits(['update:modelValue'])
const localValue = ref(undefined)

function loadValue() {
    localValue.value = !isNaN(Number(props.modelValue)) ? props.modelValue : undefined
}

function emit() {
    if (localValue.value == undefined || localValue.value == '') {
        emits('update:modelValue', undefined)
        return
    }
    emits('update:modelValue', localValue.value)
}

onMounted(loadValue)
watch(() => props.modelValue, loadValue)

</script>

<template>
    <div>
        <input class="" type="number" v-model="localValue" @input="emit()">
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
    text-align: center;
    -moz-appearance: textfield;
    width: 100%;
}

.nb-border {
    border: 1px solid var(--border-color) !important;
    border-radius: 5px;
}
</style>