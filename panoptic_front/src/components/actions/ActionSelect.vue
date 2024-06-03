<script setup lang="ts">
import { useActionStore } from '@/data/actionStore';
import { objValues } from '@/utils/utils';
import { defineProps, defineEmits, computed } from 'vue'

const actions = useActionStore()

const props = defineProps<{
    modelValue: string
    action: string
}>()
const emits = defineEmits(['update:modelValue'])

const available = computed(() => {
    const valid = objValues(actions.index).filter(a => a.hooks.includes(props.action))
    return valid.map(a => a.id)
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