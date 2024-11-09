<script setup lang="ts">
import { Colors } from '@/data/models';
import { computed, onMounted, ref, withDefaults } from 'vue';
import 'vue-color-kit/dist/vue-color-kit.css'
import Dropdown from '../dropdowns/Dropdown.vue';

const props = withDefaults(defineProps<{
    modelValue?: number
    width?: number
    minHeight?: number
    rounded?: boolean
    teleport?: boolean
    offset?: number
}>(), {
    minHeight: 30,
    offset: 0
})
const emits = defineEmits(['update:height', 'update:modelValue'])

const localValue = ref(null)
const dropdown = ref(null)
const previewWidth = ref(100)
const previewElem = ref(null)

const width = computed(() => {
    if (props.width) return props.width + 'px'
    return '100%'
})

const color = computed(() => {
    if (props.modelValue == undefined) return 'white'

    let value = Number(props.modelValue)
    if (isNaN(value) || value > 12) return 'gray'
    return Colors[value].color
})
const isFocus = ref(false)

function focus() {
    if (isFocus.value) return
    isFocus.value = true
    dropdown.value.show()
}

function unfocus() {
    isFocus.value = false
    dropdown.value.hide()
}

function updateFromStore() {
    localValue.value = props.modelValue
}

function set(color) {
    emits('update:modelValue', color)
}

function onShow() {
    if (!previewElem.value) return
    previewWidth.value = Math.max(previewElem.value.offsetWidth, 100)
}

onMounted(updateFromStore)


defineExpose({
    focus
})
</script>

<template>
    <Dropdown :teleport="props.teleport" :offset="0" @show="onShow" ref="dropdown">
        <template #button>
            <div v-if="props.modelValue !== undefined" :style="{ height: props.minHeight + 'px' }"
                style="cursor: pointer;" ref="previewElem">
                <div :class="props.rounded ? 'rounded' : ''" style="margin: auto;"
                    :style="{ width: width, backgroundColor: color, height: 'calc(100% - 3px)', position: 'relative', top: props.offset + 'px' }">
                </div>
            </div>
            <div v-else class="text-secondary" style="cursor: pointer;" :style="{ width: width }">{{ $t('none') }}</div>
        </template>
        <template #popup="{ hide }">
            <div :style="{ width: (previewWidth + 8) + 'px' }" class="p-1">
                <div v-for="c, index in Colors" class="d-flex flex-row color-option" @click="set(index); hide();">
                    <div :style="{ backgroundColor: c.color }" class="color"></div>
                    <div class="color-name"> {{ c.name }}</div>
                </div>
                <div class="hr m-1"></div>
                <div class="d-flex flex-row color-option" @click="set(undefined); hide();">
                    <div :style="{ backgroundColor: '#ffffff' }" class="color"></div>
                    <div class="color-name"> None </div>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.container {
    padding: 0;
}

.color-name {
    text-transform: capitalize;
    line-height: 20px;
    color: var(--text-color);
    font-size: 13px;
}

.color {
    width: 20px;
    height: 20px;
    border-radius: 15%;
    border: 1px solid var(--border-color);
    margin-right: 5px;
}

.color-option {
    padding: 3px 5px;
    border-radius: 5px;
    margin: 0 3px;
    cursor: pointer;
    /* background-color: var(--light-grey); */
}

.color-option:hover {
    background-color: var(--light-grey);
}
</style>
