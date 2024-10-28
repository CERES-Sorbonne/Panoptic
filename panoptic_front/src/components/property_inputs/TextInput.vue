<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch, withDefaults } from 'vue';
import { keyState } from '@/data/keyState';
import ContentEditable from '../inputs2/utils/ContentEditable.vue';

const props = withDefaults(defineProps<{
    editable?: boolean
    modelValue?: string
    width?: number
    minHeight?: number
    urlMode?: boolean
    noShadow?: boolean
    alwaysShadow?: boolean
    blurOnEnter?: boolean
    autoFocus?: boolean
}>(), {
    editable: true,
    minHeight: 30,
    blurOnEnter: true
})

const emits = defineEmits({
    'update:modelValue': Object,
    'update:height': String,
    'blur': undefined,
    'focus': undefined,
    'submit': undefined,
    'cancel': undefined
})
const elem = ref(null)
const isFocus = ref(false)
const isHover = ref(false)
const minHeight = computed(() => {
    // return '0px'
    return (props.minHeight - 2) + 'px'
})

const localValue = computed(() => props.modelValue ?? '')
const urlMode = computed(() => props.urlMode && keyState.ctrl && isHover.value)

function focus() {
    elem.value.focus()
    emits('focus')
}

defineExpose({
    focus,
    isFocus
})



let height = 0

function input(value: string) {
    if (value == '') value = undefined
    emits('update:modelValue', value)
    updateHeight()
}

function updateHeight() {
    nextTick(() => {
        if (!elem.value) return
        let newHeight = elem.value.$refs.element.clientHeight + 3
        if (height != newHeight) {
            emits('update:height', newHeight)
        }
        height = newHeight
    })
}

function contentClick() {
    if (props.urlMode && keyState.ctrl && props.modelValue) {
        let url = props.modelValue as string
        if (!url.startsWith('http')) {
            url = 'http://' + url
        }
        window.open(url, '_blank').focus()
    }
}

function onEnter(e) {
    if (!keyState.shift && props.blurOnEnter) {
        e.target.blur()
        e.preventDefault()
        e.stopPropagation()
        emits('submit')
    }
}

function onCancel() {
    emits('cancel')
}

onMounted(async () => {
    updateHeight()
    if(props.autoFocus) {
        await nextTick()
        focus()
    }
})
watch(() => props.width, () => {
    updateHeight()
})
watch(() => props.modelValue, () => {
    input(props.modelValue)
})
</script>

<template>
    <div :style="{
        width: props.width > 0 ? props.width + 'px' : '100%',
        minHeight: minHeight,
        cursor: urlMode ? 'pointer' : 'inherit',
        color: urlMode ? 'blue' : '',
    }" class="container m-0 p-0" @mouseenter="isHover = true" @mouseleave="isHover = false"
        :class="((isFocus && !props.noShadow) || props.alwaysShadow) ? 'focus' : 'container'" @click="focus">
        <ContentEditable ref="elem" @update:model-value="input" :model-value="localValue"
            :no-nl="props.urlMode" :contenteditable="props.editable"
            :style="{ width: (props.width - 5) + 'px' }" class="contenteditable" @keydown.escape="e => e.target.blur()"
            @focus="isFocus = true; emits('focus')" @blur="isFocus = false; emits('blur');" @click.stop="contentClick"
            @keydown.enter="onEnter" @keydown.esc.stop="onCancel" />
    </div>
</template>

<style scoped>
.contenteditable {
    white-space: break-spaces;
    overflow-wrap: break-word;
    padding-left: 2px;
    padding-right: 2px;
    box-sizing: content-box;
}

[contenteditable]:focus {
    outline: 0px solid transparent;
}

.container {
    cursor: text;
    /* border: 2px solid white; */
    border-radius: 5px;
}

.focus {
    /* border: 2px solid blue;
    border-radius: 5px; */
    box-shadow: 0px 0px 3px 1px var(--border-color);
    z-index: 99 !important;
    padding: 20px;
}
</style>
