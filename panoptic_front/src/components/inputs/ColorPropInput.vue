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

function save() {
    if (propRef.value.value == localValue.value) return
    globalStore.setPropertyValue(props.property.id, props.image, localValue.value)
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

watch(isFocus, () => {
    if (!isFocus.value) {
        save()
    }
})

function log(e) {
    console.log(e)
}


</script>

<template>
    <div :style="{ height: props.minHeight + 'px' }" class="container dropdown">
        <!-- <input type="color" v-model="localValue" :style="{
            width: props.width+ 'px',
        }" ref="elem" @focusin="isFocus = true" @focusout="isFocus = false"/> -->
        <div :ref="(el) => saveDropdownRef(el)" :style="{ width: props.width + 'px', backgroundColor: (propRef.value ?? 'white'), height: 'calc(100% - 3px)' }"
            data-bs-toggle="dropdown" aria-expanded="false">
        <div class="dropdown-menu">
            <div v-if="isFocus">
                im here and visible
            </div>
        </div>
        </div>
    </div>
</template>

<style scoped>
.container {
    /* padding-top: 5px !important; */
    text-align: left;
}

input:focus,
input {
    padding: 0;
    outline: none !important;
    outline-width: 0 !important;
    box-shadow: none;
    -moz-box-shadow: none;
    -webkit-box-shadow: none;
    border: none;
    margin: 0 !important;
}
</style>
