<script setup lang="ts">
import { Image, Property } from '@/data/models';
import { getImageProperty } from '@/utils/utils';
import { computed, onMounted, ref, watch } from 'vue';
import { globalStore } from '@/data/store';
import 'vue-color-kit/dist/vue-color-kit.css'
import * as bootstrap from 'bootstrap'

const props = defineProps({
    property: Object as () => Property,
    image: Object as () => Image,
    width: Number,
    minHeight: { type: Number, default: 30 }

})
const emits = defineEmits({ 'update:height': Number })

const isFirefox = navigator.userAgent.indexOf("Firefox") != -1

const localValue = ref(null)
const elem = ref(null)
const dropdown = ref(null)

const propRef = computed(() => getImageProperty(props.image.id, props.property.id))
const isFocus = ref(false)

function focus() {
    if(isFocus.value) return
    isFocus.value = true
    dropdown.value.show()
}

function unfocus() {
    isFocus.value = false
    dropdown.value.hide()
}

function updateFromStore() {
    localValue.value = propRef.value.value
}

function set(color: string) {
    globalStore.setPropertyValue(props.property.id, props.image, color)
}

function saveDropdownRef(e) {
    if(!e) return

    e.addEventListener('show.bs.dropdown', () => isFocus.value = true)
    e.addEventListener('hide.bs.dropdown', () => isFocus.value = false)
}


onMounted(updateFromStore)
// watch(propRef, updateFromStore)


defineExpose({
    // localValue,
    // inputElem
    focus
})

const colors = [
    {name: 'grey', color: '#ced4da'},
    {name: 'red', color: '#ff8787'},
    {name: 'pink', color: '#f783ac'},
    {name: 'grape', color: '#da77f2'},
    {name: 'violet', color: '#9775fa'},
    {name: 'indigo', color: '#748ffc'},
    {name: 'blue', color: '#4dabf7'},
    {name: 'cyan', color: '#3bc9db'},
    {name: 'teal', color: '#38d9a9'},
    {name: 'green', color: '#69db7c'},
    {name: 'lime', color: '#a9e34b'},
    {name: 'yellow', color: '#ffd43b'},
    {name: 'orange', color: '#ffa94d'},

]


</script>

<template>
    <div :style="{ height: props.minHeight + 'px' }" class="container dropdown">
        <!-- <input type="color" v-model="localValue" :style="{
            width: props.width+ 'px',
        }" ref="elem" @focusin="isFocus = true" @focusout="isFocus = false"/> -->
        <div :ref="(el) => saveDropdownRef(el)" :style="{ width: props.width + 'px', backgroundColor: (propRef.value ?? 'white'), height: 'calc(100% - 3px)' }"
            data-bs-toggle="dropdown" aria-expanded="false">
        <div class="dropdown-menu">
            <div v-if="isFocus" class="">
                <div v-for="c in colors" class="d-flex flex-row color-option" @click="set(c.color)">
                    <div :style="{backgroundColor: c.color}" class="color"></div>
                    <div class="color-name"> {{ c.name }}</div>
                </div>
                <div class="hr m-1"></div>
                <div class="d-flex flex-row color-option" @click="set(undefined)">
                    <div :style="{backgroundColor: '#ffffff'}" class="color"></div>
                    <div class="color-name"> None </div>
                </div>
            </div>
        </div>
        </div>
    </div>
</template>

<style scoped>
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
