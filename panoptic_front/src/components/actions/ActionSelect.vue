<script setup lang="ts">
import { useProjectStore } from '@/data/projectStore';
import { defineProps, defineEmits, computed } from 'vue'

const project = useProjectStore()

const props = defineProps<{
    modelValue: string
    action: string
}>()
const emits = defineEmits(['update:modelValue'])

const available = computed(() => {
    const action = project.actions.find(a => a.name == props.action)
    const res = action.availableFunctions
    return res
})
</script>

<template>
    <div>
        <select :value="props.modelValue" @change="(e: any) => emits('update:modelValue', e.target.value)">
            <option v-for="f in available" :value="f">
                {{ f }}
            </option>
        </select>
    </div>
</template>

<style scoped></style>