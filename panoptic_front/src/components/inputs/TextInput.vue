<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';

import contenteditable from 'vue-contenteditable'

const props = defineProps({
    'tag': String,
    'contenteditable': {
        type: [Boolean, String],
        default: true,
    },
    'modelValue': String,
    'noHtml': {
        type: Boolean,
        default: true,
    },
    'noNl': {
        type: Boolean,
        default: false,
    },
    width: Number

})

const emit = defineEmits({
    'returned': String,
    'update:modelValue': String,
    'update:height': String
})

const elem = ref(null)

let height = 0

function input(value) {
    emit('update:modelValue', value)

    let newHeight = elem.value.$refs.element.clientHeight
    if(height != newHeight) {
        emit('update:height', newHeight+6)
    }
    height = newHeight
}

onMounted(() => {
    input(props.modelValue)
})
watch(() => props.width, () => {
    input(props.modelValue)
})

</script>

<template>
    <contenteditable ref="elem" :tag="props.tag" @update:model-value="input"
        :model-value="props.modelValue" :no-html="props.noHtml" :no-nl="props.noNl" :contenteditable="props.contenteditable"
        :style="'width: ' + props.width+'px;'" class="contenteditable"/>
</template>

<style scoped>

.contenteditable {
    white-space: pre-wrap;
    padding-left: 1px;
}

</style>
