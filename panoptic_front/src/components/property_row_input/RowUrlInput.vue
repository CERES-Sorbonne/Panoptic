<script setup lang="ts">
import Dropdown from '@/components/dropdowns/Dropdown.vue';
import { onMounted, ref, watch } from 'vue';
import TextInput from '@/components/property_inputs/TextInput.vue';
import UrlPreview from '../property_preview/UrlPreview.vue';
import { keyState } from '@/data/keyState';

const props = withDefaults(defineProps<{
    modelValue?: string
    width?: number
    height?: number
    teleport?: boolean
    offset?: number
}>(), {
    offset: -24
})

const emits = defineEmits(['update:modelValue', 'focus', 'tab'])

defineExpose({
    focus
})

const previewElem = ref(null)
const widthGoal = ref(0)
const localValue = ref(undefined)

function loadValue() {
    localValue.value = props.modelValue
}

function onShow() {
    computeSize()
    emits('focus')
}

function computeSize() {
    var canvas = document.createElement('canvas');
    var ctx = canvas.getContext("2d");
    ctx.font = "12px Arial";
    var length = ctx.measureText(props.modelValue).width;
    widthGoal.value = 200
    if (length > 500) {
        widthGoal.value = 200
    }
    if (length > 800) {
        widthGoal.value = 300
    }
    if (length > 1000) {
        widthGoal.value = 400
    }

    let prevElem = previewElem.value
    if (prevElem && prevElem.offsetWidth > widthGoal.value) {
        widthGoal.value = prevElem.offsetWidth
    }
}

function submit() {
    emits('update:modelValue', localValue.value)
}

function cancel() {
    loadValue()
}

function clickUrl(e) {
    if (keyState.ctrl) {
        e.preventDefault()
        e.stopPropagation()
    }
}

function focus() {
    previewElem.value.click()
}

onMounted(loadValue)
watch(() => props.modelValue, loadValue)

</script>

<template>
    <Dropdown :offset="props.offset" :no-shadow="true" :teleport="props.teleport" @show="onShow" @hide="submit"
        placement="bottom-start">
        <template #button>
            <div ref="previewElem" style="" :style="{ width: props.width + 'px' }">
                <UrlPreview :url="props.modelValue" class="row-preview" style="cursor: pointer; font-size: 14px;"
                    @click="clickUrl" />
            </div>
        </template>
        <template #popup="{ hide }">
            <div class="bg-white" style="font-size: 14px; position: relative; top:0.5px; left:0px"
                :style="{ width: widthGoal + 'px' }">
                <TextInput v-model="localValue" :auto-focus="true" :min-height="26" @cancel="cancel(); hide();"
                    @submit="hide()" @blur="hide" :url-mode="true" @tab="emits('tab')" />
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
/* .row-preview {
    font-size: 12px;
} */
</style>