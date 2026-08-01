<script setup lang="ts">
// Number property row of a tree cell. Same shape as TreeTextInput: value until clicked,
// then a real input filling the frame.
import { nextTick, ref, watch } from 'vue'
import TreeCellFrame from './TreeCellFrame.vue'
import { PropertyType } from '@/data/models'

const props = defineProps<{
    modelValue?: number
}>()

const emits = defineEmits(['update:modelValue', 'focus', 'blur', 'tab'])

const inputElem = ref(null)
const editing = ref(false)
const localValue = ref<string>(props.modelValue?.toString() ?? '')

watch(() => props.modelValue, v => localValue.value = v?.toString() ?? '')

async function focus() {
    editing.value = true
    await nextTick()
    inputElem.value?.focus()
}

function submit() {
    const parsed = localValue.value === '' ? undefined : Number(localValue.value)
    const value = parsed === undefined || isNaN(parsed) ? undefined : parsed
    if (value === props.modelValue) return
    emits('update:modelValue', value)
}

function onBlur() {
    editing.value = false
    submit()
    emits('blur')
}

function onEscape(e: KeyboardEvent) {
    localValue.value = props.modelValue?.toString() ?? ''
    ;(e.target as HTMLInputElement).blur()
}

defineExpose({ focus })
</script>

<template>
    <TreeCellFrame :type="PropertyType.number" :empty="!editing && props.modelValue === undefined" @click="focus">
        <input v-if="editing" ref="inputElem" class="field" type="number" v-model="localValue"
            @focus="emits('focus')" @blur="onBlur" @keydown.enter.prevent="e => (e.target as HTMLElement).blur()"
            @keydown.esc.stop="onEscape" @keydown.tab.stop.prevent="emits('tab')" />
        <span v-else-if="props.modelValue !== undefined" class="value">{{ props.modelValue }}</span>
    </TreeCellFrame>
</template>

<style scoped>
.field {
    display: block;
    box-sizing: border-box;
    width: 100%;
    appearance: none;
    -webkit-appearance: none;
    padding: 0;
    margin: 0;
    border: none;
    outline: none;
    background: transparent;
    font: inherit;
    line-height: inherit;
    color: inherit;
}

/* the spinners would add a box inside the frame and shift the text */
.field::-webkit-outer-spin-button,
.field::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
}

.value {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}
</style>
