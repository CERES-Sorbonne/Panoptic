<script setup lang="ts">
import { Instance, Property } from '@/data/models';
import DateInput from './monoline/DateInput.vue';
import { ref } from 'vue';



const props = withDefaults(defineProps<{
    property: Property
    image: Instance
    width: number
    minHeight: number
}>(), {
    minHeight: 30
})
const emits = defineEmits({ 'update:height': Number })

const elem = ref(null)

function focus() {
    elem.value.focus()
}

defineExpose({
    focus
})
</script>

<template>
    <div :style="{ height: props.minHeight + 'px', width: props.width + 'px' }" class="container">
        <DateInput :image="props.image" :property="props.property" :width="props.width" />
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
