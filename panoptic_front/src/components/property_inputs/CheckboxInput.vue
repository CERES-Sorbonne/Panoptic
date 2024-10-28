<script setup lang="ts">


const props = defineProps<{
    modelValue?: boolean
    label?: string
}>()

const emits = defineEmits(['update:modelValue'])
function emitValue(v) {
    console.log(v.target.checked)
    if (!v.target.checked) {
        emits('update:modelValue', undefined)
    } else {
        emits('update:modelValue', true)
    }
}
</script>

<template>
    <div class="d-flex">
        <div><input class="offset-input" type="checkbox" :checked="props.modelValue" @input="emitValue"></div>
        <div><span v-if="props.label" class="ms-1 bb" @click="emits('update:modelValue', !props.modelValue)">{{ label }}</span></div>
    </div>
</template>

<style scoped>
.offset-input {
    position: relative;
    top: 2px;
}
</style>