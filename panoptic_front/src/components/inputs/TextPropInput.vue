<script setup lang="ts">
import { Image, Property } from '@/data/models';
import { getImageProperty } from '@/utils/utils';
import { computed, onMounted, ref, watch } from 'vue';
import TextInput from './TextInput.vue';
import { globalStore } from '@/data/store';

const props = defineProps({
    property: Object as () => Property,
    image: Object as () => Image,
    noNl: {
        type: Boolean,
        default: false,
    },
    width: Number,
    minHeight: { type: Number, default: 30 },
    urlMode: Boolean

})
const emits = defineEmits({ 'update:height': Number })

const localValue = ref('')
const elem = ref(null)
// const inputElem = computed(() => elem.value.inputElem)

const propRef = computed(() => getImageProperty(props.image.id, props.property.id))
const isFocus = computed(() => elem.value?.isFocus)

function focus() {
    elem.value.focus()
}

function updateFromStore() {
    localValue.value = propRef.value.value ?? ''
}

function save() {
    if(propRef.value.value != localValue.value) {
        globalStore.setPropertyValue(props.property.id, props.image, localValue.value)
    }
}


onMounted(updateFromStore)
// watch(propRef, updateFromStore)


defineExpose({
    localValue,
    // inputElem
    focus
})

watch(localValue, save)

function log(e) {
    console.log(e)
}

</script>

<template>
    <div class="container">
        <TextInput  class="container" :contenteditable="true" tag="div" :no-html="true" v-model="localValue" :width="props.width"
            @update:height="h => emits('update:height', h)" ref="elem" :min-height="props.minHeight" :no-nl="props.noNl" :url-mode="props.urlMode"/>
    </div>
</template>

<style scoped>
.container {
    padding-top: 2px;
}

</style>
