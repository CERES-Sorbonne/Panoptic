<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch, withDefaults } from 'vue';
import ContentEditable from '../ContentEditable.vue';
import { keyState } from '@/data/keyState';

const props = withDefaults(defineProps<{
    tag: string
    editable: boolean | string
    modelValue: any
    noHtml: boolean
    noNl: boolean
    width: number
    minHeight: number
    urlMode: boolean
    onlyNumber: boolean
    noShadow: boolean
    alwaysShadow: boolean
    blurOnEnter: boolean
}>(), {
    editable: true,
    noHtml: true,
    noNl: false,
    minHeight: 30,
    blurOnEnter: true
})

const emit = defineEmits({
    'update:modelValue': Object,
    'update:height': String,
    'blur': undefined,
    'focus': undefined
})
const elem = ref(null)
const isFocus = ref(false)
const isHover = ref(false)
const minHeight = computed(() => {
    // return '0px'
    return (props.minHeight - 6) + 'px'
})

const urlMode = computed(() => props.urlMode && keyState.alt && isHover.value)

function focus() {
    elem.value.focus()
    emit('focus')
}

defineExpose({
    focus,
    isFocus
})



let height = 0

function input(value: string | number) {
    if (props.onlyNumber && value != "" && value != undefined) {
        emit('update:modelValue', Number(value))
    } else {
        emit('update:modelValue', value)
    }
    updateHeight()
}

function updateHeight() {
    nextTick(() => {
        if (!elem.value) return
        let newHeight = elem.value.$refs.element.clientHeight
        if (height != newHeight) {
            emit('update:height', newHeight)
        }
        height = newHeight
    })
}

function contentClick() {
    if (props.urlMode && keyState.alt && props.modelValue) {
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
    }
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
    <div :style="{
        width: props.width > 0 ? props.width + 'px' : '100%',
        minHeight: minHeight,
        cursor: urlMode ? 'pointer' : 'inherit',
        color: urlMode ? 'blue' : ''
    }" class="container m-0 p-0" @mouseenter="isHover = true" @mouseleave="isHover = false"
        :class="((isFocus && !props.noShadow) || props.alwaysShadow) ? 'focus' : 'container'" @click="focus">
        <ContentEditable ref="elem" :tag="props.tag" @update:model-value="input" :model-value="String(props.modelValue)"
            :only-number="props.onlyNumber" :no-html="props.noHtml" :no-nl="props.noNl"
            :contenteditable="props.editable && !(urlMode)" :style="{ width: (props.width - 5) + 'px' }"
            class="contenteditable" @keydown.escape="e => e.target.blur()" @focus="isFocus = true; emit('focus')"
            @blur="isFocus = false; emit('blur');" @click="contentClick" @keydown.enter="onEnter" />
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
