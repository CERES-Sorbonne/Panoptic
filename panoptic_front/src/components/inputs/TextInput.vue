<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import ContentEditable from '../ContentEditable.vue';

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
    minHeight: { type: Number, default: 30 }

})

const emit = defineEmits({
    'returned': String,
    'update:modelValue': Object,
    'update:height': String,
    'blur': undefined
})
const elem = ref(null)
const isFocus = ref(false)
const minHeight = computed(() => {
    return (props.minHeight - 6)+'px'
})


function focus() {
    elem.value.focus()
}

defineExpose({
    focus,
})



let height = 0

function input(value: string) {
    emit('update:modelValue', value)
    nextTick(() => {
        if(!elem.value) return
        let newHeight = elem.value.$refs.element.clientHeight
        if (height != newHeight) {
            emit('update:height', newHeight + 6)
        }
        height = newHeight
    })
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
    <ContentEditable ref="elem" :tag="props.tag" @update:model-value="input" :model-value="props.modelValue"
        :no-html="props.noHtml" :no-nl="props.noNl" :contenteditable="props.contenteditable"
        :style="{ width: props.width + 'px', minHeight: minHeight}" class="contenteditable"
        @keydown.escape="e => e.target.blur()" @focus="isFocus = true" @blur="isFocus = false; emit('blur');"/>
</template>

<style scoped>
.contenteditable {
    white-space: break-spaces;
    padding-left: 2px;
    padding-right: 2px;
}
</style>
