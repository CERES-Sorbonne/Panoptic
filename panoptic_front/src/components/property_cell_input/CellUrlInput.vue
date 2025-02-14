<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import TextInput from '../property_inputs/TextInput.vue';
import UrlPreview from '../property_preview/UrlPreview.vue';

const props = withDefaults(defineProps<{
    editable?: boolean
    modelValue?: string
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
const emits = defineEmits(['update:modelValue', 'update:height', 'show', 'hide'])

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

    emits('hide')
}

function emitHeight(height) {
    emits('update:height', height)
}

async function edit() {
    if (localValue.value === undefined) localValue.value = ''
    await nextTick()
    if (!inputElem.value) return
    inputElem.value.focus()

    emits('show')
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
        <UrlPreview v-if="localValue === undefined" :url="props.modelValue" @click="edit"
            style="font-size: inherit; cursor: pointer;" />
        <TextInput v-else :model-value="localValue" @update:model-value="updateLocal" :min-height="props.minHeight"
            :auto-focus="props.autoFocus" :no-shadow="props.noShadow" :url-mode="true" :width="props.width"
            :always-shadow="props.alwaysShadow" :blur-on-enter="props.blurOnEnter" @cancel="cancel" @blur="emitValue"
            @update:height="emitHeight" ref="inputElem" />
    </div>
</template>

<style scoped></style>