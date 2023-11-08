<script setup lang="ts">
import { Colors, Image, Property } from '@/data/models';
import { getImageProperty } from '@/utils/utils';
import { computed, onMounted, ref, watch } from 'vue';
import { globalStore } from '@/data/store';
import 'vue-color-kit/dist/vue-color-kit.css'
import * as bootstrap from 'bootstrap'

const props = defineProps({
    modelValue: Number,
    width: Number,
    minHeight: { type: Number, default: 30 },
    rounded: Boolean

})
const emits = defineEmits({ 'update:height': Number, 'update:modelValue': undefined })

const dropdown = ref(null)

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

function set(color: number) {
    emits('update:modelValue', color)
}

function saveDropdownRef(e) {
    if (!e) return

    e.addEventListener('show.bs.dropdown', () => isFocus.value = true)
    e.addEventListener('hide.bs.dropdown', () => isFocus.value = false)
}

defineExpose({
    focus
})

</script>

<template>
    <div :style="{ height: props.minHeight + 'px' }" class="container">
        <!-- <input type="color" v-model="localValue" :style="{
            width: props.width+ 'px',
        }" ref="elem" @focusin="isFocus = true" @focusout="isFocus = false"/> -->
        <div :ref="(el) => saveDropdownRef(el)" :class="props.rounded ? 'rounded' : ''"
            :style="{ width: props.width + 'px', backgroundColor: color, height: 'calc(100% - 3px)' }"
            data-bs-toggle="dropdown" aria-expanded="false">
            <span v-if="props.modelValue == undefined" class="text-secondary">None...</span>
        </div>
        <div class="dropdown-menu">
            <div v-if="isFocus" @focusout="unfocus">
                <div v-for="c, index in Colors" class="d-flex flex-row color-option" @click="set(index)">
                    <div :style="{ backgroundColor: c.color }" class="color"></div>
                    <div class="color-name"> {{ c.name }}</div>
                </div>
                <div class="hr m-1"></div>
                <div class="d-flex flex-row color-option" @click="set(undefined)">
                    <div :style="{ backgroundColor: '#ffffff' }" class="color"></div>
                    <div class="color-name"> None </div>
                </div>
            </div>
        </div>
    </div>
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
