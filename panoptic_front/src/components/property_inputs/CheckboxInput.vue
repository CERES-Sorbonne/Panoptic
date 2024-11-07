<script setup lang="ts">
import { ref } from 'vue';



const props = defineProps<{
    modelValue?: boolean
    label?: string
}>()

const emits = defineEmits(['update:modelValue'])
defineExpose({ focus })

const inputElem = ref(null)

function focus() {
    if (!inputElem.value) return
    inputElem.value.focus()
}

function emitValue(v) {
    if (!v.target.checked) {
        emits('update:modelValue', undefined)
    } else {
        emits('update:modelValue', true)
    }
}
</script>

<template>
    <div class="d-flex">
        <div><input class="offset-input" type="checkbox" :checked="props.modelValue" @input="emitValue" ref="inputElem">
        </div>
        <div><span v-if="props.label" class="ms-1 bb" @click="emits('update:modelValue', !props.modelValue)">{{ label
                }}</span></div>
    </div>
</template>

<style scoped>
.offset-input {
    position: relative;
    top: 2px;
}
</style>