<script setup lang="ts">
import { defineProps, defineEmits, ref, onMounted, watch, nextTick } from 'vue'
import TextInput from '../property_inputs/TextInput.vue';
import TextPreview from '../property_preview/TextPreview.vue';

const props = withDefaults(defineProps<{
    editable?: boolean
    modelValue?: string | number
    width?: number
    minHeight?: number
    noShadow?: boolean
    alwaysShadow?: boolean
    blurOnEnter?: boolean
    autoFocus?: boolean
}>(), {
    blurOnEnter: true,
    autoFocus: false
})
const emits = defineEmits(['update:modelValue', 'update:height'])

defineExpose({ focus })

const inputElem = ref(null)
const localValue = ref(undefined)


function loadValue() {
    localValue.value = props.modelValue
}

async function emitValue() {
    // be sure to catch cancel event before
    await nextTick()
    if (localValue.value === '' || localValue.value === undefined) {
        emits('update:modelValue', undefined)
    } else {
        emits('update:modelValue', localValue.value)
    }

    await nextTick()
    if (localValue.value == '') {
        localValue.value = undefined
    }
}

function emitHeight(height) {
    emits('update:height', height)
}

async function edit() {
    if (localValue.value === undefined) localValue.value = ''
    await nextTick()
    if (!inputElem.value) return
    inputElem.value.focus()
}

function focus() {
    edit()
}

function cancel() {
    loadValue()
}

function updateLocal(value) {
    if (value === undefined) value = ''
    localValue.value = value
}

onMounted(loadValue)
watch(props, loadValue)

</script>

<template>
    <div>
        <TextPreview v-if="localValue === undefined" :text="props.modelValue" @click="edit"
            style="font-size: inherit; cursor: pointer; "/>
        <TextInput v-else :model-value="localValue" @update:model-value="updateLocal" :min-height="props.minHeight"
            :auto-focus="props.autoFocus" :no-shadow="props.noShadow"
            :always-shadow="props.alwaysShadow" :blur-on-enter="props.blurOnEnter" @cancel="cancel()" @blur="emitValue"
            @update:height="emitHeight" ref="inputElem" />
    </div>
</template>

<style scoped></style>