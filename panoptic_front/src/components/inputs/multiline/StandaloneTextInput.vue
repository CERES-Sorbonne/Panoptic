<script setup lang="ts">
import TextInput from '@/components/inputs/TextInput.vue'
import { computed, nextTick, onMounted, ref } from 'vue';

const props = defineProps({
    modelValue: undefined,
    width: Number,
    noNl: Boolean,
    urlMode: Boolean,
    noShadow: Boolean,
    alwaysShadow: Boolean,
    onlyNumber: Boolean,
    minHeight: Number,
    autoFocus: Boolean,
})

const emits = defineEmits(['update:height', 'update:modelValue', 'blur', 'focus'])
defineExpose({focus})


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

function onFocus() {
    isFocus.value = true
    emits('focus')
}
async function focus() {
    isFocus.value = true
    await nextTick()
    if(inputElem.value) inputElem.value.focus()
}

function update(value: String) {
    if(value == '') {
        emits('update:modelValue', undefined)
        return
    }
    emits('update:modelValue', value)
}

onMounted(() => {
    if(props.autoFocus) {
        focus()
    }
})

</script>

<template>
    <div>
        <span v-show="!props.autoFocus && (localValue == '' && !isFocus)" class="text-secondary" @click="focus" style="cursor: pointer;">None...</span>
        <TextInput v-show="props.autoFocus || isFocus || localValue != ''" tag="div" :editable="true" :no-html="true" :model-value="localValue"
            @update:model-value="update" :width="props.width"
            @update:height="h => emits('update:height', h)" :min-height="props.minHeight" :no-nl="props.noNl"
            :url-mode="props.urlMode" @blur="blur" :only-number="props.onlyNumber" :no-shadow="props.noShadow"
            :always-shadow="props.alwaysShadow" ref="inputElem" @focus="onFocus" :blur-on-enter="true"/>
    </div>
</template>