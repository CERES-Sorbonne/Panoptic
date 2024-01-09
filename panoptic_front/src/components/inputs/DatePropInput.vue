<script setup lang="ts">
import { Image, Property } from '@/data/models';
import { getImageProperty } from '@/utils/utils';
import { computed, onMounted, ref, watch } from 'vue';
import { useProjectStore } from '@/data/projectStore'
import DateInput from './monoline/DateInput.vue';
const store = useProjectStore()
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

const propRef = computed(() => getImageProperty(props.image.id, props.property.id))
// const isFocus = computed(() => elem.value?.isFocus)

function focus() {
    elem.value.focus()
}

function updateFromStore() {
    localValue.value = propRef.value.value
}

function save() {
    store.setPropertyValue(props.property.id, props.image, localValue.value)
}


onMounted(updateFromStore)
onMounted(() => {
    // emits('update:height', 24)
})
// watch(propRef, updateFromStore)


defineExpose({
    // localValue,
    // inputElem
    focus
})

// watch(localValue, save)


</script>

<template>
    <div :style="{ height: props.minHeight + 'px', width: props.width+'px'}" class="container">
        <DateInput :image="props.image" :property="props.property"/>
    </div>
</template>

<style scoped>
.container {
    /* padding-top: 5px !important; */
    text-align: center;
}

input:focus,
input {

    outline: none !important;
    outline-width: 0 !important;
    box-shadow: none;
    -moz-box-shadow: none;
    -webkit-box-shadow: none;
    border: none;
    margin: 0 !important;
}
</style>
