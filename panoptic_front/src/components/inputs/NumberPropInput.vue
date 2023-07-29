<script setup lang="ts">
import { Image, Property } from '@/data/models';
import { getImageProperty } from '@/utils/utils';
import { computed, onMounted, ref, watch } from 'vue';
import { globalStore } from '@/data/store';

const props = defineProps({
    property: Object as () => Property,
    image: Object as () => Image,
    width: Number,
    minHeight: { type: Number, default: 30 }

})
const emits = defineEmits({ 'update:height': Number })

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
    globalStore.setPropertyValue(props.property.id, props.image, localValue.value)
}


onMounted(updateFromStore)
// watch(propRef, updateFromStore)


defineExpose({
    // localValue,
    // inputElem
    focus
})

watch(localValue, save)


</script>

<template>
    <div :style="{height: props.minHeight+'px'}" @click="focus" class="container">
        <input type="number" v-model="localValue" :style="{width: (props.width-0)+'px'}" ref="elem"/>
    </div>
</template>

<style scoped>
.container {
    padding-top: 5px !important;
}

input {
    border: none;
    line-height: 30px !important;
    font-size: 15px !important;
}

</style>
