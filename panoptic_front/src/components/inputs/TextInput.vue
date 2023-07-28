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
    'blur': undefined,
    'focus': undefined
})
const elem = ref(null)
const isFocus = ref(false)
const minHeight = computed(() => {
    // return '0px'
    return (props.minHeight - 4) + 'px'
})


function focus() {
    elem.value.focus()
    emit('focus')
}

defineExpose({
    focus,
    isFocus
})



let height = 0

function input(value: string) {
    emit('update:modelValue', value)
    updateHeight()
}

function updateHeight() {
    nextTick(() => {
        if (!elem.value) return
        let newHeight = elem.value.$refs.element.clientHeight
        if (height != newHeight) {
            emit('update:height', newHeight + 8)
        }
        height = newHeight
    })
}



onMounted(() => {
    updateHeight()
})
watch(() => props.width, () => {
    updateHeight()
})
watch(() => props.modelValue, () => {
    input(props.modelValue)
})
</script>

<template>
    <div :style="{ width: props.width + 'px', minHeight: minHeight }" class="container m-0 p-0" :class="isFocus ? 'focus':'container'" @click="elem.focus()">
        <ContentEditable ref="elem" :tag="props.tag" @update:model-value="input" :model-value="props.modelValue"
            :no-html="props.noHtml" :no-nl="props.noNl" :contenteditable="props.contenteditable"
            :style="{ width: props.width + 'px'}" class="contenteditable"
            @keydown.escape="e => e.target.blur()" @focus="isFocus = true; emit('focus')"
            @blur="isFocus = false; emit('blur');" />
    </div>
</template>

<style scoped>
.contenteditable {
    white-space: break-spaces;
    padding-left: 2px;
    padding-right: 2px;
    box-sizing:content-box;
}

[contenteditable]:focus {
    outline: 0px solid transparent;
}

.container {
    cursor: text;
    border: 2px solid white;
    border-radius: 5px;
}

.focus {
    border: 2px solid blue;
    border-radius: 5px;
}

</style>
