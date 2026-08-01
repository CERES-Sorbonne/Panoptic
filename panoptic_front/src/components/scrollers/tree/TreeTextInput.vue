<script setup lang="ts">
// Text / url property row of a tree cell: shows the value, turns into a real input on click.
// Built for this scroller only — the shared Row*/Cell* inputs size themselves in absolute
// pixels from a width prop, which is exactly what a cell-filling row must not do.
import { nextTick, ref, watch } from 'vue'
import TreeCellFrame from './TreeCellFrame.vue'
import { PropertyType } from '@/data/models'
import { keyState } from '@/data/keyState'

const props = defineProps<{
    modelValue?: string
    // string or url; url values open in a new tab on ctrl/cmd-click instead of editing
    type: PropertyType
}>()

const emits = defineEmits(['update:modelValue', 'focus', 'blur', 'tab'])

const inputElem = ref(null)
const editing = ref(false)
const localValue = ref(props.modelValue ?? '')

watch(() => props.modelValue, v => localValue.value = v ?? '')

async function focus() {
    editing.value = true
    await nextTick()
    inputElem.value?.focus()
}

function onClick() {
    if (props.type == PropertyType.url && props.modelValue && (keyState.ctrl || keyState.cmd)) {
        const url = props.modelValue.startsWith('http') ? props.modelValue : 'http://' + props.modelValue
        window.open(url, '_blank')?.focus()
        return
    }
    focus()
}

function submit() {
    const value = localValue.value === '' ? undefined : localValue.value
    if (value === props.modelValue) return
    emits('update:modelValue', value)
}

function onBlur() {
    editing.value = false
    submit()
    emits('blur')
}

function onEscape(e: KeyboardEvent) {
    localValue.value = props.modelValue ?? ''
    ;(e.target as HTMLInputElement).blur()
}

defineExpose({ focus })
</script>

<template>
    <TreeCellFrame :type="props.type" :empty="!editing && !props.modelValue" @click="onClick">
        <input v-if="editing" ref="inputElem" class="field" type="text" v-model="localValue"
            @focus="emits('focus')" @blur="onBlur" @keydown.enter.prevent="e => (e.target as HTMLElement).blur()"
            @keydown.esc.stop="onEscape" @keydown.tab.stop.prevent="emits('tab')" />
        <span v-else-if="props.modelValue" class="value"
            :class="{ url: props.type == PropertyType.url }">{{ props.modelValue }}</span>
    </TreeCellFrame>
</template>

<style scoped>
/* The input replaces the value in place, so it must bring no box of its own: same font, same
   metrics, no border, no padding — nothing may move when it appears. */
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

.value {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}

.url {
    color: var(--blue);
}
</style>
