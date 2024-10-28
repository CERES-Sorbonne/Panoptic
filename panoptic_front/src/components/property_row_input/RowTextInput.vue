<script setup lang="ts">
import Dropdown from '@/components/dropdowns/Dropdown.vue';
import { onMounted, ref, watch } from 'vue';
import TextPreview from '@/components/property_preview/TextPreview.vue';
import TextInput from '@/components/property_inputs/TextInput.vue';

const props = defineProps<{
    modelValue?: string
    width?: number
    height?: number
}>()

const emits = defineEmits(['update:modelValue'])

const previewElem = ref(null)
const widthGoal = ref(0)
const localValue = ref(undefined)

function loadValue() {
    localValue.value = props.modelValue
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
    loadValue()
}

function submit() {
    emits('update:modelValue', localValue.value)
}

function cancel() {
    loadValue()
}

onMounted(loadValue)
watch(() => props.modelValue, loadValue)

</script>

<template>
    <Dropdown :offset="-20" :no-shadow="true" :teleport="true" @show="computeSize" @hide="submit">
        <template #button>
            <div ref="previewElem" :style="{width: props.width+'px'}">
                <TextPreview :text="props.modelValue" style="cursor: pointer;" />
            </div>
        </template>
        <template #popup="{hide}">
            <div class="" style="font-size: 12px; line-height: 22px;" :style="{ width: widthGoal + 'px' }">
                <TextInput v-model="localValue" :auto-focus="true" @cancel="cancel(); hide();" @submit="hide()" @blur="hide" />
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
</style>