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
    width: Number,
    minHeight: {type: Number, default: 30}

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
watch(() => props.modelValue, () => {
    input(props.modelValue)
})

</script>

<template>
    <contenteditable ref="elem" :tag="props.tag" @update:model-value="input"
        :model-value="props.modelValue" :no-html="props.noHtml" :no-nl="props.noNl" :contenteditable="props.contenteditable"
        :style="{width: 'calc(100% - 20px)', minHeight: props.minHeight-6+'px'}" class="contenteditable"
        @keydown.escape="e => e.target.blur()"
        />
</template>

<style scoped>

.contenteditable {
    white-space: break-spaces;
    padding-left: 2px;
    padding-right: 2px;
}

</style>
