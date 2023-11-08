<script setup lang="ts">
import TextInput from '@/components/inputs/TextInput.vue'
import { computed, nextTick, ref } from 'vue';

const props = defineProps({
    modelValue: undefined,
    width: Number,
    noNl: Boolean,
    urlMode: Boolean,
    noShadow: Boolean,
    alwaysShadow: Boolean,
    onlyNumber: Boolean,
    minHeight: Number
})

const emits = defineEmits(['update:height', 'update:modelValue', 'blur', 'focus'])

const inputElem = ref(null)
const isFocus = ref(false)

const localValue = computed(() => {
    if(props.modelValue) return props.modelValue
    return ''
})

function blur() {
    isFocus.value = false
    emits('blur')
}

function focus() {
    isFocus.value = true
    emits('focus')
}
function forceFocus() {
    focus()
    nextTick(() => inputElem.value.focus())
}

</script>

<template>
    <div>
        <span v-show="localValue == '' && !isFocus" class="text-secondary" @click="forceFocus" style="cursor: pointer;">None...</span>
        <TextInput v-show="isFocus || localValue != ''" tag="div" :editable="true" :no-html="true" :model-value="localValue"
            @update:model-value="v => emits('update:modelValue', v)" :width="props.width"
            @update:height="h => emits('update:height', h)" :min-height="props.minHeight" :no-nl="props.noNl"
            :url-mode="props.urlMode" @blur="blur" :only-number="props.onlyNumber" :no-shadow="props.noShadow"
            :always-shadow="props.alwaysShadow" ref="inputElem" @focus="focus"/>
    </div>
</template>