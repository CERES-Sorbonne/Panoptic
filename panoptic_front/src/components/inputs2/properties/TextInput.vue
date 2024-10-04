<script setup lang="ts">
import { defineProps, defineEmits } from 'vue'

const props = defineProps<{ modelValue: string }>()
const emits = defineEmits(['update:modelValue'])
defineExpose({ focus })

function focus() {

}
</script>

<template>
    <div>

    </div>
</template>

<style scoped></style>