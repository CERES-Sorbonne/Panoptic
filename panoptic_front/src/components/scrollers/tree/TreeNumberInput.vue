<script setup lang="ts">
// Number property row of a tree cell. Same shape as TreeTextInput: value until clicked,
// then a real input filling the frame.
import { computed, nextTick, ref, watch } from 'vue'
import TreeCellFrame from './TreeCellFrame.vue'
import { PropertyType } from '@/data/models'

const props = defineProps<{
    modelValue?: number
}>()

const emits = defineEmits(['update:modelValue', 'focus', 'blur', 'tab'])

const inputElem = ref(null)
const editing = ref(false)

// "No value" covers more than `undefined` here: a group's value can come in as null, and a
// cluster/undecided card can carry a NaN — none of which is a number to show.
const value = computed(() => {
    const v = props.modelValue
    return typeof v === 'number' && !isNaN(v) ? v : undefined
})

const localValue = ref<string>(value.value?.toString() ?? '')

watch(value, v => localValue.value = v?.toString() ?? '')

async function focus() {
    editing.value = true
    await nextTick()
    inputElem.value?.focus()
}

function submit() {
    const parsed = localValue.value === '' ? undefined : Number(localValue.value)
    const next = parsed === undefined || isNaN(parsed) ? undefined : parsed
    if (next === value.value) return
    emits('update:modelValue', next)
}

function onBlur() {
    editing.value = false
    submit()
    emits('blur')
}

function onEscape(e: KeyboardEvent) {
    localValue.value = value.value?.toString() ?? ''
    ;(e.target as HTMLInputElement).blur()
}

defineExpose({ focus })
</script>

<template>
    <TreeCellFrame :type="PropertyType.number" :empty="!editing && value === undefined" @click="focus">
        <input v-if="editing" ref="inputElem" class="field" type="number" v-model="localValue"
            @focus="emits('focus')" @blur="onBlur" @keydown.enter.prevent="e => (e.target as HTMLElement).blur()"
            @keydown.esc.stop="onEscape" @keydown.tab.stop.prevent="emits('tab')" />
        <span v-else-if="value !== undefined" class="value">{{ value }}</span>
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
