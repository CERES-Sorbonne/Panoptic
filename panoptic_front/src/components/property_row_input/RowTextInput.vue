<script setup lang="ts">
import Dropdown from '@/components/dropdowns/Dropdown.vue';
import { onMounted, ref, watch } from 'vue';
import TextPreview from '@/components/property_preview/TextPreview.vue';
import TextInput from '@/components/property_inputs/TextInput.vue';

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

defineExpose({focus})

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
    let value = localValue.value
    if (value == '') {
        value = undefined
    }
    console.log('emit', value)
    emits('update:modelValue', value)
}

function cancel() {
    loadValue()
}

function focus() {
    previewElem.value.click()
}

onMounted(loadValue)
watch(() => props.modelValue, loadValue)

</script>

<template>
    <Dropdown :offset="props.offset" :no-shadow="true" :teleport="props.teleport" @show="computeSize" @hide="submit"
        placement="bottom-start">
        <template #button>
            <div ref="previewElem" :style="{ width: props.width + 'px' }">
                <TextPreview :text="props.modelValue" style="cursor: pointer; font-size: 14px;" />
            </div>
        </template>
        <template #popup="{ hide }">
            <div class="bg-white" style="font-size: 14px; position: relative; top:0.5px; left:-2px" :style="{ width: widthGoal + 'px' }">
                <TextInput v-model="localValue" :auto-focus="true" :min-height="26" @cancel="cancel(); hide();"
                    @submit="hide()" @blur="hide" @tab="emits('tab')" @focus="emits('focus')"/>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped></style>